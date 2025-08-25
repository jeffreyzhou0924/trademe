import winston from 'winston';
import path from 'path';

// 日志级别
const levels = {
  error: 0,
  warn: 1,
  info: 2,
  http: 3,
  debug: 4,
};

// 日志颜色
const colors = {
  error: 'red',
  warn: 'yellow',
  info: 'green',
  http: 'magenta',
  debug: 'white',
};

// 添加颜色
winston.addColors(colors);

// 日志格式
const format = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss:ms' }),
  winston.format.colorize({ all: true }),
  winston.format.printf((info) => {
    if (info.stack) {
      return `${info.timestamp} ${info.level}: ${info.message}\n${info.stack}`;
    }
    return `${info.timestamp} ${info.level}: ${info.message}`;
  })
);

// 文件日志格式（不包含颜色）
const fileFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss:ms' }),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// 获取日志级别
const level = (): string => {
  const env = process.env.NODE_ENV || 'development';
  const isDevelopment = env === 'development';
  return isDevelopment ? 'debug' : 'warn';
};

// 创建日志传输
const transports = [];

// 控制台输出
if (process.env.NODE_ENV !== 'production') {
  transports.push(
    new winston.transports.Console({
      level: level(),
      format,
    })
  );
}

// 文件输出
const logDir = path.join(process.cwd(), 'logs');
transports.push(
  // 错误日志文件
  new winston.transports.File({
    filename: path.join(logDir, 'error.log'),
    level: 'error',
    format: fileFormat,
    maxsize: 5242880, // 5MB
    maxFiles: 5,
  }),
  // 所有日志文件
  new winston.transports.File({
    filename: path.join(logDir, 'combined.log'),
    format: fileFormat,
    maxsize: 5242880, // 5MB
    maxFiles: 5,
  })
);

// 创建logger实例
const logger = winston.createLogger({
  level: level(),
  levels,
  format: fileFormat,
  transports,
  exitOnError: false,
});

// HTTP请求日志中间件
export const httpLogger = winston.createLogger({
  level: 'http',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({
      filename: path.join(logDir, 'access.log'),
      maxsize: 5242880, // 5MB
      maxFiles: 5,
    }),
  ],
});

// 导出logger
export { logger };

// 错误处理函数
export const logError = (error: Error, context?: string): void => {
  logger.error(`${context ? `[${context}] ` : ''}${error.message}`, {
    stack: error.stack,
    context,
  });
};

// 请求日志函数
export const logRequest = (req: any, res: any, responseTime?: number): void => {
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
  } else {
    httpLogger.http('HTTP Request', logData);
  }
};

// 系统信息日志
export const logSystemInfo = (): void => {
  logger.info('System Information', {
    nodeVersion: process.version,
    platform: process.platform,
    arch: process.arch,
    memory: process.memoryUsage(),
    uptime: process.uptime(),
  });
};