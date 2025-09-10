"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.assertExists = exports.assertPermission = exports.assert = exports.logError = exports.asyncHandler = exports.globalErrorHandler = exports.notFoundHandler = exports.handleUnhandledRejection = exports.handleUncaughtException = exports.ConflictError = exports.ValidationError = exports.NotFoundError = exports.AuthorizationError = exports.AuthenticationError = exports.BusinessError = exports.AppError = void 0;
const library_1 = require("@prisma/client/runtime/library");
const logger_1 = require("../utils/logger");
class AppError extends Error {
    constructor(message, statusCode = 500, errorCode = 'INTERNAL_ERROR', isOperational = true) {
        super(message);
        this.statusCode = statusCode;
        this.errorCode = errorCode;
        this.isOperational = isOperational;
        Error.captureStackTrace(this, this.constructor);
    }
}
exports.AppError = AppError;
class BusinessError extends AppError {
    constructor(message, errorCode = 'BUSINESS_ERROR') {
        super(message, 400, errorCode);
    }
}
exports.BusinessError = BusinessError;
class AuthenticationError extends AppError {
    constructor(message = '认证失败', errorCode = 'AUTHENTICATION_FAILED') {
        super(message, 401, errorCode);
    }
}
exports.AuthenticationError = AuthenticationError;
class AuthorizationError extends AppError {
    constructor(message = '权限不足', errorCode = 'AUTHORIZATION_FAILED') {
        super(message, 403, errorCode);
    }
}
exports.AuthorizationError = AuthorizationError;
class NotFoundError extends AppError {
    constructor(resource = '资源') {
        super(`${resource}未找到`, 404, 'RESOURCE_NOT_FOUND');
    }
}
exports.NotFoundError = NotFoundError;
class ValidationError extends AppError {
    constructor(errors) {
        super('数据验证失败', 422, 'VALIDATION_ERROR');
        this.errors = errors;
    }
}
exports.ValidationError = ValidationError;
class ConflictError extends AppError {
    constructor(message = '资源冲突', errorCode = 'RESOURCE_CONFLICT') {
        super(message, 409, errorCode);
    }
}
exports.ConflictError = ConflictError;
const handlePrismaError = (error) => {
    logger_1.logger.error('Prisma error:', error);
    switch (error.code) {
        case 'P2002':
            const field = error.meta?.target || [];
            const fieldName = field[0] || 'field';
            if (fieldName === 'email') {
                return new ConflictError('该邮箱已被注册', 'DUPLICATE_EMAIL');
            }
            else if (fieldName === 'username') {
                return new ConflictError('该用户名已被使用', 'DUPLICATE_USERNAME');
            }
            return new ConflictError(`${fieldName}已存在`, 'DUPLICATE_FIELD');
        case 'P2025':
            return new NotFoundError();
        case 'P2003':
            return new BusinessError('关联数据不存在', 'FOREIGN_KEY_CONSTRAINT');
        case 'P2014':
            return new BusinessError('无效的ID', 'INVALID_ID');
        case 'P2021':
            return new AppError('数据库配置错误', 500, 'DATABASE_CONFIG_ERROR');
        case 'P2024':
            return new AppError('数据库连接超时', 500, 'DATABASE_TIMEOUT');
        default:
            logger_1.logger.error('Unhandled Prisma error:', { code: error.code, message: error.message });
            return new AppError('数据库操作失败', 500, 'DATABASE_ERROR');
    }
};
const handleJWTError = (error) => {
    if (error.name === 'JsonWebTokenError') {
        return new AuthenticationError('无效的访问令牌', 'INVALID_TOKEN');
    }
    else if (error.name === 'TokenExpiredError') {
        return new AuthenticationError('访问令牌已过期', 'TOKEN_EXPIRED');
    }
    else if (error.name === 'NotBeforeError') {
        return new AuthenticationError('访问令牌尚未生效', 'TOKEN_NOT_ACTIVE');
    }
    return new AuthenticationError('令牌验证失败', 'TOKEN_VERIFICATION_FAILED');
};
const handleUncaughtException = (error) => {
    logger_1.logger.error('Uncaught Exception:', error);
    process.exit(1);
};
exports.handleUncaughtException = handleUncaughtException;
const handleUnhandledRejection = (reason) => {
    logger_1.logger.error('Unhandled Rejection:', reason);
    process.exit(1);
};
exports.handleUnhandledRejection = handleUnhandledRejection;
const notFoundHandler = (req, res, next) => {
    const error = new NotFoundError(`路径 ${req.originalUrl} 不存在`);
    next(error);
};
exports.notFoundHandler = notFoundHandler;
const globalErrorHandler = (error, req, res, next) => {
    let appError;
    if (error instanceof AppError) {
        appError = error;
    }
    else if (error instanceof library_1.PrismaClientKnownRequestError) {
        appError = handlePrismaError(error);
    }
    else if (error.name?.includes('JWT')) {
        appError = handleJWTError(error);
    }
    else if (error.name === 'ValidationError') {
        appError = new ValidationError([{
                field: 'general',
                code: 'VALIDATION_ERROR',
                message: error.message,
            }]);
    }
    else {
        logger_1.logger.error('Unhandled error:', {
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
        appError = new AppError(process.env.NODE_ENV === 'production' ? '服务器内部错误' : error.message, 500, 'INTERNAL_SERVER_ERROR');
    }
    if (appError.statusCode >= 500) {
        logger_1.logger.error('Server error:', {
            error: appError.message,
            errorCode: appError.errorCode,
            statusCode: appError.statusCode,
            stack: appError.stack,
            path: req.path,
            method: req.method,
            user: req.user,
        });
    }
    else {
        logger_1.logger.warn('Client error:', {
            error: appError.message,
            errorCode: appError.errorCode,
            statusCode: appError.statusCode,
            path: req.path,
            method: req.method,
            user: req.user,
        });
    }
    const response = {
        success: false,
        code: appError.statusCode,
        message: appError.message,
        error_code: appError.errorCode,
        timestamp: new Date().toISOString(),
        request_id: req.headers['x-request-id'],
    };
    if (appError instanceof ValidationError) {
        response.errors = appError.errors;
    }
    if (process.env.NODE_ENV === 'development' && appError.stack) {
        response.stack = appError.stack;
    }
    res.status(appError.statusCode).json(response);
};
exports.globalErrorHandler = globalErrorHandler;
const asyncHandler = (fn) => {
    return (req, res, next) => {
        Promise.resolve(fn(req, res, next)).catch(next);
    };
};
exports.asyncHandler = asyncHandler;
const logError = (error, context) => {
    logger_1.logger.error('Application error:', {
        name: error.name,
        message: error.message,
        stack: error.stack,
        context,
    });
};
exports.logError = logError;
const assert = (condition, message, errorCode) => {
    if (!condition) {
        throw new BusinessError(message, errorCode);
    }
};
exports.assert = assert;
const assertPermission = (condition, message) => {
    if (!condition) {
        throw new AuthorizationError(message);
    }
};
exports.assertPermission = assertPermission;
const assertExists = (resource, name = '资源') => {
    if (!resource) {
        throw new NotFoundError(name);
    }
    return resource;
};
exports.assertExists = assertExists;
//# sourceMappingURL=errorHandler.js.map