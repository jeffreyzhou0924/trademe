import { Request, Response, NextFunction } from 'express';
export declare const avatarUpload: (req: Request, res: Response, next: NextFunction) => void;
export declare const documentUpload: (req: Request, res: Response, next: NextFunction) => void;
export declare const validateImage: (req: Request, res: Response, next: NextFunction) => Promise<void | Response<any, Record<string, any>>>;
export declare const cleanupOnError: (req: Request, res: Response, next: NextFunction) => void;
//# sourceMappingURL=upload.d.ts.map