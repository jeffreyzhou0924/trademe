import { Request, Response, NextFunction } from 'express';
import { PrismaClientKnownRequestError } from '@prisma/client/runtime/library';
import { logger } from '@/utils/logger';

// 自定义错误类
export class AppError extends Error {
  public readonly statusCode: number;
  public readonly errorCode: string;
  public readonly isOperational: boolean;

  constructor(message: string, statusCode: number = 500, errorCode: string = 'INTERNAL_ERROR', isOperational: boolean = true) {
    super(message);
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.isOperational = isOperational;

    Error.captureStackTrace(this, this.constructor);
  }
}

// 业务错误类
export class BusinessError extends AppError {
  constructor(message: string, errorCode: string = 'BUSINESS_ERROR') {
    super(message, 400, errorCode);
  }
}

// 认证错误类
export class AuthenticationError extends AppError {
  constructor(message: string = '认证失败', errorCode: string = 'AUTHENTICATION_FAILED') {
    super(message, 401, errorCode);
  }
}

// 权限错误类
export class AuthorizationError extends AppError {
  constructor(message: string = '权限不足', errorCode: string = 'AUTHORIZATION_FAILED') {
    super(message, 403, errorCode);
  }
}

// 资源未找到错误类
export class NotFoundError extends AppError {
  constructor(resource: string = '资源') {
    super(`${resource}未找到`, 404, 'RESOURCE_NOT_FOUND');
  }
}

// 验证错误类
export class ValidationError extends AppError {
  public readonly errors: Array<{
    field: string;
    code: string;
    message: string;
  }>;

  constructor(errors: Array<{ field: string; code: string; message: string }>) {
    super('数据验证失败', 422, 'VALIDATION_ERROR');
    this.errors = errors;
  }
}

// 冲突错误类
export class ConflictError extends AppError {
  constructor(message: string = '资源冲突', errorCode: string = 'RESOURCE_CONFLICT') {
    super(message, 409, errorCode);
  }
}

/**
 * Prisma错误处理
 */
const handlePrismaError = (error: PrismaClientKnownRequestError): AppError => {
  logger.error('Prisma error:', error);

  switch (error.code) {
    case 'P2002': // 唯一约束违反
      const field = error.meta?.target as string[] || [];
      const fieldName = field[0] || 'field';
      
      if (fieldName === 'email') {
        return new ConflictError('该邮箱已被注册', 'DUPLICATE_EMAIL');
      } else if (fieldName === 'username') {
        return new ConflictError('该用户名已被使用', 'DUPLICATE_USERNAME');
      }
      
      return new ConflictError(`${fieldName}已存在`, 'DUPLICATE_FIELD');

    case 'P2025': // 记录未找到
      return new NotFoundError();

    case 'P2003': // 外键约束失败
      return new BusinessError('关联数据不存在', 'FOREIGN_KEY_CONSTRAINT');

    case 'P2014': // ID无效
      return new BusinessError('无效的ID', 'INVALID_ID');

    case 'P2021': // 表不存在
      return new AppError('数据库配置错误', 500, 'DATABASE_CONFIG_ERROR');

    case 'P2024': // 连接超时
      return new AppError('数据库连接超时', 500, 'DATABASE_TIMEOUT');

    default:
      logger.error('Unhandled Prisma error:', { code: error.code, message: error.message });
      return new AppError('数据库操作失败', 500, 'DATABASE_ERROR');
  }
};

/**
 * JSON Web Token错误处理
 */
const handleJWTError = (error: Error): AppError => {
  if (error.name === 'JsonWebTokenError') {
    return new AuthenticationError('无效的访问令牌', 'INVALID_TOKEN');
  } else if (error.name === 'TokenExpiredError') {
    return new AuthenticationError('访问令牌已过期', 'TOKEN_EXPIRED');
  } else if (error.name === 'NotBeforeError') {
    return new AuthenticationError('访问令牌尚未生效', 'TOKEN_NOT_ACTIVE');
  }

  return new AuthenticationError('令牌验证失败', 'TOKEN_VERIFICATION_FAILED');
};

