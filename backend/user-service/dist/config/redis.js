"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.redis = void 0;
const redis_1 = require("redis");
const logger_1 = require("../utils/logger");
class RedisService {
    constructor() {
        this.connected = false;
        const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
        this.client = (0, redis_1.createClient)({
            url: redisUrl,
            socket: {
                reconnectStrategy: (retries) => Math.min(retries * 50, 500),
            },
        });
        this.setupEventHandlers();
    }
    static getInstance() {
        if (!RedisService.instance) {
            RedisService.instance = new RedisService();
        }
        return RedisService.instance;
    }
    setupEventHandlers() {
        this.client.on('connect', () => {
            logger_1.logger.info('Redis client connected');
            this.connected = true;
        });
        this.client.on('error', (err) => {
            logger_1.logger.error('Redis client error:', err);
            this.connected = false;
        });
        this.client.on('end', () => {
            logger_1.logger.info('Redis client disconnected');
            this.connected = false;
        });
        this.client.on('reconnecting', () => {
            logger_1.logger.info('Redis client reconnecting...');
        });
    }
    async connect() {
        try {
            if (!this.connected) {
                await this.client.connect();
            }
        }
        catch (error) {
            logger_1.logger.error('Failed to connect to Redis:', error);
            throw error;
        }
    }
    async disconnect() {
        try {
            if (this.connected) {
                await this.client.disconnect();
            }
        }
        catch (error) {
            logger_1.logger.error('Failed to disconnect from Redis:', error);
            throw error;
        }
    }
    getClient() {
        return this.client;
    }
    isConnected() {
        return this.connected;
    }
    async set(key, value, ttlSeconds) {
        try {
            if (ttlSeconds) {
                await this.client.setEx(key, ttlSeconds, value);
            }
            else {
                await this.client.set(key, value);
            }
        }
        catch (error) {
            logger_1.logger.error('Redis SET error:', { key, error });
            throw error;
        }
    }
    async get(key) {
        try {
            return await this.client.get(key);
        }
        catch (error) {
            logger_1.logger.error('Redis GET error:', { key, error });
            throw error;
        }
    }
    async del(key) {
        try {
            return await this.client.del(key);
        }
        catch (error) {
            logger_1.logger.error('Redis DEL error:', { key, error });
            throw error;
        }
    }
    async exists(key) {
        try {
            const result = await this.client.exists(key);
            return result === 1;
        }
        catch (error) {
            logger_1.logger.error('Redis EXISTS error:', { key, error });
            throw error;
        }
    }
    async incr(key) {
        try {
            return await this.client.incr(key);
        }
        catch (error) {
            logger_1.logger.error('Redis INCR error:', { key, error });
            throw error;
        }
    }
    async decr(key) {
        try {
            return await this.client.decr(key);
        }
        catch (error) {
            logger_1.logger.error('Redis DECR error:', { key, error });
            throw error;
        }
    }
    async expire(key, seconds) {
        try {
            const result = await this.client.expire(key, seconds);
            return result;
        }
        catch (error) {
            logger_1.logger.error('Redis EXPIRE error:', { key, seconds, error });
            throw error;
        }
    }
    async setSession(sessionId, data, ttlSeconds = 86400) {
        const key = `session:${sessionId}`;
        await this.set(key, JSON.stringify(data), ttlSeconds);
    }
    async getSession(sessionId) {
        const key = `session:${sessionId}`;
        const data = await this.get(key);
        return data ? JSON.parse(data) : null;
    }
    async deleteSession(sessionId) {
        const key = `session:${sessionId}`;
        await this.del(key);
    }
    async setVerificationCode(email, code, type = 'register', ttlSeconds = 300) {
        const key = `verification:${type}:${email}`;
        await this.set(key, code, ttlSeconds);
    }
    async getVerificationCode(email, type = 'register') {
        const key = `verification:${type}:${email}`;
        return await this.get(key);
    }
    async deleteVerificationCode(email, type = 'register') {
        const key = `verification:${type}:${email}`;
        await this.del(key);
    }
    async incrementCounter(key, windowSeconds) {
        const count = await this.incr(key);
        if (count === 1) {
            await this.expire(key, windowSeconds);
        }
        return count;
    }
    async healthCheck() {
        try {
            const result = await this.client.ping();
            return result === 'PONG';
        }
        catch (error) {
            logger_1.logger.error('Redis health check failed:', error);
            return false;
        }
    }
}
exports.redis = RedisService.getInstance();
//# sourceMappingURL=redis.js.map