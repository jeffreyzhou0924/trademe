"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.securityHeaders = exports.corsHandler = exports.requestLogger = exports.generateRequestId = exports.validateFileUpload = exports.validateParams = exports.validateQuery = exports.validateBody = void 0;
const logger_1 = require("../utils/logger");
const validateBody = (schema) => {
    return (req, res, next) => {
        const { error, value } = schema.validate(req.body, {
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
            logger_1.logger.warn('Request body validation failed:', {
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
        req.body = value;
        next();
    };
};
exports.validateBody = validateBody;
const validateQuery = (schema) => {
    return (req, res, next) => {
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
            logger_1.logger.warn('Query parameters validation failed:', {
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
exports.validateQuery = validateQuery;
const validateParams = (schema) => {
    return (req, res, next) => {
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
            logger_1.logger.warn('URL parameters validation failed:', {
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
exports.validateParams = validateParams;
const validateFileUpload = (options = {}) => {
    const { maxSize = 5 * 1024 * 1024, allowedTypes = ['image/jpeg', 'image/png', 'image/gif'], required = true, } = options;
    return (req, res, next) => {
        const file = req.file;
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
exports.validateFileUpload = validateFileUpload;
const generateRequestId = (req, res, next) => {
    const requestId = req.headers['x-request-id'] ||
        `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    req.headers['x-request-id'] = requestId;
    res.set('X-Request-ID', requestId);
    next();
};
exports.generateRequestId = generateRequestId;
const requestLogger = (req, res, next) => {
    const startTime = Date.now();
    logger_1.logger.info('Request started', {
        method: req.method,
        path: req.path,
        query: req.query,
        ip: req.ip,
        userAgent: req.get('User-Agent'),
        requestId: req.headers['x-request-id'],
        userId: req.user?.id,
    });
    const originalJson = res.json;
    res.json = function (body) {
        const responseTime = Date.now() - startTime;
        logger_1.logger.info('Request completed', {
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
exports.requestLogger = requestLogger;
const corsHandler = (req, res, next) => {
    const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'];
    const origin = req.headers.origin;
    if (origin && allowedOrigins.includes(origin)) {
        res.header('Access-Control-Allow-Origin', origin);
    }
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-Request-ID');
    res.header('Access-Control-Allow-Credentials', 'true');
    if (req.method === 'OPTIONS') {
        return res.status(204).send();
    }
    next();
};
exports.corsHandler = corsHandler;
const securityHeaders = (req, res, next) => {
    res.header('X-XSS-Protection', '1; mode=block');
    res.header('X-Content-Type-Options', 'nosniff');
    res.header('X-Frame-Options', 'DENY');
    if (req.secure || req.headers['x-forwarded-proto'] === 'https') {
        res.header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    }
    res.header('Content-Security-Policy', "default-src 'self'");
    res.header('Referrer-Policy', 'strict-origin-when-cross-origin');
    next();
};
exports.securityHeaders = securityHeaders;
//# sourceMappingURL=validation.js.map