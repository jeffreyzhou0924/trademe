import { createClient, RedisClientType } from 'redis';
import { logger } from '@/utils/logger';

class RedisService {
  private static instance: RedisService;
  private client: RedisClientType;
  private connected: boolean = false;

  private constructor() {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    
    this.client = createClient({
      url: redisUrl,
      socket: {
        reconnectStrategy: (retries) => Math.min(retries * 50, 500),
      },
    }) as RedisClientType;

    this.setupEventHandlers();
  }

  public static getInstance(): RedisService {
    if (!RedisService.instance) {
      RedisService.instance = new RedisService();
    }
    return RedisService.instance;
  }

  private setupEventHandlers(): void {
    this.client.on('connect', () => {
      logger.info('Redis client connected');
      this.connected = true;
    });

    this.client.on('error', (err) => {
      logger.error('Redis client error:', err);
      this.connected = false;
    });

    this.client.on('end', () => {
      logger.info('Redis client disconnected');
      this.connected = false;
    });

    this.client.on('reconnecting', () => {
      logger.info('Redis client reconnecting...');
    });
  }

  public async connect(): Promise<void> {
    try {
      if (!this.connected) {
        await this.client.connect();
      }
    } catch (error) {
      logger.error('Failed to connect to Redis:', error);
      throw error;
    }
  }

  public async disconnect(): Promise<void> {
    try {
      if (this.connected) {
        await this.client.disconnect();
      }
    } catch (error) {
      logger.error('Failed to disconnect from Redis:', error);
      throw error;
    }
  }

  public getClient(): RedisClientType {
    return this.client;
  }

  public isConnected(): boolean {
    return this.connected;
  }

  // 常用Redis操作的封装
  public async set(key: string, value: string, ttlSeconds?: number): Promise<void> {
    try {
      if (ttlSeconds) {
        await this.client.setEx(key, ttlSeconds, value);
      } else {
        await this.client.set(key, value);
      }
    } catch (error) {
      logger.error('Redis SET error:', { key, error });
      throw error;
    }
  }

  public async get(key: string): Promise<string | null> {
    try {
      return await this.client.get(key);
    } catch (error) {
      logger.error('Redis GET error:', { key, error });
      throw error;
    }
  }

  public async del(key: string): Promise<number> {
    try {
      return await this.client.del(key);
    } catch (error) {
      logger.error('Redis DEL error:', { key, error });
      throw error;
    }
  }

  public async exists(key: string): Promise<boolean> {
    try {
      const result = await this.client.exists(key);
      return result === 1;
    } catch (error) {
      logger.error('Redis EXISTS error:', { key, error });
      throw error;
    }
  }

  public async incr(key: string): Promise<number> {
    try {
      return await this.client.incr(key);
    } catch (error) {
      logger.error('Redis INCR error:', { key, error });
      throw error;
    }
  }

  public async decr(key: string): Promise<number> {
    try {
      return await this.client.decr(key);
    } catch (error) {
      logger.error('Redis DECR error:', { key, error });
      throw error;
    }
  }

  public async expire(key: string, seconds: number): Promise<boolean> {
    try {
      const result = await this.client.expire(key, seconds);
      return result;
    } catch (error) {
      logger.error('Redis EXPIRE error:', { key, seconds, error });
      throw error;
    }
  }

  // Session相关操作
  public async setSession(sessionId: string, data: object, ttlSeconds: number = 86400): Promise<void> {
    const key = `session:${sessionId}`;
    await this.set(key, JSON.stringify(data), ttlSeconds);
  }

  public async getSession(sessionId: string): Promise<object | null> {
    const key = `session:${sessionId}`;
    const data = await this.get(key);
    return data ? JSON.parse(data) : null;
  }

  public async deleteSession(sessionId: string): Promise<void> {
    const key = `session:${sessionId}`;
    await this.del(key);
  }

  // 验证码相关操作
  public async setVerificationCode(email: string, code: string, type: string = 'register', ttlSeconds: number = 300): Promise<void> {
    const key = `verification:${type}:${email}`;
    await this.set(key, code, ttlSeconds);
  }

  public async getVerificationCode(email: string, type: string = 'register'): Promise<string | null> {
    const key = `verification:${type}:${email}`;
    return await this.get(key);
  }

  public async deleteVerificationCode(email: string, type: string = 'register'): Promise<void> {
    const key = `verification:${type}:${email}`;
    await this.del(key);
  }

  // 限频操作
  public async incrementCounter(key: string, windowSeconds: number): Promise<number> {
    const count = await this.incr(key);
    if (count === 1) {
      await this.expire(key, windowSeconds);
    }
    return count;
  }

  public async healthCheck(): Promise<boolean> {
    try {
      const result = await this.client.ping();
      return result === 'PONG';
    } catch (error) {
      logger.error('Redis health check failed:', error);
      return false;
    }
  }
}

export const redis = RedisService.getInstance();