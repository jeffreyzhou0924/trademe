"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.requireAdmin = exports.requireEmailVerification = exports.requireMembership = exports.optionalAuth = exports.authenticateToken = void 0;
const jwt_1 = require("../utils/jwt");
const database_1 = require("../config/database");
const redis_1 = require("../config/redis");
const logger_1 = require("../utils/logger");
const authenticateToken = async (req, res, next) => {
    try {
        const authHeader = req.headers.authorization;
        const token = authHeader && authHeader.split(' ')[1];
        if (!token) {
            return res.status(401).json({
                success: false,
                code: 401,
                message: '访问令牌缺失',
                error_code: 'MISSING_TOKEN',
            });
        }
        let decoded;
        try {
            decoded = (0, jwt_1.verifyAccessToken)(token);
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Token verification failed';
            return res.status(401).json({
                success: false,
                code: 401,
                message: '访问令牌无效或已过期',
                error_code: errorMessage.includes('expired') ? 'TOKEN_EXPIRED' : 'INVALID_TOKEN',
            });
        }
        const isBlacklisted = await redis_1.redis.exists(`blacklist:token:${token}`);
        if (isBlacklisted) {
            return res.status(401).json({
                success: false,
                code: 401,
                message: '令牌已失效',
                error_code: 'TOKEN_BLACKLISTED',
            });
        }
        const user = await database_1.prisma.user.findUnique({
            where: { id: Number(decoded.userId) },
            select: {
                id: true,
                username: true,
                email: true,
                membershipLevel: true,
                membershipExpiresAt: true,
                isActive: true,
                emailVerified: true,
            },
        });
        if (!user) {
            return res.status(401).json({
                success: false,
                code: 401,
                message: '用户不存在',
                error_code: 'USER_NOT_FOUND',
            });
        }
        if (!user.isActive) {
            return res.status(403).json({
                success: false,
                code: 403,
                message: '用户账户已被禁用',
                error_code: 'USER_DISABLED',
            });
        }
        req.user = {
            id: user.id.toString(),
            email: user.email,
            username: user.username,
            membershipLevel: user.membershipLevel,
            membershipExpiresAt: user.membershipExpiresAt || undefined,
            isActive: user.isActive,
        };
        req.token = token;
        next();
    }
    catch (error) {
        logger_1.logger.error('Authentication middleware error:', error);
        return res.status(500).json({
            success: false,
            code: 500,
            message: '认证服务错误',
            error_code: 'AUTH_SERVICE_ERROR',
        });
    }
};
exports.authenticateToken = authenticateToken;
const optionalAuth = async (req, res, next) => {
    try {
        const authHeader = req.headers.authorization;
        const token = authHeader && authHeader.split(' ')[1];
        if (!token) {
            return next();
        }
        try {
            const decoded = (0, jwt_1.verifyAccessToken)(token);
            const isBlacklisted = await redis_1.redis.exists(`blacklist:token:${token}`);
            if (!isBlacklisted) {
                const user = await database_1.prisma.user.findUnique({
                    where: { id: Number(decoded.userId) },
                    select: {
                        id: true,
                        username: true,
                        email: true,
                        membershipLevel: true,
                        membershipExpiresAt: true,
                        isActive: true,
                    },
                });
                if (user && user.isActive) {
                    req.user = {
                        id: user.id.toString(),
                        email: user.email,
                        username: user.username,
                        membershipLevel: user.membershipLevel,
                        membershipExpiresAt: user.membershipExpiresAt || undefined,
                        isActive: user.isActive,
                    };
                    req.token = token;
                }
            }
        }
        catch (error) {
            logger_1.logger.debug('Optional auth token verification failed:', error);
        }
        next();
    }
    catch (error) {
        logger_1.logger.error('Optional auth middleware error:', error);
        next();
    }
};
exports.optionalAuth = optionalAuth;
const requireMembership = (requiredLevel) => {
    return (req, res, next) => {
        if (!req.user) {
            return res.status(401).json({
                success: false,
                code: 401,
                message: '需要登录',
                error_code: 'AUTHENTICATION_REQUIRED',
            });
        }
        const membershipLevels = {
            BASIC: 1,
            PREMIUM: 2,
            PROFESSIONAL: 3,
        };
        const userLevel = membershipLevels[req.user.membershipLevel] || 0;
        const requiredLevelValue = membershipLevels[requiredLevel];
        if (userLevel < requiredLevelValue) {
            return res.status(403).json({
                success: false,
                code: 403,
                message: `需要${requiredLevel === 'PREMIUM' ? '高级' : '专业'}会员权限`,
                error_code: 'INSUFFICIENT_MEMBERSHIP',
                required_level: requiredLevel,
                current_level: req.user.membershipLevel,
            });
        }
        if (req.user.membershipExpiresAt && req.user.membershipExpiresAt < new Date()) {
            return res.status(403).json({
                success: false,
                code: 403,
                message: '会员已过期，请续费',
                error_code: 'MEMBERSHIP_EXPIRED',
            });
        }
        next();
    };
};
exports.requireMembership = requireMembership;
const requireEmailVerification = (req, res, next) => {
    if (!req.user) {
        return res.status(401).json({
            success: false,
            code: 401,
            message: '需要登录',
            error_code: 'AUTHENTICATION_REQUIRED',
        });
    }
    database_1.prisma.user.findUnique({
        where: { id: Number(req.user.id) },
        select: { emailVerified: true },
    }).then(user => {
        if (!user?.emailVerified) {
            return res.status(403).json({
                success: false,
                code: 403,
                message: '需要验证邮箱',
                error_code: 'EMAIL_VERIFICATION_REQUIRED',
            });
        }
        next();
    }).catch(error => {
        logger_1.logger.error('Email verification check error:', error);
        return res.status(500).json({
            success: false,
            code: 500,
            message: '服务错误',
            error_code: 'SERVICE_ERROR',
        });
    });
};
exports.requireEmailVerification = requireEmailVerification;
const requireAdmin = (req, res, next) => {
    if (!req.user) {
        return res.status(401).json({
            success: false,
            code: 401,
            message: '需要登录',
            error_code: 'AUTHENTICATION_REQUIRED',
        });
    }
    if (req.user.email !== process.env.ADMIN_EMAIL) {
        return res.status(403).json({
            success: false,
            code: 403,
            message: '需要管理员权限',
            error_code: 'ADMIN_REQUIRED',
        });
    }
    next();
};
exports.requireAdmin = requireAdmin;
//# sourceMappingURL=auth.js.map