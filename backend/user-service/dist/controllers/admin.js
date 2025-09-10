"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../config/database");
class AdminController {
    static async getUsers(req, res) {
        const { page = 1, limit = 20, search, membership_level, is_active } = req.query;
        const skip = (Number(page) - 1) * Number(limit);
        const where = {};
        if (search) {
            where.OR = [
                { username: { contains: search } },
                { email: { contains: search } },
            ];
        }
        if (membership_level) {
            where.membershipLevel = membership_level.toUpperCase();
        }
        if (is_active !== undefined) {
            where.isActive = is_active === 'true';
        }
        const [users, total] = await Promise.all([
            database_1.prisma.user.findMany({
                where,
                select: {
                    id: true,
                    username: true,
                    email: true,
                    membershipLevel: true,
                    isActive: true,
                    emailVerified: true,
                    lastLoginAt: true,
                    createdAt: true,
                },
                skip,
                take: Number(limit),
                orderBy: { createdAt: 'desc' },
            }),
            database_1.prisma.user.count({ where }),
        ]);
        const totalPages = Math.ceil(total / Number(limit));
        res.json({
            success: true,
            code: 200,
            message: '获取成功',
            data: {
                users: users.map(user => ({
                    id: user.id.toString(),
                    username: user.username,
                    email: user.email,
                    membership_level: user.membershipLevel.toLowerCase(),
                    is_active: user.isActive,
                    email_verified: user.emailVerified,
                    last_login_at: user.lastLoginAt?.toISOString(),
                    created_at: user.createdAt.toISOString(),
                })),
                pagination: {
                    current_page: Number(page),
                    per_page: Number(limit),
                    total,
                    total_pages: totalPages,
                    has_next: Number(page) < totalPages,
                    has_prev: Number(page) > 1,
                },
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async getUserDetail(req, res) {
        const { userId } = req.params;
        try {
            const user = await database_1.prisma.user.findUnique({
                where: { id: Number(userId) },
                select: {
                    id: true,
                    username: true,
                    email: true,
                    phone: true,
                    avatarUrl: true,
                    membershipLevel: true,
                    membershipExpiresAt: true,
                    isActive: true,
                    emailVerified: true,
                    lastLoginAt: true,
                    createdAt: true,
                    updatedAt: true,
                    preferences: true,
                },
            });
            if (!user) {
                return res.status(404).json({
                    success: false,
                    code: 404,
                    message: '用户不存在',
                    error_code: 'USER_NOT_FOUND',
                });
            }
            res.json({
                success: true,
                code: 200,
                message: '获取成功',
                data: {
                    id: user.id.toString(),
                    username: user.username,
                    email: user.email,
                    phone: user.phone,
                    avatar_url: user.avatarUrl,
                    membership_level: user.membershipLevel.toLowerCase(),
                    membership_expires_at: user.membershipExpiresAt?.toISOString(),
                    is_active: user.isActive,
                    email_verified: user.emailVerified,
                    last_login_at: user.lastLoginAt?.toISOString(),
                    created_at: user.createdAt.toISOString(),
                    updated_at: user.updatedAt.toISOString(),
                    preferences: user.preferences ? JSON.parse(user.preferences) : null,
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Get user detail error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async updateUser(req, res) {
        const { userId } = req.params;
        const { username, email, phone, membership_level, membership_expires_at, is_active, email_verified } = req.body;
        try {
            const existingUser = await database_1.prisma.user.findUnique({
                where: { id: Number(userId) },
            });
            if (!existingUser) {
                return res.status(404).json({
                    success: false,
                    code: 404,
                    message: '用户不存在',
                    error_code: 'USER_NOT_FOUND',
                });
            }
            const updateData = {
                updatedAt: new Date(),
            };
            if (username !== undefined)
                updateData.username = username;
            if (email !== undefined)
                updateData.email = email;
            if (phone !== undefined)
                updateData.phone = phone;
            if (membership_level !== undefined) {
                updateData.membershipLevel = membership_level.toUpperCase();
            }
            if (membership_expires_at !== undefined) {
                updateData.membershipExpiresAt = new Date(membership_expires_at);
            }
            if (is_active !== undefined)
                updateData.isActive = is_active;
            if (email_verified !== undefined)
                updateData.emailVerified = email_verified;
            const updatedUser = await database_1.prisma.user.update({
                where: { id: Number(userId) },
                data: updateData,
                select: {
                    id: true,
                    username: true,
                    email: true,
                    membershipLevel: true,
                    membershipExpiresAt: true,
                    isActive: true,
                    emailVerified: true,
                    updatedAt: true,
                },
            });
            res.json({
                success: true,
                code: 200,
                message: '更新成功',
                data: {
                    id: updatedUser.id.toString(),
                    username: updatedUser.username,
                    email: updatedUser.email,
                    membership_level: updatedUser.membershipLevel.toLowerCase(),
                    membership_expires_at: updatedUser.membershipExpiresAt?.toISOString(),
                    is_active: updatedUser.isActive,
                    email_verified: updatedUser.emailVerified,
                    updated_at: updatedUser.updatedAt.toISOString(),
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Update user error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async getSystemStats(req, res) {
        try {
            const [totalUsers, activeUsers, basicUsers, premiumUsers, professionalUsers, verifiedUsers] = await Promise.all([
                database_1.prisma.user.count(),
                database_1.prisma.user.count({ where: { isActive: true } }),
                database_1.prisma.user.count({ where: { membershipLevel: 'BASIC' } }),
                database_1.prisma.user.count({ where: { membershipLevel: 'PREMIUM' } }),
                database_1.prisma.user.count({ where: { membershipLevel: 'PROFESSIONAL' } }),
                database_1.prisma.user.count({ where: { emailVerified: true } })
            ]);
            const sevenDaysAgo = new Date();
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            const recentUsers = await database_1.prisma.user.count({
                where: {
                    createdAt: {
                        gte: sevenDaysAgo,
                    },
                },
            });
            res.json({
                success: true,
                code: 200,
                message: '获取成功',
                data: {
                    users: {
                        total: totalUsers,
                        active: activeUsers,
                        inactive: totalUsers - activeUsers,
                        verified: verifiedUsers,
                        unverified: totalUsers - verifiedUsers,
                        recent_7days: recentUsers,
                    },
                    membership: {
                        basic: basicUsers,
                        premium: premiumUsers,
                        professional: professionalUsers,
                    },
                    growth: {
                        weekly_new_users: recentUsers,
                        active_rate: totalUsers > 0 ? ((activeUsers / totalUsers) * 100).toFixed(2) : '0.00',
                        verification_rate: totalUsers > 0 ? ((verifiedUsers / totalUsers) * 100).toFixed(2) : '0.00',
                    }
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Get system stats error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async getUserActivities(req, res) {
        const { userId } = req.params;
        const { page = 1, limit = 20 } = req.query;
        try {
            const skip = (Number(page) - 1) * Number(limit);
            const mockActivities = [
                {
                    id: '1',
                    action: '登录系统',
                    ip_address: '192.168.1.100',
                    user_agent: 'Mozilla/5.0 Chrome/120.0.0.0',
                    created_at: new Date().toISOString(),
                },
                {
                    id: '2',
                    action: '修改用户信息',
                    ip_address: '192.168.1.100',
                    user_agent: 'Mozilla/5.0 Chrome/120.0.0.0',
                    created_at: new Date(Date.now() - 3600000).toISOString(),
                }
            ];
            res.json({
                success: true,
                code: 200,
                message: '获取成功',
                data: {
                    activities: mockActivities,
                    pagination: {
                        current_page: Number(page),
                        per_page: Number(limit),
                        total: 2,
                        total_pages: 1,
                        has_next: false,
                        has_prev: false,
                    },
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Get user activities error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async getUserMembershipStats(req, res) {
        const { userId } = req.params;
        try {
            const user = await database_1.prisma.user.findUnique({
                where: { id: Number(userId) },
                select: {
                    id: true,
                    username: true,
                    email: true,
                    membershipLevel: true,
                    membershipExpiresAt: true,
                    emailVerified: true,
                    createdAt: true,
                },
            });
            if (!user) {
                return res.status(404).json({
                    success: false,
                    code: 404,
                    message: '用户不存在',
                    error_code: 'USER_NOT_FOUND',
                });
            }
            let usageStats = null;
            try {
                const response = await fetch(`http://localhost:8001/api/v1/membership/stats/${userId}`, {
                    headers: {
                        'Authorization': req.headers.authorization || '',
                    },
                });
                if (response.ok) {
                    const data = await response.json();
                    usageStats = data.data;
                }
            }
            catch (error) {
                console.warn('Failed to fetch usage stats from trading service:', error);
            }
            const membershipFeatures = {
                BASIC: {
                    name: '免费用户',
                    api_keys: 1,
                    ai_daily: 20,
                    tick_backtest: 0,
                    storage: 0.005,
                    indicators: 1,
                    strategies: 1,
                    live_trading: 1,
                },
                PREMIUM: {
                    name: '高级用户',
                    api_keys: 5,
                    ai_daily: 100,
                    tick_backtest: 30,
                    storage: 0.050,
                    indicators: 5,
                    strategies: 5,
                    live_trading: 5,
                },
                PROFESSIONAL: {
                    name: '专业用户',
                    api_keys: 10,
                    ai_daily: 200,
                    tick_backtest: 100,
                    storage: 0.100,
                    indicators: 10,
                    strategies: 10,
                    live_trading: 10,
                },
            };
            const currentLimits = membershipFeatures[user.membershipLevel] || membershipFeatures.BASIC;
            res.json({
                success: true,
                code: 200,
                message: '获取成功',
                data: {
                    user: {
                        id: user.id.toString(),
                        username: user.username,
                        email: user.email,
                        membership_level: user.membershipLevel.toLowerCase(),
                        membership_name: currentLimits.name,
                        membership_expires_at: user.membershipExpiresAt?.toISOString(),
                        email_verified: user.emailVerified,
                        created_at: user.createdAt.toISOString(),
                    },
                    limits: currentLimits,
                    usage: usageStats || {
                        api_keys_count: 0,
                        ai_usage_today: 0,
                        tick_backtest_today: 0,
                        storage_used: 0,
                        indicators_count: 0,
                        strategies_count: 0,
                        live_trading_count: 0,
                    },
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Get user membership stats error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async batchUpdateUsers(req, res) {
        const { user_ids, action, data } = req.body;
        try {
            if (!user_ids || !Array.isArray(user_ids) || user_ids.length === 0) {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: '用户ID列表不能为空',
                    error_code: 'INVALID_USER_IDS',
                });
            }
            let updateData = {};
            let resultMessage = '';
            switch (action) {
                case 'activate':
                    updateData = { isActive: true };
                    resultMessage = `成功激活${user_ids.length}个用户`;
                    break;
                case 'deactivate':
                    updateData = { isActive: false };
                    resultMessage = `成功停用${user_ids.length}个用户`;
                    break;
                case 'verify_email':
                    updateData = { emailVerified: true };
                    resultMessage = `成功验证${user_ids.length}个用户的邮箱`;
                    break;
                case 'upgrade_membership':
                    if (!data.membership_level) {
                        return res.status(400).json({
                            success: false,
                            code: 400,
                            message: '升级会员等级不能为空',
                            error_code: 'MISSING_MEMBERSHIP_LEVEL',
                        });
                    }
                    updateData = {
                        membershipLevel: data.membership_level.toUpperCase(),
                        membershipExpiresAt: data.expires_at ? new Date(data.expires_at) : null,
                    };
                    resultMessage = `成功升级${user_ids.length}个用户到${data.membership_level}`;
                    break;
                default:
                    return res.status(400).json({
                        success: false,
                        code: 400,
                        message: '不支持的操作类型',
                        error_code: 'UNSUPPORTED_ACTION',
                    });
            }
            const result = await database_1.prisma.user.updateMany({
                where: {
                    id: { in: user_ids.map((id) => Number(id)) },
                },
                data: updateData,
            });
            res.json({
                success: true,
                code: 200,
                message: resultMessage,
                data: {
                    updated_count: result.count,
                    requested_count: user_ids.length,
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Batch update users error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async getMembershipAnalytics(req, res) {
        try {
            const membershipStats = await database_1.prisma.user.groupBy({
                by: ['membershipLevel'],
                _count: {
                    membershipLevel: true,
                },
                where: {
                    isActive: true,
                },
            });
            const revenueStats = {
                monthly_revenue: 2380,
                yearly_revenue: 28560,
                active_subscriptions: membershipStats.reduce((sum, stat) => {
                    if (stat.membershipLevel !== 'BASIC') {
                        return sum + stat._count.membershipLevel;
                    }
                    return sum;
                }, 0),
            };
            const expiringMemberships = await database_1.prisma.user.findMany({
                where: {
                    membershipExpiresAt: {
                        lte: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
                        gte: new Date(),
                    },
                    membershipLevel: {
                        not: 'BASIC',
                    },
                },
                select: {
                    id: true,
                    username: true,
                    email: true,
                    membershipLevel: true,
                    membershipExpiresAt: true,
                },
                take: 10,
                orderBy: {
                    membershipExpiresAt: 'asc',
                },
            });
            res.json({
                success: true,
                code: 200,
                message: '获取成功',
                data: {
                    membership_distribution: membershipStats.map(stat => ({
                        level: stat.membershipLevel.toLowerCase(),
                        count: stat._count.membershipLevel,
                    })),
                    revenue: revenueStats,
                    expiring_soon: expiringMemberships.map(user => ({
                        id: user.id.toString(),
                        username: user.username,
                        email: user.email,
                        membership_level: user.membershipLevel.toLowerCase(),
                        expires_at: user.membershipExpiresAt?.toISOString(),
                        days_remaining: user.membershipExpiresAt
                            ? Math.ceil((user.membershipExpiresAt.getTime() - Date.now()) / (24 * 60 * 60 * 1000))
                            : 0,
                    })),
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            console.error('Get membership analytics error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '服务器内部错误',
                error_code: 'INTERNAL_SERVER_ERROR',
            });
        }
    }
    static async getClaudeAccounts(req, res) {
        try {
            const response = await fetch('http://localhost:8001/api/v1/admin/claude/accounts', {
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: '获取成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('获取Claude账号池失败');
            }
        }
        catch (error) {
            console.error('Get Claude accounts error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'Claude账号池获取失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async addClaudeAccount(req, res) {
        const { account_name, api_key, organization_id, project_id, daily_limit, proxy_id } = req.body;
        try {
            const response = await fetch('http://localhost:8001/api/v1/admin/claude/accounts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': req.headers.authorization || '',
                },
                body: JSON.stringify({
                    account_name,
                    api_key,
                    organization_id,
                    project_id,
                    daily_limit,
                    proxy_id
                }),
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 201,
                    message: 'Claude账号添加成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('添加Claude账号失败');
            }
        }
        catch (error) {
            console.error('Add Claude account error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'Claude账号添加失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async updateClaudeAccount(req, res) {
        const { accountId } = req.params;
        const updateData = req.body;
        try {
            const response = await fetch(`http://localhost:8001/api/v1/admin/claude/accounts/${accountId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': req.headers.authorization || '',
                },
                body: JSON.stringify(updateData),
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: 'Claude账号更新成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('更新Claude账号失败');
            }
        }
        catch (error) {
            console.error('Update Claude account error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'Claude账号更新失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async deleteClaudeAccount(req, res) {
        const { accountId } = req.params;
        try {
            const response = await fetch(`http://localhost:8001/api/v1/admin/claude/accounts/${accountId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                res.json({
                    success: true,
                    code: 200,
                    message: 'Claude账号删除成功',
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('删除Claude账号失败');
            }
        }
        catch (error) {
            console.error('Delete Claude account error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'Claude账号删除失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async testClaudeAccount(req, res) {
        const { accountId } = req.params;
        try {
            const response = await fetch(`http://localhost:8001/api/v1/admin/claude/accounts/${accountId}/test`, {
                method: 'POST',
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: 'Claude账号测试完成',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('Claude账号测试失败');
            }
        }
        catch (error) {
            console.error('Test Claude account error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'Claude账号测试失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async getClaudeUsageStats(req, res) {
        const { days = 30 } = req.query;
        try {
            const response = await fetch(`http://localhost:8001/api/v1/admin/claude/usage-stats?days=${days}`, {
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: '获取成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('获取Claude使用统计失败');
            }
        }
        catch (error) {
            console.error('Get Claude usage stats error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'Claude使用统计获取失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async getProxies(req, res) {
        try {
            const response = await fetch('http://localhost:8001/api/v1/admin/proxies', {
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: '获取成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('获取代理服务器失败');
            }
        }
        catch (error) {
            console.error('Get proxies error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '代理服务器获取失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async getSchedulerConfig(req, res) {
        try {
            const response = await fetch('http://localhost:8001/api/v1/admin/claude/scheduler-config', {
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: '获取成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('获取调度配置失败');
            }
        }
        catch (error) {
            console.error('Get scheduler config error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '调度配置获取失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async updateSchedulerConfig(req, res) {
        const configData = req.body;
        try {
            const response = await fetch('http://localhost:8001/api/v1/admin/claude/scheduler-config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': req.headers.authorization || '',
                },
                body: JSON.stringify(configData),
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: '调度配置更新成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('更新调度配置失败');
            }
        }
        catch (error) {
            console.error('Update scheduler config error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: '调度配置更新失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
    static async getAIAnomalyDetection(req, res) {
        try {
            const response = await fetch('http://localhost:8001/api/v1/admin/claude/anomaly-detection', {
                headers: {
                    'Authorization': req.headers.authorization || '',
                },
            });
            if (response.ok) {
                const data = await response.json();
                res.json({
                    success: true,
                    code: 200,
                    message: '获取成功',
                    data: data,
                    timestamp: new Date().toISOString(),
                    request_id: req.headers['x-request-id'],
                });
            }
            else {
                throw new Error('获取AI异常检测报告失败');
            }
        }
        catch (error) {
            console.error('Get AI anomaly detection error:', error);
            res.status(500).json({
                success: false,
                code: 500,
                message: 'AI异常检测报告获取失败',
                error_code: 'CLAUDE_SERVICE_ERROR',
            });
        }
    }
}
exports.default = AdminController;
//# sourceMappingURL=admin.js.map