/**
 * 未捕获异常处理
 */
export const handleUncaughtException = (error: Error): void => {
  logger.error('Uncaught Exception:', error);
  
  // 优雅关闭应用
  process.exit(1);
};

/**
 * 未处理的Promise拒绝
 */
export const handleUnhandledRejection = (reason: any): void => {
  logger.error('Unhandled Rejection:', reason);
  
  // 优雅关闭应用
  process.exit(1);
};

/**
 * 404错误处理中间件
 */
export const notFoundHandler = (req: Request, res: Response, next: NextFunction): void => {
  const error = new NotFoundError(`路径 ${req.originalUrl} 不存在`);
  next(error);
};

/**
 * 全局错误处理中间件
 */
export const globalErrorHandler = (
  error: Error,
  req: Request,
  res: Response,
  next: NextFunction
): void => {
  let appError: AppError;

  // 根据错误类型进行处理
  if (error instanceof AppError) {
    appError = error;
  } else if (error instanceof PrismaClientKnownRequestError) {
    appError = handlePrismaError(error);
  } else if (error.name?.includes('JWT')) {
    appError = handleJWTError(error);
  } else if (error.name === 'ValidationError') {
    appError = new ValidationError([{
      field: 'general',
      code: 'VALIDATION_ERROR',
      message: error.message,
    }]);
  } else {
    // 未知错误
    logger.error('Unhandled error:', {
      name: error.name,
      message: error.message,
      stack: error.stack,
      path: req.path,
      method: req.method,
      body: req.body,
      query: req.query,
      params: req.params,
      headers: req.headers,
      user: req.user,
    });

    appError = new AppError(
      process.env.NODE_ENV === 'production' ? '服务器内部错误' : error.message,
      500,
      'INTERNAL_SERVER_ERROR'
    );
  }

  // 记录错误日志
  if (appError.statusCode >= 500) {
    logger.error('Server error:', {
      error: appError.message,
      errorCode: appError.errorCode,
      statusCode: appError.statusCode,
      stack: appError.stack,
      path: req.path,
      method: req.method,
      user: req.user,
    });
  } else {
    logger.warn('Client error:', {
      error: appError.message,
      errorCode: appError.errorCode,
      statusCode: appError.statusCode,
      path: req.path,
      method: req.method,
      user: req.user,
    });
  }

  // 构造响应
  const response: any = {
    success: false,
    code: appError.statusCode,
    message: appError.message,
    error_code: appError.errorCode,
    timestamp: new Date().toISOString(),
    request_id: req.headers['x-request-id'],
  };

  // 添加验证错误详情
  if (appError instanceof ValidationError) {
    response.errors = appError.errors;
  }

  // 开发环境添加堆栈信息
  if (process.env.NODE_ENV === 'development' && appError.stack) {
    response.stack = appError.stack;
  }

  res.status(appError.statusCode).json(response);
};

/**
 * 异步错误包装器
 */
export const asyncHandler = (fn: Function) => {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
};

/**
 * 错误日志记录辅助函数
 */
export const logError = (error: Error, context?: any): void => {
  logger.error('Application error:', {
    name: error.name,
    message: error.message,
    stack: error.stack,
    context,
  });
};

/**
 * 业务断言函数
 */
export const assert = (condition: boolean, message: string, errorCode?: string): void => {
  if (!condition) {
    throw new BusinessError(message, errorCode);
  }
};

/**
 * 权限断言函数
 */
export const assertPermission = (condition: boolean, message?: string): void => {
  if (!condition) {
    throw new AuthorizationError(message);
  }
};

/**
 * 资源存在断言函数
 */
export const assertExists = <T>(resource: T | null | undefined, name: string = '资源'): T => {
  if (!resource) {
    throw new NotFoundError(name);
  }
  return resource;
};