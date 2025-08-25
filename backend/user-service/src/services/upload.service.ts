import multer from 'multer';
import path from 'path';
import fs from 'fs/promises';
import crypto from 'crypto';
import { logger } from '@/utils/logger';
import { BusinessError } from '@/middleware/errorHandler';

export interface UploadConfig {
  destination: string;
  maxSize: number;
  allowedMimeTypes: string[];
  allowedExtensions: string[];
}

export interface UploadResult {
  filename: string;
  originalName: string;
  size: number;
  mimeType: string;
  url: string;
  path: string;
}

class UploadService {
  private static instance: UploadService;
  private uploadDir: string;
  private baseUrl: string;

  private constructor() {
    this.uploadDir = process.env.UPLOAD_DIR || './uploads';
    this.baseUrl = process.env.UPLOAD_BASE_URL || 'http://localhost:3001/uploads';
    
    this.ensureUploadDirExists();
  }

  public static getInstance(): UploadService {
    if (!UploadService.instance) {
      UploadService.instance = new UploadService();
    }
    return UploadService.instance;
  }

  private async ensureUploadDirExists(): Promise<void> {
    try {
      // 创建主上传目录
      await fs.mkdir(this.uploadDir, { recursive: true });
      
      // 创建子目录
      const subdirs = ['avatars', 'documents', 'temp'];
      for (const subdir of subdirs) {
        await fs.mkdir(path.join(this.uploadDir, subdir), { recursive: true });
      }
      
      logger.info('Upload directories initialized:', { uploadDir: this.uploadDir });
    } catch (error) {
      logger.error('Failed to create upload directories:', error);
      throw error;
    }
  }

  /**
   * 生成唯一文件名
   */
  private generateUniqueFilename(originalName: string): string {
    const ext = path.extname(originalName);
    const timestamp = Date.now();
    const random = crypto.randomBytes(6).toString('hex');
    return `${timestamp}_${random}${ext}`;
  }

  /**
   * 验证文件类型
   */
  private validateFile(file: Express.Multer.File, config: UploadConfig): void {
    // 检查MIME类型
    if (!config.allowedMimeTypes.includes(file.mimetype)) {
      throw new BusinessError(
        `不支持的文件类型: ${file.mimetype}`,
        'INVALID_FILE_TYPE'
      );
    }

    // 检查文件扩展名
    const ext = path.extname(file.originalname).toLowerCase();
    if (!config.allowedExtensions.includes(ext)) {
      throw new BusinessError(
        `不支持的文件扩展名: ${ext}`,
        'INVALID_FILE_EXTENSION'
      );
    }

    // 检查文件大小
    if (file.size > config.maxSize) {
      throw new BusinessError(
        `文件大小超过限制 (${Math.round(config.maxSize / 1024 / 1024)}MB)`,
        'FILE_TOO_LARGE'
      );
    }
  }

  /**
   * 创建头像上传配置
   */
  public createAvatarUploadConfig(): UploadConfig {
    return {
      destination: path.join(this.uploadDir, 'avatars'),
      maxSize: 5 * 1024 * 1024, // 5MB
      allowedMimeTypes: [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp'
      ],
      allowedExtensions: ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    };
  }

  /**
   * 创建文档上传配置
   */
  public createDocumentUploadConfig(): UploadConfig {
    return {
      destination: path.join(this.uploadDir, 'documents'),
      maxSize: 10 * 1024 * 1024, // 10MB
      allowedMimeTypes: [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
      ],
      allowedExtensions: ['.pdf', '.doc', '.docx', '.txt']
    };
  }

