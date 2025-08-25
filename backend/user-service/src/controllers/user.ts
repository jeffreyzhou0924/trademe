import { Request, Response } from 'express';
import { prisma } from '@/config/database';
import { 
  verifyPassword, 
  hashPassword,
} from '@/utils/encryption';
import { logger } from '@/utils/logger';
import { 
  BusinessError, 
  AuthenticationError,
  NotFoundError,
  assertExists 
} from '@/middleware/errorHandler';
import { uploadService } from '@/services/upload.service';

class UserController {
  /**
   * 获取用户信息
   */
  static async getProfile(req: Request, res: Response) {
    const user = await prisma.user.findUnique({
      where: { id: Number(req.user!.id) },
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

    assertExists(user, '用户');
    if (!user) throw new NotFoundError('用户不存在');

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

  /**
   * 更新用户信息
   */
  static async updateProfile(req: Request, res: Response) {
    const { username, phone, avatar_url, preferences } = req.body;
    const userId = Number(req.user!.id);

    // 检查用户名是否已被使用
    if (username) {
      const existingUser = await prisma.user.findFirst({
        where: {
          username,
          NOT: { id: userId },
        },
      });

      if (existingUser) {
        throw new BusinessError('该用户名已被使用', 'DUPLICATE_USERNAME');
      }
    }

    // 更新用户信息
    const user = await prisma.user.update({
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

    logger.info('User profile updated:', { userId: user.id.toString() });

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

  /**
   * 修改密码
   */
  static async changePassword(req: Request, res: Response) {
    const { current_password, new_password } = req.body;
    const userId = Number(req.user!.id);

    // 获取当前用户
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { passwordHash: true },
    });

    assertExists(user, '用户');
    if (!user) throw new NotFoundError('用户不存在');

    // 验证当前密码
    if (!user.passwordHash || !(await verifyPassword(current_password, user.passwordHash))) {
      throw new AuthenticationError('当前密码错误', 'INVALID_CURRENT_PASSWORD');
    }

    // 更新密码
    const hashedPassword = await hashPassword(new_password);
    await prisma.user.update({
      where: { id: userId },
      data: { passwordHash: hashedPassword },
    });

    // 使所有会话失效（除了当前会话）
    await prisma.userSession.updateMany({
      where: { 
        userId,
        NOT: { token: req.token! },
      },
      data: { isActive: false },
    });

    logger.info('Password changed:', { userId: userId.toString() });

    res.json({
      success: true,
      code: 200,
      message: '密码修改成功',
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }

  /**
   * 绑定Google账号
   */
  static async bindGoogle(req: Request, res: Response) {
    // TODO: 实现Google账号绑定逻辑
    res.json({
      success: true,
      code: 200,
      message: 'Google账号绑定成功',
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }

  /**
   * 解绑Google账号
   */
  static async unbindGoogle(req: Request, res: Response) {
    const userId = Number(req.user!.id);

    await prisma.user.update({
      where: { id: userId },
      data: { googleId: null },
    });

    logger.info('Google account unbound:', { userId: userId.toString() });

    res.json({
      success: true,
      code: 200,
      message: 'Google账号解绑成功',
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }

  /**
   * 上传头像
   */
  static async uploadAvatar(req: Request, res: Response) {
    const userId = Number(req.user!.id);

    if (!req.file) {
      throw new BusinessError('请选择要上传的头像文件', 'NO_FILE_UPLOADED');
    }

    try {
      // 获取当前用户的头像URL（用于删除旧头像）
      const currentUser = await prisma.user.findUnique({
        where: { id: userId },
        select: { avatarUrl: true },
      });

      // 处理上传结果
      const uploadResult = uploadService.processUploadResult(req.file, 'avatars');

      // 更新数据库中的头像URL
      const updatedUser = await prisma.user.update({
        where: { id: userId },
        data: { avatarUrl: uploadResult.url },
        select: {
          id: true,
          avatarUrl: true,
        },
      });

      // 删除旧头像文件（如果存在且不是默认头像）
      if (currentUser?.avatarUrl) {
        uploadService.deleteOldAvatar(currentUser.avatarUrl).catch(error => {
          logger.error('Failed to delete old avatar:', { 
            userId: userId.toString(), 
            oldAvatarUrl: currentUser.avatarUrl,
            error 
          });
        });
      }

      logger.info('Avatar uploaded successfully:', {
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

    } catch (error) {
      // 出错时清理上传的文件
      if (req.file) {
        uploadService.deleteFile(req.file.path).catch(cleanupError => {
          logger.error('Failed to cleanup uploaded file after error:', cleanupError);
        });
      }

      logger.error('Avatar upload failed:', {
        userId: userId.toString(),
        error,
      });

      throw error; // 重新抛出错误，由错误处理中间件处理
    }
  }

  /**
   * 获取使用量统计
   */
  static async getUsageStats(req: Request, res: Response) {
    // TODO: 实现使用量统计逻辑
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

  /**
   * 获取会员信息
   */
  static async getMembershipInfo(req: Request, res: Response) {
    const user = await prisma.user.findUnique({
      where: { id: Number(req.user!.id) },
      select: {
        membershipLevel: true,
        membershipExpiresAt: true,
      },
    });

    assertExists(user, '用户');
    if (!user) throw new NotFoundError('用户不存在');

    // 计算剩余天数
    let daysRemaining = 0;
    if (user.membershipExpiresAt) {
      const now = new Date();
      const expiry = user.membershipExpiresAt;
      daysRemaining = Math.max(0, Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
    }

    // 根据会员等级设置权益
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
        features: features[user.membershipLevel as keyof typeof features],
        usage: {
          api_keys_count: 3, // TODO: 从实际数据获取
          ai_queries_today: 5,
          ai_optimizations_today: 1,
        },
      },
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }
}

export default UserController;