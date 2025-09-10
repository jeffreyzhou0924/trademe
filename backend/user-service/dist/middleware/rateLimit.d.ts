import { Request, Response, NextFunction } from 'express';
interface RateLimitOptions {
    windowMs: number;
    maxRequests: number;
    message?: string;
    keyGenerator?: (req: Request) => string;
    skipSuccessfulRequests?: boolean;
    skipFailedRequests?: boolean;
}
export declare const createRateLimit: (options: RateLimitOptions) => (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const globalRateLimit: (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const authRateLimit: (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const verificationCodeRateLimit: (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const passwordResetRateLimit: (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const userBasedRateLimit: (options: Omit<RateLimitOptions, "keyGenerator">) => (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const apiCallRateLimit: (req: Request, res: Response, next: NextFunction) => Promise<void | Response<any, Record<string, any>>>;
export declare const fileUploadRateLimit: (req: Request, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const getRateLimitStatus: (key: string) => Promise<{
    current: number;
    remaining: number;
    resetTime: Date;
}>;
export declare const clearUserRateLimit: (userId: string) => Promise<void>;
export {};
//# sourceMappingURL=rateLimit.d.ts.map