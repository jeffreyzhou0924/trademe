import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';

// 配置环境变量
dotenv.config();

// 导入中间件
import { 
  globalErrorHandler, 
  notFoundHandler,
  handleUncaughtException,
  handleUnhandledRejection 
} from '@/middleware/errorHandler';
import { 
  generateRequestId, 
  requestLogger, 
  corsHandler, 
  securityHeaders 
} from '@/middleware/validation';
import { globalRateLimit } from '@/middleware/rateLimit';

// 导入服务
import { db } from '@/config/database';
import { redis } from '@/config/redis';
import { uploadService } from '@/services/upload.service';
import { emailService } from '@/services/email.service';
import { logger, logSystemInfo } from '@/utils/logger';

// 导入路由
import authRoutes from '@/routes/auth';
import userRoutes from '@/routes/user';
import membershipRoutes from '@/routes/membership';
import configRoutes from '@/routes/config';
import adminRoutes from '@/routes/admin';
import dashboardRoutes from '@/routes/dashboard';

// 处理未捕获的异常
process.on('uncaughtException', handleUncaughtException);
process.on('unhandledRejection', handleUnhandledRejection);

class App {
  public app: express.Application;
  public port: number;

  constructor() {
    this.app = express();
    this.port = parseInt(process.env.PORT || '3001');

    this.initializeMiddlewares();
    this.initializeRoutes();
    this.initializeErrorHandling();
  }

  private initializeMiddlewares(): void {
    // 安全中间件
    this.app.use(helmet({
      contentSecurityPolicy: {
        directives: {
          defaultSrc: ["'self'"],
          styleSrc: ["'self'", "'unsafe-inline'"],
          scriptSrc: ["'self'"],
          imgSrc: ["'self'", "data:", "https:"],
        },
      },
      hsts: {
        maxAge: 31536000,
        includeSubDomains: true,
        preload: true,
      },
    }));

    // CORS配置
    this.app.use(cors({
      origin: (origin, callback) => {
        const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'];
        
        // 允许无origin的请求（如Postman）
        if (!origin) return callback(null, true);
        
        if (allowedOrigins.includes(origin)) {
          callback(null, true);
        } else {
          callback(new Error('Not allowed by CORS'));
        }
      },
      credentials: true,
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
      allowedHeaders: ['Origin', 'X-Requested-With', 'Content-Type', 'Accept', 'Authorization', 'X-Request-ID'],
    }));

    // 基础中间件
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // JSON解析错误处理中间件
    this.app.use((error: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
      if (error instanceof SyntaxError && 'body' in error && 'type' in error && (error as any).type === 'entity.parse.failed') {
        logger.warn('JSON parsing error: ' + error.message, {
          path: req.path,
          method: req.method,
        });
        
        return res.status(400).json({
          success: false,
          code: 400,
          message: 'Invalid JSON format. Please check your request body for syntax errors.',
          error_code: 'JSON_PARSE_ERROR',
          timestamp: new Date().toISOString(),
          request_id: req.headers['x-request-id'],
        });
      }
      next(error);
    });

    // 自定义中间件
    this.app.use(generateRequestId);
    this.app.use(securityHeaders);
    this.app.use(requestLogger);

    // 全局限流
    this.app.use(globalRateLimit);

    // 静态文件服务
    this.app.use('/uploads', express.static(path.join(process.cwd(), 'uploads')));

    // 信任代理（用于获取真实IP）
    this.app.set('trust proxy', 1);
  }

