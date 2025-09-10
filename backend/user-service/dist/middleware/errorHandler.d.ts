import { Request, Response, NextFunction } from 'express';
export declare class AppError extends Error {
    readonly statusCode: number;
    readonly errorCode: string;
    readonly isOperational: boolean;
    constructor(message: string, statusCode?: number, errorCode?: string, isOperational?: boolean);
}
export declare class BusinessError extends AppError {
    constructor(message: string, errorCode?: string);
}
export declare class AuthenticationError extends AppError {
    constructor(message?: string, errorCode?: string);
}
export declare class AuthorizationError extends AppError {
    constructor(message?: string, errorCode?: string);
}
export declare class NotFoundError extends AppError {
    constructor(resource?: string);
}
export declare class ValidationError extends AppError {
    readonly errors: Array<{
        field: string;
        code: string;
        message: string;
    }>;
    constructor(errors: Array<{
        field: string;
        code: string;
        message: string;
    }>);
}
export declare class ConflictError extends AppError {
    constructor(message?: string, errorCode?: string);
}
export declare const handleUncaughtException: (error: Error) => void;
export declare const handleUnhandledRejection: (reason: any) => void;
export declare const notFoundHandler: (req: Request, res: Response, next: NextFunction) => void;
export declare const globalErrorHandler: (error: Error, req: Request, res: Response, next: NextFunction) => void;
export declare const asyncHandler: (fn: Function) => (req: Request, res: Response, next: NextFunction) => void;
export declare const logError: (error: Error, context?: any) => void;
export declare const assert: (condition: boolean, message: string, errorCode?: string) => void;
export declare const assertPermission: (condition: boolean, message?: string) => void;
export declare const assertExists: <T>(resource: T | null | undefined, name?: string) => T;
//# sourceMappingURL=errorHandler.d.ts.map