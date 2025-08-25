import { Router } from 'express';
import { asyncHandler } from '@/middleware/errorHandler';
import ConfigController from '@/controllers/config';

const router = Router();

// 获取系统配置（公开接口）
router.get('/', asyncHandler(ConfigController.getSystemConfig));

export default router;