import { Request, Response, NextFunction } from 'express';
import { verifyAccessToken, JwtPayload } from '@/utils/jwt';
import { prisma } from '@/config/database';
import { redis } from '@/config/redis';
import { logger } from '@/utils/logger';

// 扩展Request接口
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        email: string;
        username: string;
        membershipLevel: string;
        membershipExpiresAt?: Date;
        isActive: boolean;
      };
      token?: string;
    }
  }
}

/**
 * JWT认证中间件
 */
export const authenticateToken = async (req: Request, res: Response, next: NextFunction) => {
  try {
    const authHeader = req.headers.authorization;
    const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

    if (!token) {
      return res.status(401).json({
        success: false,
        code: 401,
        message: '访问令牌缺失',
        error_code: 'MISSING_TOKEN',
      });
    }

    // 验证JWT令牌
    let decoded: JwtPayload;
    try {
      decoded = verifyAccessToken(token);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Token verification failed';
      
      return res.status(401).json({
        success: false,
        code: 401,
        message: '访问令牌无效或已过期',
        error_code: errorMessage.includes('expired') ? 'TOKEN_EXPIRED' : 'INVALID_TOKEN',
      });
    }

    // 检查令牌是否在Redis黑名单中
    const isBlacklisted = await redis.exists(`blacklist:token:${token}`);
    if (isBlacklisted) {
      return res.status(401).json({
        success: false,
        code: 401,
        message: '令牌已失效',
        error_code: 'TOKEN_BLACKLISTED',
      });
    }

    // 从数据库获取用户信息
    const user = await prisma.user.findUnique({
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

    // 将用户信息附加到请求对象
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
  } catch (error) {
    logger.error('Authentication middleware error:', error);
    return res.status(500).json({
      success: false,
      code: 500,
      message: '认证服务错误',
      error_code: 'AUTH_SERVICE_ERROR',
    });
  }
};

/**
 * 可选认证中间件（不强制要求登录）
 */
export const optionalAuth = async (req: Request, res: Response, next: NextFunction) => {
  try {
    const authHeader = req.headers.authorization;
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
      return next(); // 没有令牌，继续执行
    }

    // 尝试验证令牌
    try {
      const decoded = verifyAccessToken(token);
      
      // 检查黑名单
      const isBlacklisted = await redis.exists(`blacklist:token:${token}`);
      if (!isBlacklisted) {
        // 获取用户信息
        const user = await prisma.user.findUnique({
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
    } catch (error) {
      // 令牌无效，忽略错误继续执行
      logger.debug('Optional auth token verification failed:', error);
    }

    next();
  } catch (error) {
    logger.error('Optional auth middleware error:', error);
    next(); // 出错时继续执行
  }
};

/**
 * 会员等级检查中间件
 */
export const requireMembership = (requiredLevel: 'BASIC' | 'PREMIUM' | 'PROFESSIONAL') => {
  return (req: Request, res: Response, next: NextFunction) => {
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

    const userLevel = membershipLevels[req.user.membershipLevel as keyof typeof membershipLevels] || 0;
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

    // 检查会员是否过期
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

/**
 * 邮箱验证检查中间件
 */
export const requireEmailVerification = (req: Request, res: Response, next: NextFunction) => {
  if (!req.user) {
    return res.status(401).json({
      success: false,
      code: 401,
      message: '需要登录',
      error_code: 'AUTHENTICATION_REQUIRED',
    });
  }

  // 这里我们需要查询数据库获取邮箱验证状态
  // 为了简化，假设用户对象包含此信息
  prisma.user.findUnique({
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
    logger.error('Email verification check error:', error);
    return res.status(500).json({
      success: false,
      code: 500,
      message: '服务错误',
      error_code: 'SERVICE_ERROR',
    });
  });
};

/**
 * 管理员权限检查中间件
 */
export const requireAdmin = (req: Request, res: Response, next: NextFunction) => {
  if (!req.user) {
    return res.status(401).json({
      success: false,
      code: 401,
      message: '需要登录',
      error_code: 'AUTHENTICATION_REQUIRED',
    });
  }

  // 检查是否为管理员（这里可以根据实际需求实现）
  // 比如检查用户角色或者特定的管理员标识
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