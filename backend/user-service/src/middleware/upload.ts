import { Request, Response, NextFunction } from 'express';
import { uploadService } from '@/services/upload.service';
import { logger } from '@/utils/logger';
import { BusinessError } from '@/middleware/errorHandler';

/**
 * 头像上传中间件
 */
export const avatarUpload = (req: Request, res: Response, next: NextFunction) => {
  const config = uploadService.createAvatarUploadConfig();
  const upload = uploadService.createMulterMiddleware(config);
  
  upload.single('avatar')(req, res, (err: any) => {
    if (err) {
      logger.error('Avatar upload error:', err);
      
      // 处理Multer错误
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
      
      // 处理自定义错误
      if (err instanceof BusinessError) {
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
    
    // 检查是否有文件上传
    if (!req.file) {
      return res.status(400).json({
        success: false,
        code: 400,
        message: '请选择要上传的文件',
        error_code: 'NO_FILE_UPLOADED',
      });
    }
    
    logger.info('Avatar upload successful:', {
      userId: req.user?.id,
      filename: req.file.filename,
      size: req.file.size,
      mimetype: req.file.mimetype,
    });
    
    next();
  });
};

/**
 * 文档上传中间件
 */
export const documentUpload = (req: Request, res: Response, next: NextFunction) => {
  const config = uploadService.createDocumentUploadConfig();
  const upload = uploadService.createMulterMiddleware(config);
  
  upload.single('document')(req, res, (err: any) => {
    if (err) {
      logger.error('Document upload error:', err);
      
      // 处理Multer错误
      if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(400).json({
          success: false,
          code: 400,
          message: '文件大小超过限制 (10MB)',
          error_code: 'FILE_TOO_LARGE',
        });
      }
      
      if (err instanceof BusinessError) {
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
    
    logger.info('Document upload successful:', {
      userId: req.user?.id,
      filename: req.file.filename,
      size: req.file.size,
      mimetype: req.file.mimetype,
    });
    
    next();
  });
};

/**
 * 图片验证中间件 - 验证上传的文件是否为有效图片
 */
export const validateImage = async (req: Request, res: Response, next: NextFunction) => {
  try {
    if (!req.file) {
      return next();
    }

    // 基础验证已在multer中完成，这里可以添加更深入的图片验证
    // 例如：检查图片是否损坏、检查EXIF信息等

    // 简单验证：检查文件是否为图片
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(req.file.mimetype)) {
      // 删除上传的无效文件
      await uploadService.deleteFile(req.file.path);
      
      return res.status(400).json({
        success: false,
        code: 400,
        message: '文件不是有效的图片格式',
        error_code: 'INVALID_IMAGE_FORMAT',
      });
    }

    // 检查文件大小是否合理（防止恶意上传）
    if (req.file.size < 100) { // 少于100字节可能不是有效图片
      await uploadService.deleteFile(req.file.path);
      
      return res.status(400).json({
        success: false,
        code: 400,
        message: '文件可能已损坏或不是有效图片',
        error_code: 'INVALID_IMAGE_FILE',
      });
    }

    next();
  } catch (error) {
    logger.error('Image validation error:', error);
    
    // 清理上传的文件
    if (req.file) {
      await uploadService.deleteFile(req.file.path);
    }
    
    return res.status(500).json({
      success: false,
      code: 500,
      message: '文件验证失败',
      error_code: 'VALIDATION_ERROR',
    });
  }
};

/**
 * 文件清理中间件 - 在请求失败时清理上传的文件
 */
export const cleanupOnError = (req: Request, res: Response, next: NextFunction) => {
  const originalSend = res.send;
  const originalJson = res.json;
  
  // 重写send方法
  res.send = function(this: Response, body: any) {
    if (this.statusCode >= 400 && req.file) {
      // 异步清理文件，不阻塞响应
      uploadService.deleteFile(req.file.path).catch(err => {
        logger.error('Failed to cleanup uploaded file on error:', err);
      });
    }
    return originalSend.call(this, body);
  };
  
  // 重写json方法
  res.json = function(this: Response, body: any) {
    if (this.statusCode >= 400 && req.file) {
      uploadService.deleteFile(req.file.path).catch(err => {
        logger.error('Failed to cleanup uploaded file on error:', err);
      });
    }
    return originalJson.call(this, body);
  };
  
  next();
};