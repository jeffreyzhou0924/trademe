"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.emailService = void 0;
const nodemailer_1 = __importDefault(require("nodemailer"));
const logger_1 = require("../utils/logger");
class EmailService {
    constructor() {
        this.config = {
            from: process.env.EMAIL_FROM || 'noreply@trademe.com',
            replyTo: process.env.EMAIL_REPLY_TO || 'support@trademe.com',
        };
        this.transporter = nodemailer_1.default.createTransport({
            host: process.env.SMTP_HOST || 'smtp.gmail.com',
            port: parseInt(process.env.SMTP_PORT || '587'),
            secure: process.env.SMTP_SECURE === 'true',
            auth: {
                user: process.env.SMTP_USER,
                pass: process.env.SMTP_PASS,
            },
            pool: true,
            maxConnections: 5,
            maxMessages: 100,
            rateDelta: 1000,
            rateLimit: 5,
        });
        this.verifyConnection();
    }
    static getInstance() {
        if (!EmailService.instance) {
            EmailService.instance = new EmailService();
        }
        return EmailService.instance;
    }
    async verifyConnection() {
        try {
            await this.transporter.verify();
            logger_1.logger.info('邮件服务连接验证成功');
        }
        catch (error) {
            logger_1.logger.error('邮件服务连接验证失败:', error);
            logger_1.logger.warn('邮件服务不可用，请检查SMTP配置');
        }
    }
    async sendEmail(to, template, options) {
        try {
            const mailOptions = {
                from: this.config.from,
                to: Array.isArray(to) ? to.join(', ') : to,
                replyTo: this.config.replyTo,
                subject: template.subject,
                html: template.html,
                text: template.text,
                ...options,
            };
            const info = await this.transporter.sendMail(mailOptions);
            logger_1.logger.info('邮件发送成功:', {
                messageId: info.messageId,
                to: mailOptions.to,
                subject: template.subject,
            });
            return true;
        }
        catch (error) {
            logger_1.logger.error('邮件发送失败:', {
                to,
                subject: template.subject,
                error: error instanceof Error ? error.message : error,
            });
            return false;
        }
    }
    async sendVerificationCode(email, code, type = 'register') {
        const templates = {
            register: {
                subject: '【Trademe】邮箱验证码',
                html: this.getVerificationEmailHtml(code, '注册账户', '感谢您注册Trademe数字货币交易平台！'),
            },
            login: {
                subject: '【Trademe】登录验证码',
                html: this.getVerificationEmailHtml(code, '登录账户', '您正在登录Trademe数字货币交易平台'),
            },
            reset_password: {
                subject: '【Trademe】密码重置验证码',
                html: this.getVerificationEmailHtml(code, '重置密码', '您正在重置Trademe账户密码'),
            },
        };
        return await this.sendEmail(email, templates[type]);
    }
    async sendWelcomeEmail(email, username) {
        const template = {
            subject: '欢迎加入Trademe数字货币交易平台！',
            html: this.getWelcomeEmailHtml(username),
        };
        return await this.sendEmail(email, template);
    }
    async sendPasswordResetNotification(email, username) {
        const template = {
            subject: '【Trademe】密码重置成功通知',
            html: this.getPasswordResetNotificationHtml(username),
        };
        return await this.sendEmail(email, template);
    }
    getVerificationEmailHtml(code, action, description) {
        return `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>邮箱验证码</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
            .content { padding: 40px 30px; text-align: center; }
            .verification-code { background: #f8f9fa; border: 2px dashed #dee2e6; border-radius: 8px; padding: 20px; margin: 30px 0; font-size: 32px; font-weight: bold; color: #495057; letter-spacing: 4px; }
            .footer { background: #f8f9fa; padding: 20px 30px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6c757d; }
            .warning { color: #dc3545; font-size: 14px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Trademe</h1>
                <p>数字货币策略交易平台</p>
            </div>
            <div class="content">
                <h2>${action}</h2>
                <p>${description}</p>
                <p>您的验证码是：</p>
                <div class="verification-code">${code}</div>
                <p>验证码5分钟内有效，请尽快使用。</p>
                <div class="warning">
                    <p>⚠️ 请勿将验证码告诉他人，Trademe工作人员不会主动索要您的验证码。</p>
                </div>
            </div>
            <div class="footer">
                <p>如果您没有进行此操作，请忽略此邮件。</p>
                <p>© 2024 Trademe. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    `;
    }
    getWelcomeEmailHtml(username) {
        return `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>欢迎加入Trademe</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
            .content { padding: 40px 30px; }
            .feature { margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #667eea; }
            .footer { background: #f8f9fa; padding: 20px 30px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6c757d; }
            .button { display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 欢迎加入Trademe！</h1>
                <p>数字货币策略交易平台</p>
            </div>
            <div class="content">
                <h2>亲爱的 ${username}，</h2>
                <p>恭喜您成功注册Trademe账户！我们很高兴为您提供专业的数字货币策略交易服务。</p>
                
                <div class="feature">
                    <h3>🚀 AI智能策略</h3>
                    <p>使用人工智能生成和优化交易策略</p>
                </div>
                
                <div class="feature">
                    <h3>📊 回测分析</h3>
                    <p>全面的历史数据回测和风险评估</p>
                </div>
                
                <div class="feature">
                    <h3>⚡ 实时交易</h3>
                    <p>支持多交易所的实时自动化交易</p>
                </div>
                
                <div class="feature">
                    <h3>🎯 精准信号</h3>
                    <p>基于技术分析的精准交易信号</p>
                </div>
                
                <p>现在就开始您的交易之旅：</p>
                <a href="${process.env.FRONTEND_URL || 'https://trademe.com'}" class="button">立即体验</a>
                
                <p>如果您有任何问题，随时联系我们的客服团队。</p>
            </div>
            <div class="footer">
                <p>祝您交易愉快！</p>
                <p>© 2024 Trademe. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    `;
    }
    getPasswordResetNotificationHtml(username) {
        return `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>密码重置成功</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
            .content { padding: 40px 30px; }
            .footer { background: #f8f9fa; padding: 20px 30px; border-radius: 0 0 8px 8px; text-align: center; font-size: 14px; color: #6c757d; }
            .warning { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 6px; padding: 15px; margin: 20px 0; color: #856404; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ 密码重置成功</h1>
                <p>Trademe 安全通知</p>
            </div>
            <div class="content">
                <h2>亲爱的 ${username}，</h2>
                <p>您的Trademe账户密码已成功重置。</p>
                <p><strong>重置时间：</strong>${new Date().toLocaleString('zh-CN')}</p>
                
                <div class="warning">
                    <h3>🛡️ 安全提醒</h3>
                    <ul>
                        <li>如果这不是您本人的操作，请立即联系客服</li>
                        <li>建议您使用强密码并定期更换</li>
                        <li>请勿将密码告诉他人</li>
                        <li>建议开启双重认证提高账户安全性</li>
                    </ul>
                </div>
                
                <p>您现在可以使用新密码登录账户。</p>
            </div>
            <div class="footer">
                <p>如有疑问，请联系客服：support@trademe.com</p>
                <p>© 2024 Trademe. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    `;
    }
    async close() {
        try {
            this.transporter.close();
            logger_1.logger.info('邮件服务连接已关闭');
        }
        catch (error) {
            logger_1.logger.error('关闭邮件服务连接失败:', error);
        }
    }
    async healthCheck() {
        try {
            await this.transporter.verify();
            return true;
        }
        catch (error) {
            logger_1.logger.error('邮件服务健康检查失败:', error);
            return false;
        }
    }
}
exports.emailService = EmailService.getInstance();
//# sourceMappingURL=email.service.js.map