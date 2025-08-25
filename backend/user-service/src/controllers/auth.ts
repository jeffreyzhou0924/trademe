import { Request, Response } from 'express';
import { prisma } from '@/config/database';
import { redis } from '@/config/redis';
import { 
  hashPassword, 
  verifyPassword, 
  generateVerificationCode, 
  generateUUID 
} from '@/utils/encryption';
import { 
  generateTokenPair, 
  verifyRefreshToken, 
  JwtPayload 
} from '@/utils/jwt';
import { logger } from '@/utils/logger';
import { 
  BusinessError, 
  AuthenticationError, 
  ConflictError,
  NotFoundError,
  assertExists 
} from '@/middleware/errorHandler';
import { OAuth2Client } from 'google-auth-library';
import { emailService } from '@/services/email.service';

const googleClient = new OAuth2Client(process.env.GOOGLE_CLIENT_ID);

class AuthController {
  /**
   * 用户注册
   */
  static async register(req: Request, res: Response) {
    const { username, email, password } = req.body;

    // 检查邮箱是否已存在
    const existingUser = await prisma.user.findFirst({
      where: {
        OR: [
          { email },
          { username }
        ]
      }
    });

    if (existingUser) {
      if (existingUser.email === email) {
        throw new ConflictError('该邮箱已被注册', 'DUPLICATE_EMAIL');
      } else {
        throw new ConflictError('该用户名已被使用', 'DUPLICATE_USERNAME');
      }
    }

    // 创建用户
    const hashedPassword = await hashPassword(password);
    const user = await prisma.user.create({
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

    // 发送邮箱验证码
    const verificationCode = generateVerificationCode();
    await prisma.emailVerification.create({
      data: {
        userId: user.id,
        email,
        code: verificationCode,
        type: 'REGISTER',
        expiresAt: new Date(Date.now() + 5 * 60 * 1000), // 5分钟后过期
      },
    });

    // 存储验证码到Redis（用于快速验证）
    await redis.setVerificationCode(email, verificationCode, 'register', 300);

    // 发送验证码邮件
    try {
      await emailService.sendVerificationCode(email, verificationCode, 'register');
      logger.info('Registration verification email sent:', { email, userId: user.id });
    } catch (error) {
      logger.error('Failed to send registration verification email:', { email, error });
      // 邮件发送失败不影响注册流程，但记录警告
      logger.warn('用户注册成功但验证码邮件发送失败，验证码为:', verificationCode);
    }

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

  /**
   * 发送验证码
   */
  static async sendVerificationCode(req: Request, res: Response) {
    const { email, type = 'register' } = req.body;

    // 生成验证码
    const code = generateVerificationCode();
    const expiresAt = new Date(Date.now() + 5 * 60 * 1000); // 5分钟后过期

    // 存储到数据库
    await prisma.emailVerification.create({
      data: {
        email,
        code,
        type: type.toUpperCase(),
        expiresAt,
      },
    });

    // 存储到Redis
    await redis.setVerificationCode(email, code, type, 300);

    // 发送验证码邮件
    try {
      await emailService.sendVerificationCode(email, code, type as any);
      logger.info('Verification email sent:', { email, type });
    } catch (error) {
      logger.error('Failed to send verification email:', { email, type, error });
      // 邮件发送失败不影响流程，但记录警告
      logger.warn('验证码邮件发送失败，验证码为:', code);
    }

    res.json({
      success: true,
      code: 200,
      message: '验证码已发送',
      data: {
        expires_at: expiresAt.toISOString(),
        resend_after: 60, // 60秒后可重新发送
      },
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }

  /**
   * 验证邮箱
   */
  static async verifyEmail(req: Request, res: Response) {
    const { email, code } = req.body;

    // 从Redis验证
    const storedCode = await redis.getVerificationCode(email, 'register');
    
    if (!storedCode || storedCode !== code) {
      throw new BusinessError('验证码无效或已过期', 'INVALID_VERIFICATION_CODE');
    }

    // 更新用户邮箱验证状态
    const user = await prisma.user.update({
      where: { email },
      data: { emailVerified: true },
      select: { username: true },
    });

    // 删除验证码
    await redis.deleteVerificationCode(email, 'register');
    await prisma.emailVerification.updateMany({
      where: {
        email,
        type: 'REGISTER',
        used: false,
      },
      data: { used: true },
    });

    // 发送欢迎邮件
    try {
      await emailService.sendWelcomeEmail(email, user.username);
      logger.info('Welcome email sent:', { email, username: user.username });
    } catch (error) {
      logger.error('Failed to send welcome email:', { email, error });
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

  /**
   * 用户登录
   */
  static async login(req: Request, res: Response) {
    const { email, password } = req.body;

    // 查找用户
    const user = await prisma.user.findUnique({
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
      throw new AuthenticationError('邮箱或密码错误', 'INVALID_CREDENTIALS');
    }

    if (!user.isActive) {
      throw new AuthenticationError('账户已被禁用', 'ACCOUNT_DISABLED');
    }

    // 验证密码
    if (!user.passwordHash || !(await verifyPassword(password, user.passwordHash))) {
      throw new AuthenticationError('邮箱或密码错误', 'INVALID_CREDENTIALS');
    }

    // 生成令牌
    const tokens = generateTokenPair({
      userId: user.id.toString(),
      email: user.email,
      membershipLevel: user.membershipLevel,
    });

    // 创建会话
    const sessionId = generateUUID();
    await prisma.userSession.create({
      data: {
        userId: user.id,
        token: tokens.accessToken,
        refreshToken: tokens.refreshToken,
        expiresAt: new Date(Date.now() + tokens.expiresIn * 1000),
        ipAddress: req.ip,
        userAgent: req.get('User-Agent') || '',
      },
    });

    // 更新最后登录时间
    await prisma.user.update({
      where: { id: user.id },
      data: { lastLoginAt: new Date() },
    });

    // 记录登录日志
    logger.info('User logged in:', {
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

  /**
   * Google OAuth登录
   */
  static async googleAuth(req: Request, res: Response) {
    const { google_token } = req.body;

    try {
      // 验证Google令牌
      const ticket = await googleClient.verifyIdToken({
        idToken: google_token,
        audience: process.env.GOOGLE_CLIENT_ID,
      });

      const payload = ticket.getPayload();
      if (!payload) {
        throw new AuthenticationError('Google令牌验证失败', 'INVALID_GOOGLE_TOKEN');
      }

      const { sub: googleId, email, name, picture } = payload;
      
      if (!email) {
        throw new BusinessError('无法获取Google账户邮箱', 'MISSING_GOOGLE_EMAIL');
      }

      // 查找或创建用户
      let user = await prisma.user.findFirst({
        where: {
          OR: [
            { googleId },
            { email },
          ],
        },
      });

      if (!user) {
        // 创建新用户
        user = await prisma.user.create({
          data: {
            username: name || `user_${Date.now()}`,
            email,
            googleId,
            avatarUrl: picture,
            emailVerified: true, // Google账户默认已验证
            preferences: JSON.stringify({
              language: 'zh-CN',
              timezone: 'Asia/Shanghai',
              theme: 'light',
            }),
          },
        });
      } else if (!user.googleId) {
        // 绑定Google账户到已存在用户
        user = await prisma.user.update({
          where: { id: user.id },
          data: { 
            googleId,
            emailVerified: true,
            avatarUrl: user.avatarUrl || picture,
          },
        });
      }

      if (!user.isActive) {
        throw new AuthenticationError('账户已被禁用', 'ACCOUNT_DISABLED');
      }

      // 生成令牌（与普通登录相同的逻辑）
      const tokens = generateTokenPair({
        userId: user.id.toString(),
        email: user.email,
        membershipLevel: user.membershipLevel,
      });

      // 创建会话
      await prisma.userSession.create({
        data: {
          userId: user.id,
          token: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          expiresAt: new Date(Date.now() + tokens.expiresIn * 1000),
          ipAddress: req.ip,
          userAgent: req.get('User-Agent') || '',
        },
      });

      // 更新最后登录时间
      await prisma.user.update({
        where: { id: user.id },
        data: { lastLoginAt: new Date() },
      });

      logger.info('User logged in via Google:', {
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

    } catch (error) {
      logger.error('Google OAuth error:', error);
      if (error instanceof AuthenticationError || error instanceof BusinessError) {
        throw error;
      }
      throw new AuthenticationError('Google登录失败', 'GOOGLE_AUTH_FAILED');
    }
  }

  /**
   * 刷新令牌
   */
  static async refreshToken(req: Request, res: Response) {
    const { refresh_token } = req.body;

    // 验证刷新令牌
    let decoded: JwtPayload;
    try {
      decoded = verifyRefreshToken(refresh_token);
    } catch (error) {
      throw new AuthenticationError('刷新令牌无效或已过期', 'INVALID_REFRESH_TOKEN');
    }

    // 查找会话
    const session = await prisma.userSession.findFirst({
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
      throw new AuthenticationError('无效的刷新令牌', 'INVALID_REFRESH_TOKEN');
    }

    // 生成新令牌
    const tokens = generateTokenPair({
      userId: session.user.id.toString(),
      email: session.user.email,
      membershipLevel: session.user.membershipLevel,
    });

    // 更新会话
    await prisma.userSession.update({
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

  /**
   * 重置密码
   */
  static async resetPassword(req: Request, res: Response) {
    const { email, code, new_password } = req.body;

    // 验证验证码
    const storedCode = await redis.getVerificationCode(email, 'reset_password');
    
    if (!storedCode || storedCode !== code) {
      throw new BusinessError('验证码无效或已过期', 'INVALID_VERIFICATION_CODE');
    }

    // 查找用户
    const user = await prisma.user.findUnique({
      where: { email },
      select: { id: true, username: true },
    });

    if (!user) {
      throw new NotFoundError('用户');
    }

    // 更新密码
    const hashedPassword = await hashPassword(new_password);
    await prisma.user.update({
      where: { id: user.id },
      data: { passwordHash: hashedPassword },
    });

    // 删除验证码
    await redis.deleteVerificationCode(email, 'reset_password');
    
    // 使所有会话失效
    await prisma.userSession.updateMany({
      where: { userId: user.id },
      data: { isActive: false },
    });

    // 发送密码重置成功通知邮件
    try {
      await emailService.sendPasswordResetNotification(email, user.username);
      logger.info('Password reset notification sent:', { email, username: user.username });
    } catch (error) {
      logger.error('Failed to send password reset notification:', { email, error });
    }

    logger.info('Password reset successful:', { userId: user.id.toString(), email });

    res.json({
      success: true,
      code: 200,
      message: '密码重置成功',
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }

  /**
   * 用户登出
   */
  static async logout(req: Request, res: Response) {
    const token = req.token!;
    
    // 将令牌加入黑名单
    await redis.set(`blacklist:token:${token}`, '1', 24 * 60 * 60); // 24小时

    // 使会话失效
    await prisma.userSession.updateMany({
      where: { 
        userId: Number(req.user!.id),
        token,
      },
      data: { isActive: false },
    });

    logger.info('User logged out:', { userId: req.user!.id });

    res.json({
      success: true,
      code: 200,
      message: '登出成功',
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }

  /**
   * 获取当前用户信息
   */
  static async getCurrentUser(req: Request, res: Response) {
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
}

export default AuthController;