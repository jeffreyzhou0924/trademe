"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.logSystemInfo = exports.logRequest = exports.logError = exports.logger = exports.httpLogger = void 0;
const winston_1 = __importDefault(require("winston"));
const path_1 = __importDefault(require("path"));
const levels = {
    error: 0,
    warn: 1,
    info: 2,
    http: 3,
    debug: 4,
};
const colors = {
    error: 'red',
    warn: 'yellow',
    info: 'green',
    http: 'magenta',
    debug: 'white',
};
winston_1.default.addColors(colors);
const format = winston_1.default.format.combine(winston_1.default.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss:ms' }), winston_1.default.format.colorize({ all: true }), winston_1.default.format.printf((info) => {
    if (info.stack) {
        return `${info.timestamp} ${info.level}: ${info.message}\n${info.stack}`;
    }
    return `${info.timestamp} ${info.level}: ${info.message}`;
}));
const fileFormat = winston_1.default.format.combine(winston_1.default.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss:ms' }), winston_1.default.format.errors({ stack: true }), winston_1.default.format.json());
const level = () => {
    const env = process.env.NODE_ENV || 'development';
    const isDevelopment = env === 'development';
    return isDevelopment ? 'debug' : 'warn';
};
const transports = [];
if (process.env.NODE_ENV !== 'production') {
    transports.push(new winston_1.default.transports.Console({
        level: level(),
        format,
    }));
}
const logDir = path_1.default.join(process.cwd(), 'logs');
transports.push(new winston_1.default.transports.File({
    filename: path_1.default.join(logDir, 'error.log'),
    level: 'error',
    format: fileFormat,
    maxsize: 5242880,
    maxFiles: 5,
}), new winston_1.default.transports.File({
    filename: path_1.default.join(logDir, 'combined.log'),
    format: fileFormat,
    maxsize: 5242880,
    maxFiles: 5,
}));
const logger = winston_1.default.createLogger({
    level: level(),
    levels,
    format: fileFormat,
    transports,
    exitOnError: false,
});
exports.logger = logger;
exports.httpLogger = winston_1.default.createLogger({
    level: 'http',
    format: winston_1.default.format.combine(winston_1.default.format.timestamp(), winston_1.default.format.json()),
    transports: [
        new winston_1.default.transports.File({
            filename: path_1.default.join(logDir, 'access.log'),
            maxsize: 5242880,
            maxFiles: 5,
        }),
    ],
});
const logError = (error, context) => {
    logger.error(`${context ? `[${context}] ` : ''}${error.message}`, {
        stack: error.stack,
        context,
    });
};
exports.logError = logError;
const logRequest = (req, res, responseTime) => {
    const logData = {
        method: req.method,
        url: req.url,
        status: res.statusCode,
        userAgent: req.get('User-Agent'),
        ip: req.ip || req.connection.remoteAddress,
        responseTime: responseTime ? `${responseTime}ms` : undefined,
        userId: req.user?.id,
    };
    if (res.statusCode >= 400) {
        logger.warn('HTTP Request Error', logData);
    }
    else {
        exports.httpLogger.http('HTTP Request', logData);
    }
};
exports.logRequest = logRequest;
const logSystemInfo = () => {
    logger.info('System Information', {
        nodeVersion: process.version,
        platform: process.platform,
        arch: process.arch,
        memory: process.memoryUsage(),
        uptime: process.uptime(),
    });
};
exports.logSystemInfo = logSystemInfo;
//# sourceMappingURL=logger.js.map