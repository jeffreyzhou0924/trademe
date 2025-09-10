import { RedisClientType } from 'redis';
declare class RedisService {
    private static instance;
    private client;
    private connected;
    private constructor();
    static getInstance(): RedisService;
    private setupEventHandlers;
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    getClient(): RedisClientType;
    isConnected(): boolean;
    set(key: string, value: string, ttlSeconds?: number): Promise<void>;
    get(key: string): Promise<string | null>;
    del(key: string): Promise<number>;
    exists(key: string): Promise<boolean>;
    incr(key: string): Promise<number>;
    decr(key: string): Promise<number>;
    expire(key: string, seconds: number): Promise<boolean>;
    setSession(sessionId: string, data: object, ttlSeconds?: number): Promise<void>;
    getSession(sessionId: string): Promise<object | null>;
    deleteSession(sessionId: string): Promise<void>;
    setVerificationCode(email: string, code: string, type?: string, ttlSeconds?: number): Promise<void>;
    getVerificationCode(email: string, type?: string): Promise<string | null>;
    deleteVerificationCode(email: string, type?: string): Promise<void>;
    incrementCounter(key: string, windowSeconds: number): Promise<number>;
    healthCheck(): Promise<boolean>;
}
export declare const redis: RedisService;
export {};
//# sourceMappingURL=redis.d.ts.map