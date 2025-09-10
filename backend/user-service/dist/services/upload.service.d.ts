import multer from 'multer';
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
declare class UploadService {
    private static instance;
    private uploadDir;
    private baseUrl;
    private constructor();
    static getInstance(): UploadService;
    private ensureUploadDirExists;
    private generateUniqueFilename;
    private validateFile;
    createAvatarUploadConfig(): UploadConfig;
    createDocumentUploadConfig(): UploadConfig;
    createMulterMiddleware(config: UploadConfig): multer.Multer;
    processUploadResult(file: Express.Multer.File, subfolder?: string): UploadResult;
    deleteFile(filePath: string): Promise<boolean>;
    deleteOldAvatar(avatarUrl: string): Promise<boolean>;
    cleanupTempFiles(olderThanHours?: number): Promise<void>;
    getFileInfo(filePath: string): Promise<{
        size: number;
        mtime: Date;
        exists: boolean;
    }>;
    getUploadDirInfo(): {
        uploadDir: string;
        baseUrl: string;
        subdirectories: string[];
    };
    healthCheck(): Promise<boolean>;
}
export declare const uploadService: UploadService;
export {};
//# sourceMappingURL=upload.service.d.ts.map