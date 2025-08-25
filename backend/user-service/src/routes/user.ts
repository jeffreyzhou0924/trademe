import { Router } from 'express';
import { updateProfileSchema, changePasswordSchema, googleAuthSchema } from '@/utils/validation';
import { validateBody } from '@/middleware/validation';
import { asyncHandler } from '@/middleware/errorHandler';
import { authenticateToken, requireEmailVerification } from '@/middleware/auth';
import { fileUploadRateLimit } from '@/middleware/rateLimit';
import { avatarUpload, validateImage, cleanupOnError } from '@/middleware/upload';
import UserController from '@/controllers/user';

const router = Router();

// 所有用户路由都需要认证
router.use(authenticateToken);

// 获取用户信息
router.get('/profile', asyncHandler(UserController.getProfile));

// 更新用户信息
router.put('/profile',
  validateBody(updateProfileSchema),
  asyncHandler(UserController.updateProfile)
);

// 修改密码
router.put('/change-password',
  validateBody(changePasswordSchema),
  asyncHandler(UserController.changePassword)
);

// 绑定Google账号
router.post('/bind-google',
  validateBody(googleAuthSchema),
  asyncHandler(UserController.bindGoogle)
);

// 解绑Google账号
router.delete('/unbind-google',
  asyncHandler(UserController.unbindGoogle)
);

// 上传头像
router.post('/upload-avatar',
  fileUploadRateLimit,
  cleanupOnError,
  avatarUpload,
  validateImage,
  asyncHandler(UserController.uploadAvatar)
);

// 获取使用量统计
router.get('/usage-stats',
  asyncHandler(UserController.getUsageStats)
);

// 获取会员信息
router.get('/membership',
  asyncHandler(UserController.getMembershipInfo)
);

export default router;