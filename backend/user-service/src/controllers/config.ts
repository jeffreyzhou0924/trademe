import { Request, Response } from 'express';

class ConfigController {
  /**
   * 获取系统配置
   */
  static async getSystemConfig(req: Request, res: Response) {
    const config = {
      app: {
        name: 'Trademe',
        version: '1.0.0',
        description: '数字货币策略交易平台',
      },
      features: {
        google_oauth_enabled: !!process.env.GOOGLE_CLIENT_ID,
        email_verification_required: true,
        maintenance_mode: false,
      },
      limits: {
        file_upload_max_size: 5242880, // 5MB
        api_rate_limit: 100, // 每分钟
      },
      supported_languages: ['zh-CN', 'en-US'],
      supported_timezones: [
        'Asia/Shanghai',
        'Asia/Hong_Kong',
        'UTC',
      ],
    };

    res.json({
      success: true,
      code: 200,
      message: '获取成功',
      data: config,
      timestamp: new Date().toISOString(),
      request_id: req.headers['x-request-id'],
    });
  }
}

export default ConfigController;