  private initializeRoutes(): void {
    // 健康检查
    this.app.get('/health', async (req, res) => {
      try {
        const dbHealth = await db.healthCheck();
        const redisHealth = await redis.healthCheck();
        const uploadHealth = await uploadService.healthCheck();
        const emailHealth = await emailService.healthCheck();
        
        const health = {
          status: 'ok',
          timestamp: new Date().toISOString(),
          uptime: process.uptime(),
          services: {
            database: dbHealth ? 'healthy' : 'unhealthy',
            redis: redisHealth ? 'healthy' : 'unhealthy',
            upload: uploadHealth ? 'healthy' : 'unhealthy',
            email: emailHealth ? 'healthy' : 'warning', // 邮件服务不健康不影响主服务
          },
          version: process.env.npm_package_version || '1.0.0',
          environment: process.env.NODE_ENV || 'development',
        };

        const statusCode = dbHealth && redisHealth && uploadHealth ? 200 : 503;
        res.status(statusCode).json(health);
      } catch (error) {
        logger.error('Health check error:', error);
        res.status(503).json({
          status: 'error',
          message: 'Service unavailable',
        });
      }
    });

    // API根路径
    this.app.get('/api/v1', (req, res) => {
      res.json({
        success: true,
        message: 'Trademe User Service API v1',
        version: '1.0.0',
        timestamp: new Date().toISOString(),
        endpoints: {
          auth: '/api/v1/auth',
          user: '/api/v1/user',
          membership: '/api/v1/membership',
          config: '/api/v1/config',
          admin: '/api/v1/admin',
          dashboard: '/api/v1/dashboard',
        },
      });
    });

    // 注册路由
    this.app.use('/api/v1/auth', authRoutes);
    this.app.use('/api/v1/user', userRoutes);
    this.app.use('/api/v1/membership', membershipRoutes);
    this.app.use('/api/v1/config', configRoutes);
    this.app.use('/api/v1/admin', adminRoutes);
    this.app.use('/api/v1/dashboard', dashboardRoutes);
  }

  private initializeErrorHandling(): void {
    // 404处理
    this.app.use(notFoundHandler);

    // 全局错误处理
    this.app.use(globalErrorHandler);
  }

  private async initializeDatabase(): Promise<void> {
    try {
      await db.connect();
      logger.info('Database initialized successfully');
    } catch (error) {
      logger.error('Database initialization failed:', error);
      throw error;
    }
  }

  private async initializeRedis(): Promise<void> {
    try {
      await redis.connect();
      logger.info('Redis initialized successfully');
    } catch (error) {
      logger.error('Redis initialization failed:', error);
      throw error;
    }
  }

  public async start(): Promise<void> {
    try {
      // 初始化数据库连接
      await this.initializeDatabase();
      await this.initializeRedis();

      // 启动HTTP服务器 - 监听所有网络接口以支持公网访问
      const server = this.app.listen(this.port, '0.0.0.0', () => {
        logger.info(`🚀 User Service started successfully!`);
        logger.info(`📡 Server running on port ${this.port} (all interfaces)`);
        logger.info(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
        logger.info(`🔗 Health check: http://localhost:${this.port}/health`);
        logger.info(`📚 API docs: http://localhost:${this.port}/api/v1`);
        
        // 记录系统信息
        logSystemInfo();
      });

      // 优雅关闭处理
      const gracefulShutdown = async (signal: string) => {
        logger.info(`Received ${signal}. Starting graceful shutdown...`);

        server.close(async () => {
          try {
            await db.disconnect();
            await redis.disconnect();
            
            logger.info('Graceful shutdown completed');
            process.exit(0);
          } catch (error) {
            logger.error('Error during shutdown:', error);
            process.exit(1);
          }
        });

        // 强制退出超时
        setTimeout(() => {
          logger.error('Forced shutdown due to timeout');
          process.exit(1);
        }, 30000); // 30秒超时
      };

      process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
      process.on('SIGINT', () => gracefulShutdown('SIGINT'));

    } catch (error) {
      logger.error('Failed to start application:', error);
      process.exit(1);
    }
  }

  public getApp(): express.Application {
    return this.app;
  }
}

// 创建应用实例
const app = new App();

// 如果直接运行此文件，启动服务器
if (require.main === module) {
  app.start().catch((error) => {
    logger.error('Application startup failed:', error);
    process.exit(1);
  });
}

export default app;