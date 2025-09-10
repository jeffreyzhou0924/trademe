"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
class ConfigController {
    static async getSystemConfig(req, res) {
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
                file_upload_max_size: 5242880,
                api_rate_limit: 100,
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
exports.default = ConfigController;
//# sourceMappingURL=config.js.map