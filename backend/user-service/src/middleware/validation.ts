import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import { logger } from '@/utils/logger';

/**
 * 请求体验证中间件工厂
 */
export const validateBody = (schema: Joi.ObjectSchema) => {
  return (req: Request, res: Response, next: NextFunction) => {
    const { error, value } = schema.validate(req.body, {
      abortEarly: false, // 收集所有验证错误
      stripUnknown: true, // 移除未知字段
      convert: true, // 类型转换
    });

    if (error) {
      const errors = error.details.map(detail => ({
        field: detail.path.join('.'),
        code: detail.type.toUpperCase().replace(/\./g, '_'),
        message: detail.message,
      }));

      logger.warn('Request body validation failed:', {
        path: req.path,
        method: req.method,
        errors,
        body: req.body,
      });

      return res.status(422).json({
        success: false,
        code: 422,
        message: '请求参数验证失败',
        errors,
        timestamp: new Date().toISOString(),
        request_id: req.headers['x-request-id'],
      });
    }

    // 将验证后的值替换原始请求体
    req.body = value;
    next();
  };
};

/**
 * 查询参数验证中间件工厂
 */
export const validateQuery = (schema: Joi.ObjectSchema) => {
  return (req: Request, res: Response, next: NextFunction) => {
    const { error, value } = schema.validate(req.query, {
      abortEarly: false,
      stripUnknown: true,
      convert: true,
    });

    if (error) {
      const errors = error.details.map(detail => ({
        field: detail.path.join('.'),
        code: detail.type.toUpperCase().replace(/\./g, '_'),
        message: detail.message,
      }));

      logger.warn('Query parameters validation failed:', {
        path: req.path,
        method: req.method,
        errors,
        query: req.query,
      });

      return res.status(422).json({
        success: false,
        code: 422,
        message: '查询参数验证失败',
        errors,
        timestamp: new Date().toISOString(),
        request_id: req.headers['x-request-id'],
      });
    }

    req.query = value;
    next();
  };
};

/**
 * URL参数验证中间件工厂
 */
export const validateParams = (schema: Joi.ObjectSchema) => {
  return (req: Request, res: Response, next: NextFunction) => {
    const { error, value } = schema.validate(req.params, {
      abortEarly: false,
      stripUnknown: true,
      convert: true,
    });

    if (error) {
      const errors = error.details.map(detail => ({
        field: detail.path.join('.'),
        code: detail.type.toUpperCase().replace(/\./g, '_'),
        message: detail.message,
      }));

      logger.warn('URL parameters validation failed:', {
        path: req.path,
        method: req.method,
        errors,
        params: req.params,
      });

      return res.status(422).json({
        success: false,
        code: 422,
        message: 'URL参数验证失败',
        errors,
        timestamp: new Date().toISOString(),
        request_id: req.headers['x-request-id'],
      });
    }

    req.params = value;
    next();
  };
};

/**
 * 文件上传验证中间件
 */
export const validateFileUpload = (options: {
  maxSize?: number; // 最大文件大小（字节）
  allowedTypes?: string[]; // 允许的MIME类型
  required?: boolean; // 是否必须上传文件
} = {}) => {
  const {
    maxSize = 5 * 1024 * 1024, // 5MB
    allowedTypes = ['image/jpeg', 'image/png', 'image/gif'],
    required = true,
  } = options;

  return (req: Request, res: Response, next: NextFunction) => {
    const file = (req as any).file;

    // 检查文件是否存在
    if (!file) {
      if (required) {
        return res.status(422).json({
          success: false,
          code: 422,
          message: '文件上传失败',
          errors: [{
            field: 'file',
            code: 'REQUIRED',
            message: '必须上传文件',
          }],
        });
      }
      return next();
    }

    // 检查文件大小
    if (file.size > maxSize) {
      return res.status(422).json({
        success: false,
        code: 422,
        message: '文件过大',
        errors: [{
          field: 'file',
          code: 'FILE_TOO_LARGE',
          message: `文件大小不能超过 ${Math.round(maxSize / 1024 / 1024)}MB`,
        }],
      });
    }

    // 检查文件类型
    if (!allowedTypes.includes(file.mimetype)) {
      return res.status(422).json({
        success: false,
        code: 422,
        message: '文件类型不支持',
        errors: [{
          field: 'file',
          code: 'INVALID_FILE_TYPE',
          message: `只支持以下文件类型: ${allowedTypes.join(', ')}`,
        }],
      });
    }

    next();
  };
};

/**
 * 请求ID生成中间件
 */
export const generateRequestId = (req: Request, res: Response, next: NextFunction) => {
  const requestId = req.headers['x-request-id'] || 
    `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
  
  req.headers['x-request-id'] = requestId as string;
  res.set('X-Request-ID', requestId as string);
  
  next();
};

/**
 * 请求日志中间件
 */
export const requestLogger = (req: Request, res: Response, next: NextFunction) => {
  const startTime = Date.now();

  // 记录请求开始
  logger.info('Request started', {
    method: req.method,
    path: req.path,
    query: req.query,
    ip: req.ip,
    userAgent: req.get('User-Agent'),
    requestId: req.headers['x-request-id'],
    userId: req.user?.id,
  });

  // 重写res.json方法来记录响应
  const originalJson = res.json;
  res.json = function(body) {
    const responseTime = Date.now() - startTime;
    
    logger.info('Request completed', {
      method: req.method,
      path: req.path,
      statusCode: res.statusCode,
      responseTime: `${responseTime}ms`,
      requestId: req.headers['x-request-id'],
      userId: req.user?.id,
    });

    return originalJson.call(this, body);
  };

  next();
};

/**
 * CORS中间件
 */
export const corsHandler = (req: Request, res: Response, next: NextFunction) => {
  const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'];
  const origin = req.headers.origin;

  if (origin && allowedOrigins.includes(origin)) {
    res.header('Access-Control-Allow-Origin', origin);
  }

  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-Request-ID');
  res.header('Access-Control-Allow-Credentials', 'true');

  // 处理预检请求
  if (req.method === 'OPTIONS') {
    return res.status(204).send();
  }

  next();
};

/**
 * 安全头部中间件
 */
export const securityHeaders = (req: Request, res: Response, next: NextFunction) => {
  // 防止XSS攻击
  res.header('X-XSS-Protection', '1; mode=block');
  
  // 防止MIME类型嗅探
  res.header('X-Content-Type-Options', 'nosniff');
  
  // 防止点击劫持
  res.header('X-Frame-Options', 'DENY');
  
  // 严格传输安全
  if (req.secure || req.headers['x-forwarded-proto'] === 'https') {
    res.header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
  
  // 内容安全策略
  res.header('Content-Security-Policy', "default-src 'self'");
  
  // 引用策略
  res.header('Referrer-Policy', 'strict-origin-when-cross-origin');

  next();
};