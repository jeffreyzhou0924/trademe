import { Router } from 'express';
import { asyncHandler } from '@/middleware/errorHandler';
import { optionalAuth } from '@/middleware/auth';
import MembershipController from '@/controllers/membership';

const router = Router();

// 获取会员套餐列表（公开接口）
router.get('/plans',
  optionalAuth,
  asyncHandler(MembershipController.getPlans)
);

export default router;