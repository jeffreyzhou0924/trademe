import express from 'express';
declare class App {
    app: express.Application;
    port: number;
    constructor();
    private initializeMiddlewares;
    private initializeRoutes;
    private initializeErrorHandling;
    private initializeDatabase;
    private initializeRedis;
    start(): Promise<void>;
    getApp(): express.Application;
}
declare const app: App;
export default app;
//# sourceMappingURL=app.d.ts.map