import { Request, Response, NextFunction } from 'express';
import { redis } from '@/config/redis';
import { logger } from '@/utils/logger';

interface RateLimitOptions {
  windowMs: number; // 时间窗口（毫秒）
  maxRequests: number; // 最大请求次数
  message?: string; // 限流消息
  keyGenerator?: (req: Request) => string; // 自定义key生成函数
  skipSuccessfulRequests?: boolean; // 是否跳过成功请求
  skipFailedRequests?: boolean; // 是否跳过失败请求
}

/**
 * 通用限流中间件工厂
 */
export const createRateLimit = (options: RateLimitOptions) => {
  const {
    windowMs,
    maxRequests,
    message = '请求过于频繁，请稍后再试',
    keyGenerator = (req) => req.ip || 'unknown',
    skipSuccessfulRequests = false,
    skipFailedRequests = false,
  } = options;

  const windowSeconds = Math.ceil(windowMs / 1000);

  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const key = `rate_limit:${keyGenerator(req)}`;
      
      // 获取当前计数
      const current = await redis.incr(key);
      
      // 如果是第一次请求，设置过期时间
      if (current === 1) {
        await redis.expire(key, windowSeconds);
      }

      // 获取剩余时间
      const ttl = await redis.getClient().ttl(key);
      const resetTime = new Date(Date.now() + (ttl * 1000));

      // 设置响应头
      res.set({
        'X-RateLimit-Limit': maxRequests.toString(),
        'X-RateLimit-Remaining': Math.max(0, maxRequests - current).toString(),
        'X-RateLimit-Reset': resetTime.toISOString(),
      });

      // 检查是否超出限制
      if (current > maxRequests) {
        logger.warn('Rate limit exceeded', {
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

      // 包装res.json方法来处理成功/失败请求跳过
      const originalJson = res.json;
      res.json = function(body: any) {
        const shouldSkip = 
          (skipSuccessfulRequests && res.statusCode < 400) ||
          (skipFailedRequests && res.statusCode >= 400);

        if (shouldSkip) {
          // 如果需要跳过，减少计数
          redis.decr(key).catch((err: Error) => {
            logger.error('Failed to decrement rate limit counter:', err);
          });
        }

        return originalJson.call(this, body);
      };

      next();
    } catch (error) {
      logger.error('Rate limit middleware error:', error);
      // 限流出错时不阻塞请求
      next();
    }
  };
};

/**
 * 全局API限流
 */
export const globalRateLimit = createRateLimit({
  windowMs: 15 * 60 * 1000, // 15分钟
  maxRequests: 100, // 每15分钟最多100次请求
  message: '请求过于频繁，请稍后再试',
});

/**
 * 认证相关接口限流
 */
export const authRateLimit = createRateLimit({
  windowMs: 15 * 60 * 1000, // 15分钟
  maxRequests: 10, // 每15分钟最多10次认证请求
  message: '登录尝试次数过多，请稍后再试',
  keyGenerator: (req) => `auth:${req.ip}`,
});

/**
 * 验证码发送限流
 */
export const verificationCodeRateLimit = createRateLimit({
  windowMs: 60 * 1000, // 1分钟
  maxRequests: 1, // 每分钟最多1次验证码发送
  message: '验证码发送过于频繁，请稍后再试',
  keyGenerator: (req) => `verification:${req.body.email || req.ip}`,
});

/**
 * 密码重置限流
 */
export const passwordResetRateLimit = createRateLimit({
  windowMs: 60 * 60 * 1000, // 1小时
  maxRequests: 5, // 每小时最多5次密码重置
  message: '密码重置次数过多，请稍后再试',
  keyGenerator: (req) => `password_reset:${req.body.email || req.ip}`,
});

/**
 * 基于用户的限流
 */
export const userBasedRateLimit = (options: Omit<RateLimitOptions, 'keyGenerator'>) => {
  return createRateLimit({
    ...options,
    keyGenerator: (req) => {
      if (req.user?.id) {
        return `user:${req.user.id}`;
      }
      return `ip:${req.ip}`;
    },
  });
};

/**
 * API调用限流（基于用户会员等级）
 */
export const apiCallRateLimit = async (req: Request, res: Response, next: NextFunction) => {
  try {
    if (!req.user) {
      return next();
    }

    // 根据会员等级设置不同的限制
    const limits = {
      BASIC: { windowMs: 60 * 60 * 1000, maxRequests: 100 }, // 1小时100次
      PREMIUM: { windowMs: 60 * 60 * 1000, maxRequests: 500 }, // 1小时500次
      PROFESSIONAL: { windowMs: 60 * 60 * 1000, maxRequests: 1000 }, // 1小时1000次
    };

    const userLevel = req.user.membershipLevel as keyof typeof limits;
    const limit = limits[userLevel] || limits.BASIC;

    const rateLimit = createRateLimit({
      ...limit,
      message: 'API调用次数已达上限，请升级会员或稍后再试',
      keyGenerator: (req) => `api_calls:${req.user!.id}`,
    });

    return rateLimit(req, res, next);
  } catch (error) {
    logger.error('API call rate limit error:', error);
    next();
  }
};

/**
 * 文件上传限流
 */
export const fileUploadRateLimit = createRateLimit({
  windowMs: 60 * 60 * 1000, // 1小时
  maxRequests: 10, // 每小时最多10次文件上传
  message: '文件上传次数过多，请稍后再试',
  keyGenerator: (req) => `file_upload:${req.user?.id || req.ip}`,
});

/**
 * 获取限流状态
 */
export const getRateLimitStatus = async (key: string): Promise<{
  current: number;
  remaining: number;
  resetTime: Date;
}> => {
  try {
    const current = await redis.get(key);
    const ttl = await redis.getClient().ttl(key);
    
    const currentCount = current ? parseInt(current) : 0;
    const resetTime = new Date(Date.now() + (ttl * 1000));
    
    return {
      current: currentCount,
      remaining: Math.max(0, 100 - currentCount), // 默认限制100
      resetTime,
    };
  } catch (error) {
    logger.error('Get rate limit status error:', error);
    return {
      current: 0,
      remaining: 100,
      resetTime: new Date(),
    };
  }
};

/**
 * 清除用户限流计数
 */
export const clearUserRateLimit = async (userId: string): Promise<void> => {
  try {
    const keys = [
      `rate_limit:user:${userId}`,
      `api_calls:${userId}`,
      `file_upload:${userId}`,
    ];

    await Promise.all(keys.map(key => redis.del(key)));
    
    logger.info(`Cleared rate limit for user ${userId}`);
  } catch (error) {
    logger.error('Clear user rate limit error:', error);
    throw error;
  }
};