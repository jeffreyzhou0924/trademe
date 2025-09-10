"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.clearUserRateLimit = exports.getRateLimitStatus = exports.fileUploadRateLimit = exports.apiCallRateLimit = exports.userBasedRateLimit = exports.passwordResetRateLimit = exports.verificationCodeRateLimit = exports.authRateLimit = exports.globalRateLimit = exports.createRateLimit = void 0;
const redis_1 = require("../config/redis");
const logger_1 = require("../utils/logger");
const createRateLimit = (options) => {
    const { windowMs, maxRequests, message = '请求过于频繁，请稍后再试', keyGenerator = (req) => req.ip || 'unknown', skipSuccessfulRequests = false, skipFailedRequests = false, } = options;
    const windowSeconds = Math.ceil(windowMs / 1000);
    return async (req, res, next) => {
        try {
            const key = `rate_limit:${keyGenerator(req)}`;
            const current = await redis_1.redis.incr(key);
            if (current === 1) {
                await redis_1.redis.expire(key, windowSeconds);
            }
            const ttl = await redis_1.redis.getClient().ttl(key);
            const resetTime = new Date(Date.now() + (ttl * 1000));
            res.set({
                'X-RateLimit-Limit': maxRequests.toString(),
                'X-RateLimit-Remaining': Math.max(0, maxRequests - current).toString(),
                'X-RateLimit-Reset': resetTime.toISOString(),
            });
            if (current > maxRequests) {
                logger_1.logger.warn('Rate limit exceeded', {
                    key,
                    current,
                    limit: maxRequests,
                    ip: req.ip,
                    path: req.path,
                    userAgent: req.get('User-Agent'),
                });
                return res.status(429).json({
                    success: false,
                    code: 429,
                    message,
                    error_code: 'RATE_LIMIT_EXCEEDED',
                    retry_after: ttl,
                    timestamp: new Date().toISOString(),
                });
            }
            const originalJson = res.json;
            res.json = function (body) {
                const shouldSkip = (skipSuccessfulRequests && res.statusCode < 400) ||
                    (skipFailedRequests && res.statusCode >= 400);
                if (shouldSkip) {
                    redis_1.redis.decr(key).catch((err) => {
                        logger_1.logger.error('Failed to decrement rate limit counter:', err);
                    });
                }
                return originalJson.call(this, body);
            };
            next();
        }
        catch (error) {
            logger_1.logger.error('Rate limit middleware error:', error);
            next();
        }
    };
};
exports.createRateLimit = createRateLimit;
exports.globalRateLimit = (0, exports.createRateLimit)({
    windowMs: 15 * 60 * 1000,
    maxRequests: 100,
    message: '请求过于频繁，请稍后再试',
});
exports.authRateLimit = (0, exports.createRateLimit)({
    windowMs: 15 * 60 * 1000,
    maxRequests: 10,
    message: '登录尝试次数过多，请稍后再试',
    keyGenerator: (req) => `auth:${req.ip}`,
});
exports.verificationCodeRateLimit = (0, exports.createRateLimit)({
    windowMs: 60 * 1000,
    maxRequests: 1,
    message: '验证码发送过于频繁，请稍后再试',
    keyGenerator: (req) => `verification:${req.body.email || req.ip}`,
});
exports.passwordResetRateLimit = (0, exports.createRateLimit)({
    windowMs: 60 * 60 * 1000,
    maxRequests: 5,
    message: '密码重置次数过多，请稍后再试',
    keyGenerator: (req) => `password_reset:${req.body.email || req.ip}`,
});
const userBasedRateLimit = (options) => {
    return (0, exports.createRateLimit)({
        ...options,
        keyGenerator: (req) => {
            if (req.user?.id) {
                return `user:${req.user.id}`;
            }
            return `ip:${req.ip}`;
        },
    });
};
exports.userBasedRateLimit = userBasedRateLimit;
const apiCallRateLimit = async (req, res, next) => {
    try {
        if (!req.user) {
            return next();
        }
        const limits = {
            BASIC: { windowMs: 60 * 60 * 1000, maxRequests: 100 },
            PREMIUM: { windowMs: 60 * 60 * 1000, maxRequests: 500 },
            PROFESSIONAL: { windowMs: 60 * 60 * 1000, maxRequests: 1000 },
        };
        const userLevel = req.user.membershipLevel;
        const limit = limits[userLevel] || limits.BASIC;
        const rateLimit = (0, exports.createRateLimit)({
            ...limit,
            message: 'API调用次数已达上限，请升级会员或稍后再试',
            keyGenerator: (req) => `api_calls:${req.user.id}`,
        });
        return rateLimit(req, res, next);
    }
    catch (error) {
        logger_1.logger.error('API call rate limit error:', error);
        next();
    }
};
exports.apiCallRateLimit = apiCallRateLimit;
exports.fileUploadRateLimit = (0, exports.createRateLimit)({
    windowMs: 60 * 60 * 1000,
    maxRequests: 10,
    message: '文件上传次数过多，请稍后再试',
    keyGenerator: (req) => `file_upload:${req.user?.id || req.ip}`,
});
const getRateLimitStatus = async (key) => {
    try {
        const current = await redis_1.redis.get(key);
        const ttl = await redis_1.redis.getClient().ttl(key);
        const currentCount = current ? parseInt(current) : 0;
        const resetTime = new Date(Date.now() + (ttl * 1000));
        return {
            current: currentCount,
            remaining: Math.max(0, 100 - currentCount),
            resetTime,
        };
    }
    catch (error) {
        logger_1.logger.error('Get rate limit status error:', error);
        return {
            current: 0,
            remaining: 100,
            resetTime: new Date(),
        };
    }
};
exports.getRateLimitStatus = getRateLimitStatus;
const clearUserRateLimit = async (userId) => {
    try {
        const keys = [
            `rate_limit:user:${userId}`,
            `api_calls:${userId}`,
            `file_upload:${userId}`,
        ];
        await Promise.all(keys.map(key => redis_1.redis.del(key)));
        logger_1.logger.info(`Cleared rate limit for user ${userId}`);
    }
    catch (error) {
        logger_1.logger.error('Clear user rate limit error:', error);
        throw error;
    }
};
exports.clearUserRateLimit = clearUserRateLimit;
//# sourceMappingURL=rateLimit.js.map