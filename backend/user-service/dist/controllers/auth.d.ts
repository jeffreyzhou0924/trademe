import { Request, Response } from 'express';
declare class AuthController {
    static register(req: Request, res: Response): Promise<void>;
    static sendVerificationCode(req: Request, res: Response): Promise<void>;
    static verifyEmail(req: Request, res: Response): Promise<void>;
    static login(req: Request, res: Response): Promise<void>;
    static googleAuth(req: Request, res: Response): Promise<void>;
    static refreshToken(req: Request, res: Response): Promise<void>;
    static resetPassword(req: Request, res: Response): Promise<void>;
    static logout(req: Request, res: Response): Promise<void>;
    static getCurrentUser(req: Request, res: Response): Promise<void>;
    private static allocateClaudeKeyForNewUser;
}
export default AuthController;
//# sourceMappingURL=auth.d.ts.map