"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../config/database");
const redis_1 = require("../config/redis");
const encryption_1 = require("../utils/encryption");
const jwt_1 = require("../utils/jwt");
const logger_1 = require("../utils/logger");
const errorHandler_1 = require("../middleware/errorHandler");
const google_auth_library_1 = require("google-auth-library");
const email_service_1 = require("../services/email.service");
const wallet_service_1 = require("../services/wallet.service");
const googleClient = new google_auth_library_1.OAuth2Client(process.env.GOOGLE_CLIENT_ID);
class AuthController {
    static async register(req, res) {
        const { username, email, password } = req.body;
        const existingUser = await database_1.prisma.user.findFirst({
            where: {
                OR: [
                    { email },
                    { username }
                ]
            }
        });
        if (existingUser) {
            if (existingUser.email === email) {
                throw new errorHandler_1.ConflictError('该邮箱已被注册', 'DUPLICATE_EMAIL');
            }
            else {
                throw new errorHandler_1.ConflictError('该用户名已被使用', 'DUPLICATE_USERNAME');
            }
        }
        const hashedPassword = await (0, encryption_1.hashPassword)(password);
        const user = await database_1.prisma.user.create({
            data: {
                username,
                email,
                passwordHash: hashedPassword,
                preferences: JSON.stringify({
                    language: 'zh-CN',
                    timezone: 'Asia/Shanghai',
                    theme: 'light',
                }),
            },
            select: {
                id: true,
                username: true,
                email: true,
                membershipLevel: true,
                createdAt: true,
            },
        });
        const verificationCode = (0, encryption_1.generateVerificationCode)();
        await database_1.prisma.emailVerification.create({
            data: {
                userId: user.id,
                email,
                code: verificationCode,
                type: 'REGISTER',
                expiresAt: new Date(Date.now() + 5 * 60 * 1000),
            },
        });
        await redis_1.redis.setVerificationCode(email, verificationCode, 'register', 300);
        try {
            await email_service_1.emailService.sendVerificationCode(email, verificationCode, 'register');
            logger_1.logger.info('Registration verification email sent:', { email, userId: user.id });
        }
        catch (error) {
            logger_1.logger.error('Failed to send registration verification email:', { email, error });
            logger_1.logger.warn('用户注册成功但验证码邮件发送失败，验证码为:', verificationCode);
        }
        AuthController.allocateClaudeKeyForNewUser(user.id).catch(error => {
            logger_1.logger.error('Failed to allocate Claude API key for new user:', {
                userId: user.id,
                email: user.email,
                error
            });
        });
        wallet_service_1.WalletService.allocateWalletsForNewUser(user.id, user.email).catch(error => {
            logger_1.logger.error('Failed to allocate wallets for new user:', {
                userId: user.id,
                email: user.email,
                error
            });
        });
        res.status(201).json({
            success: true,
            code: 201,
            message: '注册成功，请查收邮箱验证码',
            data: {
                user_id: user.id.toString(),
                email: user.email,
                verification_required: true,
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async sendVerificationCode(req, res) {
        const { email, type = 'register' } = req.body;
        const code = (0, encryption_1.generateVerificationCode)();
        const expiresAt = new Date(Date.now() + 5 * 60 * 1000);
        await database_1.prisma.emailVerification.create({
            data: {
                email,
                code,
                type: type.toUpperCase(),
                expiresAt,
            },
        });
        await redis_1.redis.setVerificationCode(email, code, type, 300);
        try {
            await email_service_1.emailService.sendVerificationCode(email, code, type);
            logger_1.logger.info('Verification email sent:', { email, type });
        }
        catch (error) {
            logger_1.logger.error('Failed to send verification email:', { email, type, error });
            logger_1.logger.warn('验证码邮件发送失败，验证码为:', code);
        }
        res.json({
            success: true,
            code: 200,
            message: '验证码已发送',
            data: {
                expires_at: expiresAt.toISOString(),
                resend_after: 60,
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async verifyEmail(req, res) {
        const { email, code } = req.body;
        const storedCode = await redis_1.redis.getVerificationCode(email, 'register');
        if (!storedCode || storedCode !== code) {
            throw new errorHandler_1.BusinessError('验证码无效或已过期', 'INVALID_VERIFICATION_CODE');
        }
        const user = await database_1.prisma.user.update({
            where: { email },
            data: { emailVerified: true },
            select: { username: true },
        });
        await redis_1.redis.deleteVerificationCode(email, 'register');
        await database_1.prisma.emailVerification.updateMany({
            where: {
                email,
                type: 'REGISTER',
                used: false,
            },
            data: { used: true },
        });
        try {
            await email_service_1.emailService.sendWelcomeEmail(email, user.username);
            logger_1.logger.info('Welcome email sent:', { email, username: user.username });
        }
        catch (error) {
            logger_1.logger.error('Failed to send welcome email:', { email, error });
        }
        res.json({
            success: true,
            code: 200,
            message: '邮箱验证成功',
            data: {
                verified: true,
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async login(req, res) {
        const { email, password } = req.body;
        const user = await database_1.prisma.user.findUnique({
            where: { email },
            select: {
                id: true,
                username: true,
                email: true,
                passwordHash: true,
                membershipLevel: true,
                membershipExpiresAt: true,
                isActive: true,
                emailVerified: true,
                avatarUrl: true,
                createdAt: true,
            },
        });
        if (!user) {
            throw new errorHandler_1.AuthenticationError('邮箱或密码错误', 'INVALID_CREDENTIALS');
        }
        if (!user.isActive) {
            throw new errorHandler_1.AuthenticationError('账户已被禁用', 'ACCOUNT_DISABLED');
        }
        if (!user.passwordHash || !(await (0, encryption_1.verifyPassword)(password, user.passwordHash))) {
            throw new errorHandler_1.AuthenticationError('邮箱或密码错误', 'INVALID_CREDENTIALS');
        }
        const tokens = (0, jwt_1.generateTokenPair)({
            userId: user.id.toString(),
            email: user.email,
            membershipLevel: user.membershipLevel,
        });
        const sessionId = (0, encryption_1.generateUUID)();
        await database_1.prisma.userSession.create({
            data: {
                userId: user.id,
                token: tokens.accessToken,
                refreshToken: tokens.refreshToken,
                expiresAt: new Date(Date.now() + tokens.expiresIn * 1000),
                ipAddress: req.ip,
                userAgent: req.get('User-Agent') || '',
            },
        });
        await database_1.prisma.user.update({
            where: { id: user.id },
            data: { lastLoginAt: new Date() },
        });
        logger_1.logger.info('User logged in:', {
            userId: user.id.toString(),
            email: user.email,
            ip: req.ip,
            userAgent: req.get('User-Agent'),
        });
        res.json({
            success: true,
            code: 200,
            message: '登录成功',
            data: {
                access_token: tokens.accessToken,
                refresh_token: tokens.refreshToken,
                token_type: 'Bearer',
                expires_in: tokens.expiresIn,
                user: {
                    id: user.id.toString(),
                    username: user.username,
                    email: user.email,
                    avatar_url: user.avatarUrl,
                    membership_level: user.membershipLevel,
                    membership_expires_at: user.membershipExpiresAt?.toISOString(),
                    email_verified: user.emailVerified,
                    created_at: user.createdAt.toISOString(),
                },
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async googleAuth(req, res) {
        const { google_token } = req.body;
        try {
            const ticket = await googleClient.verifyIdToken({
                idToken: google_token,
                audience: process.env.GOOGLE_CLIENT_ID,
            });
            const payload = ticket.getPayload();
            if (!payload) {
                throw new errorHandler_1.AuthenticationError('Google令牌验证失败', 'INVALID_GOOGLE_TOKEN');
            }
            const { sub: googleId, email, name, picture } = payload;
            if (!email) {
                throw new errorHandler_1.BusinessError('无法获取Google账户邮箱', 'MISSING_GOOGLE_EMAIL');
            }
            let user = await database_1.prisma.user.findFirst({
                where: {
                    OR: [
                        { googleId },
                        { email },
                    ],
                },
            });
            if (!user) {
                user = await database_1.prisma.user.create({
                    data: {
                        username: name || `user_${Date.now()}`,
                        email,
                        googleId,
                        avatarUrl: picture,
                        emailVerified: true,
                        preferences: JSON.stringify({
                            language: 'zh-CN',
                            timezone: 'Asia/Shanghai',
                            theme: 'light',
                        }),
                    },
                });
                if (user) {
                    const userId = user.id;
                    const userEmail = user.email;
                    AuthController.allocateClaudeKeyForNewUser(userId).catch(error => {
                        logger_1.logger.error('Failed to allocate Claude API key for Google OAuth new user:', {
                            userId,
                            email: userEmail,
                            googleId,
                            error
                        });
                    });
                    wallet_service_1.WalletService.allocateWalletsForNewUser(userId, userEmail).catch(error => {
                        logger_1.logger.error('Failed to allocate wallets for Google OAuth new user:', {
                            userId,
                            email: userEmail,
                            googleId,
                            error
                        });
                    });
                }
            }
            else if (!user.googleId) {
                user = await database_1.prisma.user.update({
                    where: { id: user.id },
                    data: {
                        googleId,
                        emailVerified: true,
                        avatarUrl: user.avatarUrl || picture,
                    },
                });
            }
            if (!user.isActive) {
                throw new errorHandler_1.AuthenticationError('账户已被禁用', 'ACCOUNT_DISABLED');
            }
            const tokens = (0, jwt_1.generateTokenPair)({
                userId: user.id.toString(),
                email: user.email,
                membershipLevel: user.membershipLevel,
            });
            await database_1.prisma.userSession.create({
                data: {
                    userId: user.id,
                    token: tokens.accessToken,
                    refreshToken: tokens.refreshToken,
                    expiresAt: new Date(Date.now() + tokens.expiresIn * 1000),
                    ipAddress: req.ip,
                    userAgent: req.get('User-Agent') || '',
                },
            });
            await database_1.prisma.user.update({
                where: { id: user.id },
                data: { lastLoginAt: new Date() },
            });
            logger_1.logger.info('User logged in via Google:', {
                userId: user.id.toString(),
                email: user.email,
                googleId,
            });
            res.json({
                success: true,
                code: 200,
                message: '登录成功',
                data: {
                    access_token: tokens.accessToken,
                    refresh_token: tokens.refreshToken,
                    token_type: 'Bearer',
                    expires_in: tokens.expiresIn,
                    user: {
                        id: user.id.toString(),
                        username: user.username,
                        email: user.email,
                        avatar_url: user.avatarUrl,
                        membership_level: user.membershipLevel,
                        membership_expires_at: user.membershipExpiresAt?.toISOString(),
                        email_verified: user.emailVerified,
                        created_at: user.createdAt.toISOString(),
                    },
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            logger_1.logger.error('Google OAuth error:', error);
            if (error instanceof errorHandler_1.AuthenticationError || error instanceof errorHandler_1.BusinessError) {
                throw error;
            }
            throw new errorHandler_1.AuthenticationError('Google登录失败', 'GOOGLE_AUTH_FAILED');
        }
    }
    static async refreshToken(req, res) {
        const { refresh_token } = req.body;
        let decoded;
        try {
            decoded = (0, jwt_1.verifyRefreshToken)(refresh_token);
        }
        catch (error) {
            throw new errorHandler_1.AuthenticationError('刷新令牌无效或已过期', 'INVALID_REFRESH_TOKEN');
        }
        const session = await database_1.prisma.userSession.findFirst({
            where: {
                refreshToken: refresh_token,
                isActive: true,
            },
            include: {
                user: {
                    select: {
                        id: true,
                        email: true,
                        membershipLevel: true,
                        isActive: true,
                    },
                },
            },
        });
        if (!session || !session.user.isActive) {
            throw new errorHandler_1.AuthenticationError('无效的刷新令牌', 'INVALID_REFRESH_TOKEN');
        }
        const tokens = (0, jwt_1.generateTokenPair)({
            userId: session.user.id.toString(),
            email: session.user.email,
            membershipLevel: session.user.membershipLevel,
        });
        await database_1.prisma.userSession.update({
            where: { id: session.id },
            data: {
                token: tokens.accessToken,
                refreshToken: tokens.refreshToken,
                expiresAt: new Date(Date.now() + tokens.expiresIn * 1000),
            },
        });
        res.json({
            success: true,
            code: 200,
            message: '令牌刷新成功',
            data: {
                access_token: tokens.accessToken,
                refresh_token: tokens.refreshToken,
                token_type: 'Bearer',
                expires_in: tokens.expiresIn,
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async resetPassword(req, res) {
        const { email, code, new_password } = req.body;
        const storedCode = await redis_1.redis.getVerificationCode(email, 'reset_password');
        if (!storedCode || storedCode !== code) {
            throw new errorHandler_1.BusinessError('验证码无效或已过期', 'INVALID_VERIFICATION_CODE');
        }
        const user = await database_1.prisma.user.findUnique({
            where: { email },
            select: { id: true, username: true },
        });
        if (!user) {
            throw new errorHandler_1.NotFoundError('用户');
        }
        const hashedPassword = await (0, encryption_1.hashPassword)(new_password);
        await database_1.prisma.user.update({
            where: { id: user.id },
            data: { passwordHash: hashedPassword },
        });
        await redis_1.redis.deleteVerificationCode(email, 'reset_password');
        await database_1.prisma.userSession.updateMany({
            where: { userId: user.id },
            data: { isActive: false },
        });
        try {
            await email_service_1.emailService.sendPasswordResetNotification(email, user.username);
            logger_1.logger.info('Password reset notification sent:', { email, username: user.username });
        }
        catch (error) {
            logger_1.logger.error('Failed to send password reset notification:', { email, error });
        }
        logger_1.logger.info('Password reset successful:', { userId: user.id.toString(), email });
        res.json({
            success: true,
            code: 200,
            message: '密码重置成功',
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async logout(req, res) {
        const token = req.token;
        await redis_1.redis.set(`blacklist:token:${token}`, '1', 24 * 60 * 60);
        await database_1.prisma.userSession.updateMany({
            where: {
                userId: Number(req.user.id),
                token,
            },
            data: { isActive: false },
        });
        logger_1.logger.info('User logged out:', { userId: req.user.id });
        res.json({
            success: true,
            code: 200,
            message: '登出成功',
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async getCurrentUser(req, res) {
        const user = await database_1.prisma.user.findUnique({
            where: { id: Number(req.user.id) },
            select: {
                id: true,
                username: true,
                email: true,
                phone: true,
                avatarUrl: true,
                membershipLevel: true,
                membershipExpiresAt: true,
                emailVerified: true,
                isActive: true,
                lastLoginAt: true,
                preferences: true,
                createdAt: true,
                updatedAt: true,
            },
        });
        (0, errorHandler_1.assertExists)(user, '用户');
        if (!user)
            throw new errorHandler_1.NotFoundError('用户不存在');
        res.json({
            success: true,
            code: 200,
            message: '获取成功',
            data: {
                id: user.id.toString(),
                username: user.username,
                email: user.email,
                phone: user.phone,
                avatar_url: user.avatarUrl,
                membership_level: user.membershipLevel,
                membership_expires_at: user.membershipExpiresAt?.toISOString(),
                email_verified: user.emailVerified,
                is_active: user.isActive,
                last_login_at: user.lastLoginAt?.toISOString(),
                preferences: user.preferences,
                created_at: user.createdAt.toISOString(),
                updated_at: user.updatedAt.toISOString(),
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async allocateClaudeKeyForNewUser(userId) {
        try {
            const tradingServiceUrl = process.env.TRADING_SERVICE_URL || 'http://localhost:8001';
            const internalToken = (0, jwt_1.generateAccessToken)({
                userId: userId.toString(),
                email: 'internal@trademe.com',
                membershipLevel: 'basic'
            });
            const response = await fetch(`${tradingServiceUrl}/api/v1/user-claude-keys/auto-allocate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${internalToken}`,
                    'User-Agent': 'Trademe-UserService/1.0'
                },
                body: JSON.stringify({
                    user_id: userId
                })
            });
            if (!response.ok) {
                throw new Error(`Trading service responded with ${response.status}: ${response.statusText}`);
            }
            const result = await response.json();
            logger_1.logger.info('Successfully allocated Claude API key for new user:', {
                userId,
                keyId: result.data?.id,
                virtualKey: result.data?.virtual_key ? `${result.data.virtual_key.substring(0, 10)}...` : 'N/A'
            });
        }
        catch (error) {
            logger_1.logger.error('Failed to allocate Claude API key for new user:', {
                userId,
                error: error instanceof Error ? error.message : 'Unknown error'
            });
        }
    }
}
exports.default = AuthController;
//# sourceMappingURL=auth.js.map