  /**
   * 创建Multer中间件
   */
  public createMulterMiddleware(config: UploadConfig) {
    const storage = multer.diskStorage({
      destination: (req, file, cb) => {
        cb(null, config.destination);
      },
      filename: (req, file, cb) => {
        const uniqueName = this.generateUniqueFilename(file.originalname);
        cb(null, uniqueName);
      }
    });

    const fileFilter = (req: any, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
      try {
        this.validateFile(file, config);
        cb(null, true);
      } catch (error) {
        cb(error as any, false);
      }
    };

    return multer({
      storage,
      fileFilter,
      limits: {
        fileSize: config.maxSize,
        files: 1, // 限制单次只能上传一个文件
      }
    });
  }

  /**
   * 处理文件上传结果
   */
  public processUploadResult(file: Express.Multer.File, subfolder: string = ''): UploadResult {
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

  /**
   * 删除文件
   */
  public async deleteFile(filePath: string): Promise<boolean> {
    try {
      // 确保文件在上传目录内（安全检查）
      const normalizedPath = path.normalize(filePath);
      const normalizedUploadDir = path.normalize(this.uploadDir);
      
      if (!normalizedPath.startsWith(normalizedUploadDir)) {
        logger.warn('Attempt to delete file outside upload directory:', filePath);
        return false;
      }

      await fs.unlink(filePath);
      logger.info('File deleted successfully:', filePath);
      return true;
    } catch (error) {
      logger.error('Failed to delete file:', { filePath, error });
      return false;
    }
  }

  /**
   * 删除旧头像文件
   */
  public async deleteOldAvatar(avatarUrl: string): Promise<boolean> {
    if (!avatarUrl || !avatarUrl.includes(this.baseUrl)) {
      return true; // 外部URL，不需要删除
    }

    try {
      // 从URL提取文件路径
      const filename = avatarUrl.split('/').pop();
      if (!filename) return false;

      const filePath = path.join(this.uploadDir, 'avatars', filename);
      return await this.deleteFile(filePath);
    } catch (error) {
      logger.error('Failed to delete old avatar:', { avatarUrl, error });
      return false;
    }
  }

  /**
   * 清理临时文件（定时任务）
   */
  public async cleanupTempFiles(olderThanHours: number = 24): Promise<void> {
    const tempDir = path.join(this.uploadDir, 'temp');
    const cutoffTime = Date.now() - (olderThanHours * 60 * 60 * 1000);

    try {
      const files = await fs.readdir(tempDir);
      let deletedCount = 0;

      for (const file of files) {
        const filePath = path.join(tempDir, file);
        const stats = await fs.stat(filePath);
        
        if (stats.mtime.getTime() < cutoffTime) {
          await this.deleteFile(filePath);
          deletedCount++;
        }
      }

      logger.info('Temp files cleanup completed:', { deletedCount });
    } catch (error) {
      logger.error('Temp files cleanup failed:', error);
    }
  }

  /**
   * 获取文件信息
   */
  public async getFileInfo(filePath: string): Promise<{
    size: number;
    mtime: Date;
    exists: boolean;
  }> {
    try {
      const stats = await fs.stat(filePath);
      return {
        size: stats.size,
        mtime: stats.mtime,
        exists: true
      };
    } catch (error) {
      return {
        size: 0,
        mtime: new Date(0),
        exists: false
      };
    }
  }

  /**
   * 获取上传目录信息
   */
  public getUploadDirInfo(): {
    uploadDir: string;
    baseUrl: string;
    subdirectories: string[];
  } {
    return {
      uploadDir: this.uploadDir,
      baseUrl: this.baseUrl,
      subdirectories: ['avatars', 'documents', 'temp']
    };
  }

  /**
   * 健康检查
   */
  public async healthCheck(): Promise<boolean> {
    try {
      // 检查上传目录是否可写
      const testFile = path.join(this.uploadDir, 'temp', 'health_check.txt');
      await fs.writeFile(testFile, 'health check');
      await fs.unlink(testFile);
      
      logger.info('Upload service health check passed');
      return true;
    } catch (error) {
      logger.error('Upload service health check failed:', error);
      return false;
    }
  }
}

export const uploadService = UploadService.getInstance();