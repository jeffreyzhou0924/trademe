"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cleanupOnError = exports.validateImage = exports.documentUpload = exports.avatarUpload = void 0;
const upload_service_1 = require("../services/upload.service");
const logger_1 = require("../utils/logger");
const errorHandler_1 = require("./errorHandler");
const avatarUpload = (req, res, next) => {
    const config = upload_service_1.uploadService.createAvatarUploadConfig();
    const upload = upload_service_1.uploadService.createMulterMiddleware(config);
    upload.single('avatar')(req, res, (err) => {
        if (err) {
            logger_1.logger.error('Avatar upload error:', err);
            if (err.code === 'LIMIT_FILE_SIZE') {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: '文件大小超过限制 (5MB)',
                    error_code: 'FILE_TOO_LARGE',
                });
            }
            if (err.code === 'LIMIT_FILE_COUNT') {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: '只能上传一个文件',
                    error_code: 'TOO_MANY_FILES',
                });
            }
            if (err.code === 'LIMIT_UNEXPECTED_FILE') {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: '不支持的文件字段名',
                    error_code: 'INVALID_FIELD_NAME',
                });
            }
            if (err instanceof errorHandler_1.BusinessError) {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: err.message,
                    error_code: 'UPLOAD_ERROR',
                });
            }
            return res.status(400).json({
                success: false,
                code: 400,
                message: '文件上传失败',
                error_code: 'UPLOAD_FAILED',
            });
        }
        if (!req.file) {
            return res.status(400).json({
                success: false,
                code: 400,
                message: '请选择要上传的文件',
                error_code: 'NO_FILE_UPLOADED',
            });
        }
        logger_1.logger.info('Avatar upload successful:', {
            userId: req.user?.id,
            filename: req.file.filename,
            size: req.file.size,
            mimetype: req.file.mimetype,
        });
        next();
    });
};
exports.avatarUpload = avatarUpload;
const documentUpload = (req, res, next) => {
    const config = upload_service_1.uploadService.createDocumentUploadConfig();
    const upload = upload_service_1.uploadService.createMulterMiddleware(config);
    upload.single('document')(req, res, (err) => {
        if (err) {
            logger_1.logger.error('Document upload error:', err);
            if (err.code === 'LIMIT_FILE_SIZE') {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: '文件大小超过限制 (10MB)',
                    error_code: 'FILE_TOO_LARGE',
                });
            }
            if (err instanceof errorHandler_1.BusinessError) {
                return res.status(400).json({
                    success: false,
                    code: 400,
                    message: err.message,
                    error_code: 'UPLOAD_ERROR',
                });
            }
            return res.status(400).json({
                success: false,
                code: 400,
                message: '文档上传失败',
                error_code: 'UPLOAD_FAILED',
            });
        }
        if (!req.file) {
            return res.status(400).json({
                success: false,
                code: 400,
                message: '请选择要上传的文档',
                error_code: 'NO_FILE_UPLOADED',
            });
        }
        logger_1.logger.info('Document upload successful:', {
            userId: req.user?.id,
            filename: req.file.filename,
            size: req.file.size,
            mimetype: req.file.mimetype,
        });
        next();
    });
};
exports.documentUpload = documentUpload;
const validateImage = async (req, res, next) => {
    try {
        if (!req.file) {
            return next();
        }
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        if (!allowedTypes.includes(req.file.mimetype)) {
            await upload_service_1.uploadService.deleteFile(req.file.path);
            return res.status(400).json({
                success: false,
                code: 400,
                message: '文件不是有效的图片格式',
                error_code: 'INVALID_IMAGE_FORMAT',
            });
        }
        if (req.file.size < 100) {
            await upload_service_1.uploadService.deleteFile(req.file.path);
            return res.status(400).json({
                success: false,
                code: 400,
                message: '文件可能已损坏或不是有效图片',
                error_code: 'INVALID_IMAGE_FILE',
            });
        }
        next();
    }
    catch (error) {
        logger_1.logger.error('Image validation error:', error);
        if (req.file) {
            await upload_service_1.uploadService.deleteFile(req.file.path);
        }
        return res.status(500).json({
            success: false,
            code: 500,
            message: '文件验证失败',
            error_code: 'VALIDATION_ERROR',
        });
    }
};
exports.validateImage = validateImage;
const cleanupOnError = (req, res, next) => {
    const originalSend = res.send;
    const originalJson = res.json;
    res.send = function (body) {
        if (this.statusCode >= 400 && req.file) {
            upload_service_1.uploadService.deleteFile(req.file.path).catch(err => {
                logger_1.logger.error('Failed to cleanup uploaded file on error:', err);
            });
        }
        return originalSend.call(this, body);
    };
    res.json = function (body) {
        if (this.statusCode >= 400 && req.file) {
            upload_service_1.uploadService.deleteFile(req.file.path).catch(err => {
                logger_1.logger.error('Failed to cleanup uploaded file on error:', err);
            });
        }
        return originalJson.call(this, body);
    };
    next();
};
exports.cleanupOnError = cleanupOnError;
//# sourceMappingURL=upload.js.map