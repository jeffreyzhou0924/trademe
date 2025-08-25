import { Router } from 'express';
import { 
  registerSchema,
  loginSchema,
  googleAuthSchema,
  sendVerificationSchema,
  verifyEmailSchema,
  refreshTokenSchema,
  resetPasswordSchema,
} from '@/utils/validation';
import { validateBody } from '@/middleware/validation';
import { 
  authRateLimit,
  verificationCodeRateLimit,
  passwordResetRateLimit 
} from '@/middleware/rateLimit';
import { asyncHandler } from '@/middleware/errorHandler';
import { authenticateToken } from '@/middleware/auth';
import AuthController from '@/controllers/auth';

const router = Router();

// 用户注册
router.post('/register',
  authRateLimit,
  validateBody(registerSchema),
  asyncHandler(AuthController.register)
);

// 发送验证码
router.post('/send-verification',
  verificationCodeRateLimit,
  validateBody(sendVerificationSchema),
  asyncHandler(AuthController.sendVerificationCode)
);

// 邮箱验证
router.post('/verify-email',
  validateBody(verifyEmailSchema),
  asyncHandler(AuthController.verifyEmail)
);

// 用户登录
router.post('/login',
  authRateLimit,
  validateBody(loginSchema),
  asyncHandler(AuthController.login)
);

// Google OAuth登录
router.post('/google',
  authRateLimit,
  validateBody(googleAuthSchema),
  asyncHandler(AuthController.googleAuth)
);

// 刷新令牌
router.post('/refresh',
  validateBody(refreshTokenSchema),
  asyncHandler(AuthController.refreshToken)
);

// 重置密码
router.post('/reset-password',
  passwordResetRateLimit,
  validateBody(resetPasswordSchema),
  asyncHandler(AuthController.resetPassword)
);

// 用户登出
router.post('/logout',
  authenticateToken,
  asyncHandler(AuthController.logout)
);

// 检查认证状态
router.get('/me',
  authenticateToken,
  asyncHandler(AuthController.getCurrentUser)
);

export default router;