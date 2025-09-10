import { PrismaClient } from '@prisma/client';
declare class DatabaseService {
    private static instance;
    private prisma;
    private constructor();
    static getInstance(): DatabaseService;
    getClient(): PrismaClient;
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    healthCheck(): Promise<boolean>;
}
export declare const db: DatabaseService;
export declare const prisma: PrismaClient<import(".prisma/client").Prisma.PrismaClientOptions, never, import("@prisma/client/runtime/library").DefaultArgs>;
export {};
//# sourceMappingURL=database.d.ts.map