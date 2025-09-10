"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const auth_1 = require("../middleware/auth");
const errorHandler_1 = require("../middleware/errorHandler");
const client_1 = require("@prisma/client");
const router = (0, express_1.Router)();
const prisma = new client_1.PrismaClient();
router.get('/stats', auth_1.authenticateToken, (0, errorHandler_1.asyncHandler)(async (req, res) => {
    const userId = req.user?.id;
    try {
        const apiKeyCount = await prisma.$queryRaw `
      SELECT COUNT(*) as count 
      FROM api_keys 
      WHERE user_id = ${userId} AND is_active = 1
    `;
        const strategyCount = await prisma.$queryRaw `
      SELECT COUNT(*) as strategy_count
      FROM strategies 
      WHERE user_id = ${userId} 
        AND is_active = 1 
        AND name NOT LIKE '%指标%' 
        AND name NOT LIKE '%RSI%' 
        AND name NOT LIKE '%MACD%'
        AND name NOT LIKE '%MA%'
        AND name NOT LIKE '%KDJ%'
        AND name NOT LIKE '%BOLL%'
    `;
        const indicatorCount = await prisma.$queryRaw `
      SELECT COUNT(*) as indicator_count
      FROM strategies 
      WHERE user_id = ${userId} 
        AND is_active = 1 
        AND (name LIKE '%指标%' 
             OR name LIKE '%RSI%' 
             OR name LIKE '%MACD%'
             OR name LIKE '%MA%'
             OR name LIKE '%KDJ%'
             OR name LIKE '%BOLL%')
    `;
        const liveStrategyCount = await prisma.$queryRaw `
      SELECT 
        COUNT(*) as total_live,
        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_live,
        COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_live
      FROM live_strategies 
      WHERE user_id = ${userId} 
        AND status IN ('running', 'paused')
    `;
        const thirtyDaysAgo = new Date();
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
        const recentTrades = await prisma.$queryRaw `
      SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN side = 'BUY' THEN total_amount ELSE -total_amount END) as net_amount,
        AVG(total_amount) as avg_trade_size
      FROM trades 
      WHERE user_id = ${userId} AND created_at >= ${thirtyDaysAgo}
    `;
        const profitability = await prisma.$queryRaw `
      SELECT 
        SUM(CASE WHEN side = 'SELL' THEN total_amount - fee ELSE -(total_amount + fee) END) as realized_pnl
      FROM trades 
      WHERE user_id = ${userId} AND created_at >= ${thirtyDaysAgo}
    `;
        const user = await prisma.user.findUnique({
            where: { id: Number(userId) },
            select: {
                membershipLevel: true,
                membershipExpiresAt: true
            }
        });
        const membershipLimits = getMembershipLimits(user?.membershipLevel || 'basic');
        const stats = {
            api_keys: {
                current: Number(apiKeyCount[0]?.count || 0),
                limit: membershipLimits.api_keys
            },
            strategies: {
                current: Number(strategyCount[0]?.strategy_count || 0),
                limit: membershipLimits.strategies
            },
            indicators: {
                current: Number(indicatorCount[0]?.indicator_count || 0),
                limit: 5
            },
            live_strategies: {
                total: Number(liveStrategyCount[0]?.total_live || 0),
                running: Number(liveStrategyCount[0]?.running_live || 0),
                paused: Number(liveStrategyCount[0]?.paused_live || 0),
                limit: 5
            },
            trading_stats: {
                total_trades: Number(recentTrades[0]?.total_trades || 0),
                net_amount: Number(recentTrades[0]?.net_amount || 0),
                avg_trade_size: Number(recentTrades[0]?.avg_trade_size || 0),
                realized_pnl: Number(profitability[0]?.realized_pnl || 0)
            },
            monthly_return: calculateMonthlyReturn(profitability[0]?.realized_pnl || 0),
            membership: {
                level: user?.membershipLevel || 'basic',
                expires_at: user?.membershipExpiresAt
            }
        };
        res.json({
            success: true,
            data: stats
        });
    }
    catch (error) {
        console.error('获取仪表板统计失败:', error);
        res.status(500).json({
            success: false,
            message: '获取统计数据失败',
            error: error instanceof Error ? error.message : '未知错误'
        });
    }
}));
router.get('/profit-curve', auth_1.authenticateToken, (0, errorHandler_1.asyncHandler)(async (req, res) => {
    const userId = req.user?.id;
    const days = parseInt(req.query.days) || 90;
    try {
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - days);
        const dailyTrades = await prisma.$queryRaw `
      SELECT 
        DATE(created_at) as trade_date,
        SUM(CASE WHEN side = 'SELL' THEN total_amount - fee ELSE -(total_amount + fee) END) as daily_pnl
      FROM trades 
      WHERE user_id = ${userId} 
        AND created_at >= ${startDate}
        AND trade_type = 'LIVE'
      GROUP BY DATE(created_at)
      ORDER BY trade_date ASC
    `;
        let cumulativePnL = 0;
        const profitCurve = dailyTrades.map(trade => {
            cumulativePnL += Number(trade.daily_pnl || 0);
            return {
                timestamp: trade.trade_date,
                value: cumulativePnL
            };
        });
        if (profitCurve.length === 0) {
            const defaultData = generateDemoData(days);
            return res.json({
                success: true,
                data: defaultData,
                is_demo: true
            });
        }
        res.json({
            success: true,
            data: profitCurve,
            is_demo: false
        });
    }
    catch (error) {
        console.error('获取收益曲线失败:', error);
        const defaultData = generateDemoData(days);
        res.json({
            success: true,
            data: defaultData,
            is_demo: true,
            note: '使用演示数据，实际交易数据加载失败'
        });
    }
}));
function getMembershipLimits(level) {
    const limits = {
        basic: { api_keys: 1, strategies: 2 },
        premium: { api_keys: 5, strategies: 10 },
        professional: { api_keys: 20, strategies: 50 }
    };
    return limits[level] || limits.basic;
}
function calculateMonthlyReturn(realizedPnl) {
    const initialCapital = 10000;
    const monthlyReturn = (realizedPnl / initialCapital) * 100;
    return Math.round(monthlyReturn * 100) / 100;
}
function generateDemoData(days) {
    const data = [];
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    let cumulativeReturn = 0;
    for (let i = 0; i < Math.min(days, 90); i += 7) {
        const date = new Date(startDate);
        date.setDate(date.getDate() + i);
        const weeklyGain = (Math.random() * 4 - 1) + 0.5;
        cumulativeReturn += weeklyGain;
        data.push({
            timestamp: date.toISOString().split('T')[0],
            value: Math.round(cumulativeReturn * 100) / 100
        });
    }
    return data;
}
exports.default = router;
//# sourceMappingURL=dashboard.js.map