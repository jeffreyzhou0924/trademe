import { Router, Request, Response } from 'express'
import { authenticateToken } from '../middleware/auth'
import { asyncHandler } from '../middleware/errorHandler'
import { PrismaClient } from '@prisma/client'

const router = Router()
const prisma = new PrismaClient()

/**
 * 获取用户仪表板统计数据
 */
router.get('/stats', authenticateToken, asyncHandler(async (req: Request, res: Response) => {
  const userId = req.user?.id

  try {
    // 查询用户的API密钥数量
    const apiKeyCount = await prisma.$queryRaw`
      SELECT COUNT(*) as count 
      FROM api_keys 
      WHERE user_id = ${userId} AND is_active = 1
    ` as any[]
    
    // 查询用户的AI策略数量（排除指标）
    const strategyCount = await prisma.$queryRaw`
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
    ` as any[]

    // 查询用户的AI指标数量
    const indicatorCount = await prisma.$queryRaw`
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
    ` as any[]

    // 查询用户的实盘交易数量（运行中+暂停）
    const liveStrategyCount = await prisma.$queryRaw`
      SELECT 
        COUNT(*) as total_live,
        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_live,
        COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_live
      FROM live_strategies 
      WHERE user_id = ${userId} 
        AND status IN ('running', 'paused')
    ` as any[]

    // 查询最近30天的交易统计
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

    const recentTrades = await prisma.$queryRaw`
      SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN side = 'BUY' THEN total_amount ELSE -total_amount END) as net_amount,
        AVG(total_amount) as avg_trade_size
      FROM trades 
      WHERE user_id = ${userId} AND created_at >= ${thirtyDaysAgo}
    ` as any[]

    // 计算收益率（简单计算，基于交易数据）
    const profitability = await prisma.$queryRaw`
      SELECT 
        SUM(CASE WHEN side = 'SELL' THEN total_amount - fee ELSE -(total_amount + fee) END) as realized_pnl
      FROM trades 
      WHERE user_id = ${userId} AND created_at >= ${thirtyDaysAgo}
    ` as any[]

    // 获取用户会员信息
    const user = await prisma.user.findUnique({
      where: { id: Number(userId!) },
      select: {
        membershipLevel: true,
        membershipExpiresAt: true
      }
    })

    // 计算会员限制
    const membershipLimits = getMembershipLimits(user?.membershipLevel || 'basic')

    const stats = {
      api_keys: {
        current: Number(apiKeyCount[0]?.count || 0),
        limit: membershipLimits.api_keys
      },
      // AI生成的策略统计
      strategies: {
        current: Number(strategyCount[0]?.strategy_count || 0),
        limit: membershipLimits.strategies
      },
      // AI生成的指标统计
      indicators: {
        current: Number(indicatorCount[0]?.indicator_count || 0),
        limit: 5 // 指标限制为5个
      },
      // 实盘交易统计
      live_strategies: {
        total: Number(liveStrategyCount[0]?.total_live || 0),
        running: Number(liveStrategyCount[0]?.running_live || 0),
        paused: Number(liveStrategyCount[0]?.paused_live || 0),
        limit: 5 // 实盘交易限制为5个
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
    }

    res.json({
      success: true,
      data: stats
    })

  } catch (error) {
    console.error('获取仪表板统计失败:', error)
    res.status(500).json({
      success: false,
      message: '获取统计数据失败',
      error: error instanceof Error ? error.message : '未知错误'
    })
  }
}))

/**
 * 获取收益曲线数据（最近3个月）
 */
router.get('/profit-curve', authenticateToken, asyncHandler(async (req: Request, res: Response) => {
  const userId = req.user?.id
  const days = parseInt(req.query.days as string) || 90

  try {
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - days)

    // 按日期聚合交易数据，计算累计收益
    const dailyTrades = await prisma.$queryRaw`
      SELECT 
        DATE(created_at) as trade_date,
        SUM(CASE WHEN side = 'SELL' THEN total_amount - fee ELSE -(total_amount + fee) END) as daily_pnl
      FROM trades 
      WHERE user_id = ${userId} 
        AND created_at >= ${startDate}
        AND trade_type = 'LIVE'
      GROUP BY DATE(created_at)
      ORDER BY trade_date ASC
    ` as any[]

    // 计算累计收益曲线
    let cumulativePnL = 0
    const profitCurve = dailyTrades.map(trade => {
      cumulativePnL += Number(trade.daily_pnl || 0)
      return {
        timestamp: trade.trade_date,
        value: cumulativePnL
      }
    })

    // 如果没有交易数据，返回默认的演示数据
    if (profitCurve.length === 0) {
      const defaultData = generateDemoData(days)
      return res.json({
        success: true,
        data: defaultData,
        is_demo: true
      })
    }

    res.json({
      success: true,
      data: profitCurve,
      is_demo: false
    })

  } catch (error) {
    console.error('获取收益曲线失败:', error)
    
    // 发生错误时返回演示数据
    const defaultData = generateDemoData(days)
    res.json({
      success: true,
      data: defaultData,
      is_demo: true,
      note: '使用演示数据，实际交易数据加载失败'
    })
  }
}))

// 辅助函数
function getMembershipLimits(level: string) {
  const limits = {
    basic: { api_keys: 1, strategies: 2 },
    premium: { api_keys: 5, strategies: 10 },
    professional: { api_keys: 20, strategies: 50 }
  }
  return limits[level as keyof typeof limits] || limits.basic
}

function calculateMonthlyReturn(realizedPnl: number): number {
  // 简单的月收益率计算（假设初始资金为10000）
  const initialCapital = 10000
  const monthlyReturn = (realizedPnl / initialCapital) * 100
  return Math.round(monthlyReturn * 100) / 100
}

function generateDemoData(days: number) {
  const data = []
  const startDate = new Date()
  startDate.setDate(startDate.getDate() - days)
  
  let cumulativeReturn = 0
  for (let i = 0; i < Math.min(days, 90); i += 7) {
    const date = new Date(startDate)
    date.setDate(date.getDate() + i)
    
    // 生成逐渐增长的演示数据
    const weeklyGain = (Math.random() * 4 - 1) + 0.5 // -1% to +3.5%
    cumulativeReturn += weeklyGain
    
    data.push({
      timestamp: date.toISOString().split('T')[0],
      value: Math.round(cumulativeReturn * 100) / 100
    })
  }
  
  return data
}

export default router