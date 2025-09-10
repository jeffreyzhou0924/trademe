"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WalletService = void 0;
const axios_1 = __importDefault(require("axios"));
const logger_1 = require("../utils/logger");
const jwt_1 = require("../utils/jwt");
const TRADING_SERVICE_URL = process.env.TRADING_SERVICE_URL || 'http://localhost:8001';
class WalletService {
    static async allocateWalletsForNewUser(userId, userEmail) {
        try {
            logger_1.logger.info(`开始为用户 ${userId} (${userEmail}) 分配钱包`);
            const internalToken = (0, jwt_1.generateAccessToken)({
                userId: userId.toString(),
                email: 'internal@trademe.com',
                membershipLevel: 'basic'
            });
            const response = await axios_1.default.post(`${TRADING_SERVICE_URL}/api/v1/user-wallets/admin/user/${userId}/allocate`, {}, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${internalToken}`,
                    'User-Agent': 'Trademe-UserService/1.0'
                },
                timeout: 10000
            });
            if (response.data?.success) {
                const wallets = response.data.data?.wallets || {};
                logger_1.logger.info(`用户 ${userId} 钱包分配成功:`, {
                    userId,
                    userEmail,
                    wallets: Object.keys(wallets).map(network => ({
                        network,
                        address: wallets[network]
                    }))
                });
            }
            else {
                throw new Error(`API响应失败: ${response.data?.message || '未知错误'}`);
            }
        }
        catch (error) {
            logger_1.logger.error(`用户 ${userId} 钱包分配失败:`, {
                userId,
                userEmail,
                error: error instanceof Error ? error.message : String(error),
                stack: error instanceof Error ? error.stack : undefined
            });
        }
    }
    static async getUserWallets(userId) {
        try {
            const internalToken = (0, jwt_1.generateAccessToken)({
                userId: userId.toString(),
                email: 'internal@trademe.com',
                membershipLevel: 'basic'
            });
            const response = await axios_1.default.get(`${TRADING_SERVICE_URL}/api/v1/user-wallets/admin/user/${userId}/wallets`, {
                headers: {
                    'Authorization': `Bearer ${internalToken}`,
                    'User-Agent': 'Trademe-UserService/1.0'
                },
                timeout: 5000
            });
            if (response.data?.success) {
                return response.data.data;
            }
            else {
                throw new Error(`API响应失败: ${response.data?.message || '未知错误'}`);
            }
        }
        catch (error) {
            logger_1.logger.error(`获取用户 ${userId} 钱包信息失败:`, {
                error: error instanceof Error ? error.message : String(error)
            });
            return null;
        }
    }
    static async checkWalletServiceHealth() {
        try {
            const response = await axios_1.default.get(`${TRADING_SERVICE_URL}/health`, {
                timeout: 3000
            });
            return response.status === 200;
        }
        catch (error) {
            logger_1.logger.warn('钱包服务连接检查失败:', {
                error: error instanceof Error ? error.message : String(error)
            });
            return false;
        }
    }
}
exports.WalletService = WalletService;
//# sourceMappingURL=wallet.service.js.map