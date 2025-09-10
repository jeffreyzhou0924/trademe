import { Request, Response } from 'express';
declare class UserController {
    static getProfile(req: Request, res: Response): Promise<void>;
    static updateProfile(req: Request, res: Response): Promise<void>;
    static changePassword(req: Request, res: Response): Promise<void>;
    static bindGoogle(req: Request, res: Response): Promise<void>;
    static unbindGoogle(req: Request, res: Response): Promise<void>;
    static uploadAvatar(req: Request, res: Response): Promise<void>;
    static getUsageStats(req: Request, res: Response): Promise<void>;
    static getMembershipInfo(req: Request, res: Response): Promise<void>;
}
export default UserController;
//# sourceMappingURL=user.d.ts.map