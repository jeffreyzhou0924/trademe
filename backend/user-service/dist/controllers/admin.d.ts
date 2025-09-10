import { Request, Response } from 'express';
declare class AdminController {
    static getUsers(req: Request, res: Response): Promise<void>;
    static getUserDetail(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    static updateUser(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    static getSystemStats(req: Request, res: Response): Promise<void>;
    static getUserActivities(req: Request, res: Response): Promise<void>;
    static getUserMembershipStats(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    static batchUpdateUsers(req: Request, res: Response): Promise<Response<any, Record<string, any>> | undefined>;
    static getMembershipAnalytics(req: Request, res: Response): Promise<void>;
    static getClaudeAccounts(req: Request, res: Response): Promise<void>;
    static addClaudeAccount(req: Request, res: Response): Promise<void>;
    static updateClaudeAccount(req: Request, res: Response): Promise<void>;
    static deleteClaudeAccount(req: Request, res: Response): Promise<void>;
    static testClaudeAccount(req: Request, res: Response): Promise<void>;
    static getClaudeUsageStats(req: Request, res: Response): Promise<void>;
    static getProxies(req: Request, res: Response): Promise<void>;
    static getSchedulerConfig(req: Request, res: Response): Promise<void>;
    static updateSchedulerConfig(req: Request, res: Response): Promise<void>;
    static getAIAnomalyDetection(req: Request, res: Response): Promise<void>;
}
export default AdminController;
//# sourceMappingURL=admin.d.ts.map