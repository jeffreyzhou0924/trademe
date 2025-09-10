"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.prisma = exports.db = void 0;
const client_1 = require("@prisma/client");
const logger_1 = require("../utils/logger");
class DatabaseService {
    constructor() {
        this.prisma = new client_1.PrismaClient({
            log: ['query', 'error', 'info', 'warn'],
            errorFormat: 'pretty',
        });
    }
    static getInstance() {
        if (!DatabaseService.instance) {
            DatabaseService.instance = new DatabaseService();
        }
        return DatabaseService.instance;
    }
    getClient() {
        return this.prisma;
    }
    async connect() {
        try {
            await this.prisma.$connect();
            logger_1.logger.info('Database connected successfully');
        }
        catch (error) {
            logger_1.logger.error('Failed to connect to database:', error);
            throw error;
        }
    }
    async disconnect() {
        try {
            await this.prisma.$disconnect();
            logger_1.logger.info('Database disconnected');
        }
        catch (error) {
            logger_1.logger.error('Failed to disconnect from database:', error);
            throw error;
        }
    }
    async healthCheck() {
        try {
            await this.prisma.$queryRaw `SELECT 1`;
            return true;
        }
        catch (error) {
            logger_1.logger.error('Database health check failed:', error);
            return false;
        }
    }
}
exports.db = DatabaseService.getInstance();
exports.prisma = exports.db.getClient();
//# sourceMappingURL=database.js.map