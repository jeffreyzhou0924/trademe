"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.uploadService = void 0;
const multer_1 = __importDefault(require("multer"));
const path_1 = __importDefault(require("path"));
const promises_1 = __importDefault(require("fs/promises"));
const crypto_1 = __importDefault(require("crypto"));
const logger_1 = require("../utils/logger");
const errorHandler_1 = require("../middleware/errorHandler");
class UploadService {
    constructor() {
        this.uploadDir = process.env.UPLOAD_DIR || './uploads';
        this.baseUrl = process.env.UPLOAD_BASE_URL || 'http://localhost:3001/uploads';
        this.ensureUploadDirExists();
    }
    static getInstance() {
        if (!UploadService.instance) {
            UploadService.instance = new UploadService();
        }
        return UploadService.instance;
    }
    async ensureUploadDirExists() {
        try {
            await promises_1.default.mkdir(this.uploadDir, { recursive: true });
            const subdirs = ['avatars', 'documents', 'temp'];
            for (const subdir of subdirs) {
                await promises_1.default.mkdir(path_1.default.join(this.uploadDir, subdir), { recursive: true });
            }
            logger_1.logger.info('Upload directories initialized:', { uploadDir: this.uploadDir });
        }
        catch (error) {
            logger_1.logger.error('Failed to create upload directories:', error);
            throw error;
        }
    }
    generateUniqueFilename(originalName) {
        const ext = path_1.default.extname(originalName);
        const timestamp = Date.now();
        const random = crypto_1.default.randomBytes(6).toString('hex');
        return `${timestamp}_${random}${ext}`;
    }
    validateFile(file, config) {
        if (!config.allowedMimeTypes.includes(file.mimetype)) {
            throw new errorHandler_1.BusinessError(`不支持的文件类型: ${file.mimetype}`, 'INVALID_FILE_TYPE');
        }
        const ext = path_1.default.extname(file.originalname).toLowerCase();
        if (!config.allowedExtensions.includes(ext)) {
            throw new errorHandler_1.BusinessError(`不支持的文件扩展名: ${ext}`, 'INVALID_FILE_EXTENSION');
        }
        if (file.size > config.maxSize) {
            throw new errorHandler_1.BusinessError(`文件大小超过限制 (${Math.round(config.maxSize / 1024 / 1024)}MB)`, 'FILE_TOO_LARGE');
        }
    }
    createAvatarUploadConfig() {
        return {
            destination: path_1.default.join(this.uploadDir, 'avatars'),
            maxSize: 5 * 1024 * 1024,
            allowedMimeTypes: [
                'image/jpeg',
                'image/png',
                'image/gif',
                'image/webp'
            ],
            allowedExtensions: ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        };
    }
    createDocumentUploadConfig() {
        return {
            destination: path_1.default.join(this.uploadDir, 'documents'),
            maxSize: 10 * 1024 * 1024,
            allowedMimeTypes: [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain'
            ],
            allowedExtensions: ['.pdf', '.doc', '.docx', '.txt']
        };
    }
    createMulterMiddleware(config) {
        const storage = multer_1.default.diskStorage({
            destination: (req, file, cb) => {
                cb(null, config.destination);
            },
            filename: (req, file, cb) => {
                const uniqueName = this.generateUniqueFilename(file.originalname);
                cb(null, uniqueName);
            }
        });
        const fileFilter = (req, file, cb) => {
            try {
                this.validateFile(file, config);
                cb(null, true);
            }
            catch (error) {
                cb(error, false);
            }
        };
        return (0, multer_1.default)({
            storage,
            fileFilter,
            limits: {
                fileSize: config.maxSize,
                files: 1,
            }
        });
    }
    processUploadResult(file, subfolder = '') {
        const relativePath = subfolder ? `${subfolder}/${file.filename}` : file.filename;
        const url = `${this.baseUrl}/${relativePath}`;
        return {
            filename: file.filename,
            originalName: file.originalname,
            size: file.size,
            mimeType: file.mimetype,
            url,
            path: file.path
        };
    }
    async deleteFile(filePath) {
        try {
            const normalizedPath = path_1.default.normalize(filePath);
            const normalizedUploadDir = path_1.default.normalize(this.uploadDir);
            if (!normalizedPath.startsWith(normalizedUploadDir)) {
                logger_1.logger.warn('Attempt to delete file outside upload directory:', filePath);
                return false;
            }
            await promises_1.default.unlink(filePath);
            logger_1.logger.info('File deleted successfully:', filePath);
            return true;
        }
        catch (error) {
            logger_1.logger.error('Failed to delete file:', { filePath, error });
            return false;
        }
    }
    async deleteOldAvatar(avatarUrl) {
        if (!avatarUrl || !avatarUrl.includes(this.baseUrl)) {
            return true;
        }
        try {
            const filename = avatarUrl.split('/').pop();
            if (!filename)
                return false;
            const filePath = path_1.default.join(this.uploadDir, 'avatars', filename);
            return await this.deleteFile(filePath);
        }
        catch (error) {
            logger_1.logger.error('Failed to delete old avatar:', { avatarUrl, error });
            return false;
        }
    }
    async cleanupTempFiles(olderThanHours = 24) {
        const tempDir = path_1.default.join(this.uploadDir, 'temp');
        const cutoffTime = Date.now() - (olderThanHours * 60 * 60 * 1000);
        try {
            const files = await promises_1.default.readdir(tempDir);
            let deletedCount = 0;
            for (const file of files) {
                const filePath = path_1.default.join(tempDir, file);
                const stats = await promises_1.default.stat(filePath);
                if (stats.mtime.getTime() < cutoffTime) {
                    await this.deleteFile(filePath);
                    deletedCount++;
                }
            }
            logger_1.logger.info('Temp files cleanup completed:', { deletedCount });
        }
        catch (error) {
            logger_1.logger.error('Temp files cleanup failed:', error);
        }
    }
    async getFileInfo(filePath) {
        try {
            const stats = await promises_1.default.stat(filePath);
            return {
                size: stats.size,
                mtime: stats.mtime,
                exists: true
            };
        }
        catch (error) {
            return {
                size: 0,
                mtime: new Date(0),
                exists: false
            };
        }
    }
    getUploadDirInfo() {
        return {
            uploadDir: this.uploadDir,
            baseUrl: this.baseUrl,
            subdirectories: ['avatars', 'documents', 'temp']
        };
    }
    async healthCheck() {
        try {
            const testFile = path_1.default.join(this.uploadDir, 'temp', 'health_check.txt');
            await promises_1.default.writeFile(testFile, 'health check');
            await promises_1.default.unlink(testFile);
            logger_1.logger.info('Upload service health check passed');
            return true;
        }
        catch (error) {
            logger_1.logger.error('Upload service health check failed:', error);
            return false;
        }
    }
}
exports.uploadService = UploadService.getInstance();
//# sourceMappingURL=upload.service.js.map