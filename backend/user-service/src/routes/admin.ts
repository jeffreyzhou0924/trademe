import { Router } from 'express';
import { paginationSchema } from '@/utils/validation';
import { validateQuery } from '@/middleware/validation';
import { asyncHandler } from '@/middleware/errorHandler';
import { authenticateToken, requireAdmin } from '@/middleware/auth';
import AdminController from '@/controllers/admin';

const router = Router();

// 所有管理员路由都需要认证和管理员权限
router.use(authenticateToken);
router.use(requireAdmin);

// 获取用户列表
router.get('/users',
  validateQuery(paginationSchema),
  asyncHandler(AdminController.getUsers)
);

// 获取用户详情
router.get('/users/:userId',
  asyncHandler(AdminController.getUserDetail)
);

// 更新用户信息
router.put('/users/:userId',
  asyncHandler(AdminController.updateUser)
);

// 获取系统统计信息
router.get('/stats/system',
  asyncHandler(AdminController.getSystemStats)
);

// 获取用户活动日志
router.get('/users/:userId/activities',
  validateQuery(paginationSchema),
  asyncHandler(AdminController.getUserActivities)
);

// 获取用户会员使用统计
router.get('/users/:userId/membership-stats',
  asyncHandler(AdminController.getUserMembershipStats)
);

// 批量更新用户状态
router.patch('/users/batch',
  asyncHandler(AdminController.batchUpdateUsers)
);

// 获取会员级别分析
router.get('/analytics/membership',
  asyncHandler(AdminController.getMembershipAnalytics)
);

// === Claude AI服务管理路由 ===

// 获取Claude账号列表
router.get('/claude/accounts',
  asyncHandler(AdminController.getClaudeAccounts)
);

// 添加Claude账号
router.post('/claude/accounts',
  asyncHandler(AdminController.addClaudeAccount)
);

// 更新Claude账号
router.put('/claude/accounts/:accountId',
  asyncHandler(AdminController.updateClaudeAccount)
);

// 删除Claude账号
router.delete('/claude/accounts/:accountId',
  asyncHandler(AdminController.deleteClaudeAccount)
);

// 测试Claude账号连接
router.post('/claude/accounts/:accountId/test',
  asyncHandler(AdminController.testClaudeAccount)
);

// 获取Claude使用统计
router.get('/claude/usage-stats',
  asyncHandler(AdminController.getClaudeUsageStats)
);

// 获取代理服务器列表
router.get('/proxies',
  asyncHandler(AdminController.getProxies)
);

// 获取调度器配置
router.get('/scheduler/config',
  asyncHandler(AdminController.getSchedulerConfig)
);

// 更新调度器配置
router.put('/scheduler/config',
  asyncHandler(AdminController.updateSchedulerConfig)
);

// 获取AI异常检测报告
router.get('/claude/anomaly-detection',
  asyncHandler(AdminController.getAIAnomalyDetection)
);

export default router;