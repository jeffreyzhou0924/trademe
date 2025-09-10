import winston from 'winston';
declare const logger: winston.Logger;
export declare const httpLogger: winston.Logger;
export { logger };
export declare const logError: (error: Error, context?: string) => void;
export declare const logRequest: (req: any, res: any, responseTime?: number) => void;
export declare const logSystemInfo: () => void;
//# sourceMappingURL=logger.d.ts.map