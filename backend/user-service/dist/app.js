"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const helmet_1 = __importDefault(require("helmet"));
const cors_1 = __importDefault(require("cors"));
const dotenv_1 = __importDefault(require("dotenv"));
const path_1 = __importDefault(require("path"));
dotenv_1.default.config();
const errorHandler_1 = require("./middleware/errorHandler");
const validation_1 = require("./middleware/validation");
const rateLimit_1 = require("./middleware/rateLimit");
const database_1 = require("./config/database");
const redis_1 = require("./config/redis");
const upload_service_1 = require("./services/upload.service");
const email_service_1 = require("./services/email.service");
const logger_1 = require("./utils/logger");
const auth_1 = __importDefault(require("./routes/auth"));
const user_1 = __importDefault(require("./routes/user"));
const membership_1 = __importDefault(require("./routes/membership"));
const config_1 = __importDefault(require("./routes/config"));
const admin_1 = __importDefault(require("./routes/admin"));
const dashboard_1 = __importDefault(require("./routes/dashboard"));
process.on('uncaughtException', errorHandler_1.handleUncaughtException);
process.on('unhandledRejection', errorHandler_1.handleUnhandledRejection);
class App {
    constructor() {
        this.app = (0, express_1.default)();
        this.port = parseInt(process.env.PORT || '3001');
        this.initializeMiddlewares();
        this.initializeRoutes();
        this.initializeErrorHandling();
    }
    initializeMiddlewares() {
        this.app.use((0, helmet_1.default)({
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
        this.app.use((0, cors_1.default)({
            origin: (origin, callback) => {
                const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'];
                if (!origin)
                    return callback(null, true);
                if (allowedOrigins.includes(origin)) {
                    callback(null, true);
                }
                else {
                    callback(new Error('Not allowed by CORS'));
                }
            },
            credentials: true,
            methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allowedHeaders: ['Origin', 'X-Requested-With', 'Content-Type', 'Accept', 'Authorization', 'X-Request-ID'],
        }));
        this.app.use(express_1.default.json({ limit: '10mb' }));
        this.app.use(express_1.default.urlencoded({ extended: true, limit: '10mb' }));
        this.app.use((error, req, res, next) => {
            if (error instanceof SyntaxError && 'body' in error && 'type' in error && error.type === 'entity.parse.failed') {
                logger_1.logger.warn('JSON parsing error: ' + error.message, {
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
        this.app.use(validation_1.generateRequestId);
        this.app.use(validation_1.securityHeaders);
        this.app.use(validation_1.requestLogger);
        this.app.use(rateLimit_1.globalRateLimit);
        this.app.use('/uploads', express_1.default.static(path_1.default.join(process.cwd(), 'uploads')));
        this.app.set('trust proxy', 1);
    }
    initializeRoutes() {
        this.app.get('/health', async (req, res) => {
            try {
                const dbHealth = await database_1.db.healthCheck();
                const redisHealth = await redis_1.redis.healthCheck();
                const uploadHealth = await upload_service_1.uploadService.healthCheck();
                const emailHealth = await email_service_1.emailService.healthCheck();
                const health = {
                    status: 'ok',
                    timestamp: new Date().toISOString(),
                    uptime: process.uptime(),
                    services: {
                        database: dbHealth ? 'healthy' : 'unhealthy',
                        redis: redisHealth ? 'healthy' : 'unhealthy',
                        upload: uploadHealth ? 'healthy' : 'unhealthy',
                        email: emailHealth ? 'healthy' : 'warning',
                    },
                    version: process.env.npm_package_version || '1.0.0',
                    environment: process.env.NODE_ENV || 'development',
                };
                const statusCode = dbHealth && redisHealth && uploadHealth ? 200 : 503;
                res.status(statusCode).json(health);
            }
            catch (error) {
                logger_1.logger.error('Health check error:', error);
                res.status(503).json({
                    status: 'error',
                    message: 'Service unavailable',
                });
            }
        });
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
        this.app.use('/api/v1/auth', auth_1.default);
        this.app.use('/api/v1/user', user_1.default);
        this.app.use('/api/v1/membership', membership_1.default);
        this.app.use('/api/v1/config', config_1.default);
        this.app.use('/api/v1/admin', admin_1.default);
        this.app.use('/api/v1/dashboard', dashboard_1.default);
    }
    initializeErrorHandling() {
        this.app.use(errorHandler_1.notFoundHandler);
        this.app.use(errorHandler_1.globalErrorHandler);
    }
    async initializeDatabase() {
        try {
            await database_1.db.connect();
            logger_1.logger.info('Database initialized successfully');
        }
        catch (error) {
            logger_1.logger.error('Database initialization failed:', error);
            throw error;
        }
    }
    async initializeRedis() {
        try {
            await redis_1.redis.connect();
            logger_1.logger.info('Redis initialized successfully');
        }
        catch (error) {
            logger_1.logger.error('Redis initialization failed:', error);
            throw error;
        }
    }
    async start() {
        try {
            await this.initializeDatabase();
            await this.initializeRedis();
            const server = this.app.listen(this.port, '0.0.0.0', () => {
                logger_1.logger.info(`🚀 User Service started successfully!`);
                logger_1.logger.info(`📡 Server running on port ${this.port} (all interfaces)`);
                logger_1.logger.info(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
                logger_1.logger.info(`🔗 Health check: http://localhost:${this.port}/health`);
                logger_1.logger.info(`📚 API docs: http://localhost:${this.port}/api/v1`);
                (0, logger_1.logSystemInfo)();
            });
            const gracefulShutdown = async (signal) => {
                logger_1.logger.info(`Received ${signal}. Starting graceful shutdown...`);
                server.close(async () => {
                    try {
                        await database_1.db.disconnect();
                        await redis_1.redis.disconnect();
                        logger_1.logger.info('Graceful shutdown completed');
                        process.exit(0);
                    }
                    catch (error) {
                        logger_1.logger.error('Error during shutdown:', error);
                        process.exit(1);
                    }
                });
                setTimeout(() => {
                    logger_1.logger.error('Forced shutdown due to timeout');
                    process.exit(1);
                }, 30000);
            };
            process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
            process.on('SIGINT', () => gracefulShutdown('SIGINT'));
        }
        catch (error) {
            logger_1.logger.error('Failed to start application:', error);
            process.exit(1);
        }
    }
    getApp() {
        return this.app;
    }
}
const app = new App();
if (require.main === module) {
    app.start().catch((error) => {
        logger_1.logger.error('Application startup failed:', error);
        process.exit(1);
    });
}
exports.default = app;
//# sourceMappingURL=app.js.map