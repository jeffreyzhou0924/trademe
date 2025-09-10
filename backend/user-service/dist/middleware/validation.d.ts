import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
export declare const validateBody: (schema: Joi.ObjectSchema) => (req: Request, res: Response, next: NextFunction) => Response<any, Record<string, any>> | undefined;
export declare const validateQuery: (schema: Joi.ObjectSchema) => (req: Request, res: Response, next: NextFunction) => Response<any, Record<string, any>> | undefined;
export declare const validateParams: (schema: Joi.ObjectSchema) => (req: Request, res: Response, next: NextFunction) => Response<any, Record<string, any>> | undefined;
export declare const validateFileUpload: (options?: {
    maxSize?: number;
    allowedTypes?: string[];
    required?: boolean;
}) => (req: Request, res: Response, next: NextFunction) => void | Response<any, Record<string, any>>;
export declare const generateRequestId: (req: Request, res: Response, next: NextFunction) => void;
export declare const requestLogger: (req: Request, res: Response, next: NextFunction) => void;
export declare const corsHandler: (req: Request, res: Response, next: NextFunction) => Response<any, Record<string, any>> | undefined;
export declare const securityHeaders: (req: Request, res: Response, next: NextFunction) => void;
//# sourceMappingURL=validation.d.ts.map