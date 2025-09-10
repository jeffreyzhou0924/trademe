/**
 * 钱包服务集成
 * 与交易服务的用户钱包管理API集成
 */

import axios from 'axios';
import { logger } from '@/utils/logger';
import { generateAccessToken } from '@/utils/jwt';

const TRADING_SERVICE_URL = process.env.TRADING_SERVICE_URL || 'http://localhost:8001';

export class WalletService {
  /**
   * 为新用户分配钱包
   * @param userId 用户ID
   * @param userEmail 用户邮箱（用于日志记录）
   */
  static async allocateWalletsForNewUser(userId: number, userEmail: string): Promise<void> {
    try {
      logger.info(`开始为用户 ${userId} (${userEmail}) 分配钱包`);
      
      // 生成内部服务调用的JWT Token
      const internalToken = generateAccessToken({
        userId: userId.toString(),
        email: 'internal@trademe.com',
        membershipLevel: 'basic'
      });
      
      // 调用交易服务的钱包分配API
      const response = await axios.post(
        `${TRADING_SERVICE_URL}/api/v1/user-wallets/admin/user/${userId}/allocate`,
        {},
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${internalToken}`,
            'User-Agent': 'Trademe-UserService/1.0'
          },
          timeout: 10000 // 10秒超时
        }
      );

      if (response.data?.success) {
        const wallets = response.data.data?.wallets || {};
        logger.info(`用户 ${userId} 钱包分配成功:`, {
          userId,
          userEmail,
          wallets: Object.keys(wallets).map(network => ({
            network,
            address: wallets[network]
          }))
        });
      } else {
        throw new Error(`API响应失败: ${response.data?.message || '未知错误'}`);
      }
      
    } catch (error) {
      logger.error(`用户 ${userId} 钱包分配失败:`, {
        userId,
        userEmail,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined
      });
      
      // 钱包分配失败不应该阻止用户注册，只记录错误
      // 可以后续通过管理后台手动分配
    }
  }

  /**
   * 获取用户钱包信息
   * @param userId 用户ID
   * @returns 用户钱包信息
   */
  static async getUserWallets(userId: number): Promise<any> {
    try {
      // 生成内部服务调用的JWT Token
      const internalToken = generateAccessToken({
        userId: userId.toString(),
        email: 'internal@trademe.com',
        membershipLevel: 'basic'
      });
      
      const response = await axios.get(
        `${TRADING_SERVICE_URL}/api/v1/user-wallets/admin/user/${userId}/wallets`,
        {
          headers: {
            'Authorization': `Bearer ${internalToken}`,
            'User-Agent': 'Trademe-UserService/1.0'
          },
          timeout: 5000
        }
      );

      if (response.data?.success) {
        return response.data.data;
      } else {
        throw new Error(`API响应失败: ${response.data?.message || '未知错误'}`);
      }
      
    } catch (error) {
      logger.error(`获取用户 ${userId} 钱包信息失败:`, {
        error: error instanceof Error ? error.message : String(error)
      });
      return null;
    }
  }

  /**
   * 检查钱包服务连接状态
   * @returns 连接是否正常
   */
  static async checkWalletServiceHealth(): Promise<boolean> {
    try {
      const response = await axios.get(`${TRADING_SERVICE_URL}/health`, {
        timeout: 3000
      });
      
      return response.status === 200;
    } catch (error) {
      logger.warn('钱包服务连接检查失败:', {
        error: error instanceof Error ? error.message : String(error)
      });
      return false;
    }
  }
}