"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../config/database");
const encryption_1 = require("../utils/encryption");
const logger_1 = require("../utils/logger");
const errorHandler_1 = require("../middleware/errorHandler");
const upload_service_1 = require("../services/upload.service");
class UserController {
    static async getProfile(req, res) {
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
    static async updateProfile(req, res) {
        const { username, phone, avatar_url, preferences } = req.body;
        const userId = Number(req.user.id);
        if (username) {
            const existingUser = await database_1.prisma.user.findFirst({
                where: {
                    username,
                    NOT: { id: userId },
                },
            });
            if (existingUser) {
                throw new errorHandler_1.BusinessError('该用户名已被使用', 'DUPLICATE_USERNAME');
            }
        }
        const user = await database_1.prisma.user.update({
            where: { id: userId },
            data: {
                ...(username && { username }),
                ...(phone !== undefined && { phone }),
                ...(avatar_url !== undefined && { avatarUrl: avatar_url }),
                ...(preferences && { preferences }),
            },
            select: {
                id: true,
                username: true,
                email: true,
                phone: true,
                avatarUrl: true,
                membershipLevel: true,
                membershipExpiresAt: true,
                preferences: true,
                updatedAt: true,
            },
        });
        logger_1.logger.info('User profile updated:', { userId: user.id.toString() });
        res.json({
            success: true,
            code: 200,
            message: '更新成功',
            data: {
                id: user.id.toString(),
                username: user.username,
                email: user.email,
                phone: user.phone,
                avatar_url: user.avatarUrl,
                membership_level: user.membershipLevel,
                membership_expires_at: user.membershipExpiresAt?.toISOString(),
                preferences: user.preferences,
                updated_at: user.updatedAt.toISOString(),
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async changePassword(req, res) {
        const { current_password, new_password } = req.body;
        const userId = Number(req.user.id);
        const user = await database_1.prisma.user.findUnique({
            where: { id: userId },
            select: { passwordHash: true },
        });
        (0, errorHandler_1.assertExists)(user, '用户');
        if (!user)
            throw new errorHandler_1.NotFoundError('用户不存在');
        if (!user.passwordHash || !(await (0, encryption_1.verifyPassword)(current_password, user.passwordHash))) {
            throw new errorHandler_1.AuthenticationError('当前密码错误', 'INVALID_CURRENT_PASSWORD');
        }
        const hashedPassword = await (0, encryption_1.hashPassword)(new_password);
        await database_1.prisma.user.update({
            where: { id: userId },
            data: { passwordHash: hashedPassword },
        });
        await database_1.prisma.userSession.updateMany({
            where: {
                userId,
                NOT: { token: req.token },
            },
            data: { isActive: false },
        });
        logger_1.logger.info('Password changed:', { userId: userId.toString() });
        res.json({
            success: true,
            code: 200,
            message: '密码修改成功',
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async bindGoogle(req, res) {
        res.json({
            success: true,
            code: 200,
            message: 'Google账号绑定成功',
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async unbindGoogle(req, res) {
        const userId = Number(req.user.id);
        await database_1.prisma.user.update({
            where: { id: userId },
            data: { googleId: null },
        });
        logger_1.logger.info('Google account unbound:', { userId: userId.toString() });
        res.json({
            success: true,
            code: 200,
            message: 'Google账号解绑成功',
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async uploadAvatar(req, res) {
        const userId = Number(req.user.id);
        if (!req.file) {
            throw new errorHandler_1.BusinessError('请选择要上传的头像文件', 'NO_FILE_UPLOADED');
        }
        try {
            const currentUser = await database_1.prisma.user.findUnique({
                where: { id: userId },
                select: { avatarUrl: true },
            });
            const uploadResult = upload_service_1.uploadService.processUploadResult(req.file, 'avatars');
            const updatedUser = await database_1.prisma.user.update({
                where: { id: userId },
                data: { avatarUrl: uploadResult.url },
                select: {
                    id: true,
                    avatarUrl: true,
                },
            });
            if (currentUser?.avatarUrl) {
                upload_service_1.uploadService.deleteOldAvatar(currentUser.avatarUrl).catch(error => {
                    logger_1.logger.error('Failed to delete old avatar:', {
                        userId: userId.toString(),
                        oldAvatarUrl: currentUser.avatarUrl,
                        error
                    });
                });
            }
            logger_1.logger.info('Avatar uploaded successfully:', {
                userId: userId.toString(),
                filename: uploadResult.filename,
                size: uploadResult.size,
                url: uploadResult.url,
            });
            res.json({
                success: true,
                code: 200,
                message: '头像上传成功',
                data: {
                    url: uploadResult.url,
                    size: uploadResult.size,
                    mime_type: uploadResult.mimeType,
                    filename: uploadResult.filename,
                },
                timestamp: new Date().toISOString(),
                request_id: req.headers['x-request-id'],
            });
        }
        catch (error) {
            if (req.file) {
                upload_service_1.uploadService.deleteFile(req.file.path).catch(cleanupError => {
                    logger_1.logger.error('Failed to cleanup uploaded file after error:', cleanupError);
                });
            }
            logger_1.logger.error('Avatar upload failed:', {
                userId: userId.toString(),
                error,
            });
            throw error;
        }
    }
    static async getUsageStats(req, res) {
        res.json({
            success: true,
            code: 200,
            message: '获取成功',
            data: {
                period: 'day',
                date: new Date().toISOString().split('T')[0],
                stats: {
                    ai_queries: { used: 5, limit: 30, remaining: 25 },
                    ai_optimizations: { used: 1, limit: 5, remaining: 4 },
                    api_requests: 150,
                    strategies_created: 2,
                    backtests_run: 3,
                },
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
    static async getMembershipInfo(req, res) {
        const user = await database_1.prisma.user.findUnique({
            where: { id: Number(req.user.id) },
            select: {
                membershipLevel: true,
                membershipExpiresAt: true,
            },
        });
        (0, errorHandler_1.assertExists)(user, '用户');
        if (!user)
            throw new errorHandler_1.NotFoundError('用户不存在');
        let daysRemaining = 0;
        if (user.membershipExpiresAt) {
            const now = new Date();
            const expiry = user.membershipExpiresAt;
            daysRemaining = Math.max(0, Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
        }
        const features = {
            BASIC: {
                api_keys_limit: 5,
                ai_queries_daily: 2,
                ai_strategy_optimization_daily: 0,
                advanced_charts: false,
                priority_support: false,
            },
            PREMIUM: {
                api_keys_limit: -1,
                ai_queries_daily: 30,
                ai_strategy_optimization_daily: 5,
                advanced_charts: true,
                priority_support: true,
            },
            PROFESSIONAL: {
                api_keys_limit: -1,
                ai_queries_daily: 100,
                ai_strategy_optimization_daily: 20,
                advanced_charts: true,
                priority_support: true,
            },
        };
        res.json({
            success: true,
            code: 200,
            message: '获取成功',
            data: {
                level: user.membershipLevel.toLowerCase(),
                expires_at: user.membershipExpiresAt?.toISOString(),
                days_remaining: daysRemaining,
                features: features[user.membershipLevel],
                usage: {
                    api_keys_count: 3,
                    ai_queries_today: 5,
                    ai_optimizations_today: 1,
                },
            },
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
}
exports.default = UserController;
//# sourceMappingURL=user.js.map