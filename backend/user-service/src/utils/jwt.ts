import jwt, { SignOptions } from 'jsonwebtoken';
import { logger } from './logger';

// JWT配置
const JWT_SECRET = process.env.JWT_SECRET || 'your_super_secret_jwt_key_here';
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || 'your_super_secret_refresh_key_here';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '24h';
const JWT_REFRESH_EXPIRES_IN = process.env.JWT_REFRESH_EXPIRES_IN || '30d';

// JWT载荷接口
export interface JwtPayload {
  userId: string;
  email: string;
  membershipLevel: string;
  type: 'access' | 'refresh';
  iat?: number;
  exp?: number;
}

// 令牌对
export interface TokenPair {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

/**
 * 生成访问令牌
 */
export const generateAccessToken = (payload: Omit<JwtPayload, 'type' | 'iat' | 'exp'>): string => {
  try {
    const tokenPayload: JwtPayload = {
      ...payload,
      type: 'access',
    };

    return jwt.sign(tokenPayload, JWT_SECRET, {
      expiresIn: JWT_EXPIRES_IN,
      issuer: 'trademe-user-service',
      audience: 'trademe-app',
    } as any);
  } catch (error) {
    logger.error('Error generating access token:', error);
    throw new Error('Failed to generate access token');
  }
};

/**
 * 生成刷新令牌
 */
export const generateRefreshToken = (payload: Omit<JwtPayload, 'type' | 'iat' | 'exp'>): string => {
  try {
    const tokenPayload: JwtPayload = {
      ...payload,
      type: 'refresh',
    };

    return jwt.sign(tokenPayload, JWT_REFRESH_SECRET, {
      expiresIn: JWT_REFRESH_EXPIRES_IN,
      issuer: 'trademe-user-service',
      audience: 'trademe-app',
    } as any);
  } catch (error) {
    logger.error('Error generating refresh token:', error);
    throw new Error('Failed to generate refresh token');
  }
};

/**
 * 生成令牌对
 */
export const generateTokenPair = (payload: Omit<JwtPayload, 'type' | 'iat' | 'exp'>): TokenPair => {
  const accessToken = generateAccessToken(payload);
  const refreshToken = generateRefreshToken(payload);
  
  // 计算过期时间（秒）
  let expiresIn = 24 * 60 * 60; // 默认24小时
  if (JWT_EXPIRES_IN.includes('h')) {
    expiresIn = parseInt(JWT_EXPIRES_IN.replace('h', '')) * 60 * 60;
  } else if (JWT_EXPIRES_IN.includes('d')) {
    expiresIn = parseInt(JWT_EXPIRES_IN.replace('d', '')) * 24 * 60 * 60;
  }

  return {
    accessToken,
    refreshToken,
    expiresIn,
  };
};

/**
 * 验证访问令牌
 */
export const verifyAccessToken = (token: string): JwtPayload => {
  try {
    const decoded = jwt.verify(token, JWT_SECRET, {
      issuer: 'trademe-user-service',
      audience: 'trademe-app',
    }) as JwtPayload;

    if (decoded.type !== 'access') {
      throw new Error('Invalid token type');
    }

    return decoded;
  } catch (error) {
    if (error instanceof jwt.TokenExpiredError) {
      throw new Error('Token expired');
    } else if (error instanceof jwt.JsonWebTokenError) {
      throw new Error('Invalid token');
    } else {
      logger.error('Error verifying access token:', error);
      throw new Error('Token verification failed');
    }
  }
};

/**
 * 验证刷新令牌
 */
export const verifyRefreshToken = (token: string): JwtPayload => {
  try {
    const decoded = jwt.verify(token, JWT_REFRESH_SECRET, {
      issuer: 'trademe-user-service',
      audience: 'trademe-app',
    }) as JwtPayload;

    if (decoded.type !== 'refresh') {
      throw new Error('Invalid token type');
    }

    return decoded;
  } catch (error) {
    if (error instanceof jwt.TokenExpiredError) {
      throw new Error('Refresh token expired');
    } else if (error instanceof jwt.JsonWebTokenError) {
      throw new Error('Invalid refresh token');
    } else {
      logger.error('Error verifying refresh token:', error);
      throw new Error('Refresh token verification failed');
    }
  }
};

/**
 * 解码令牌（不验证签名）
 */
export const decodeToken = (token: string): JwtPayload | null => {
  try {
    return jwt.decode(token) as JwtPayload;
  } catch (error) {
    logger.error('Error decoding token:', error);
    return null;
  }
};

/**
 * 检查令牌是否即将过期（剩余时间少于指定分钟）
 */
export const isTokenExpiringSoon = (token: string, minutesBefore: number = 30): boolean => {
  try {
    const decoded = decodeToken(token);
    if (!decoded || !decoded.exp) {
      return true;
    }

    const now = Math.floor(Date.now() / 1000);
    const timeUntilExpiry = decoded.exp - now;
    const minutesUntilExpiry = timeUntilExpiry / 60;

    return minutesUntilExpiry <= minutesBefore;
  } catch (error) {
    logger.error('Error checking token expiry:', error);
    return true;
  }
};

/**
 * 获取令牌剩余时间（秒）
 */
export const getTokenRemainingTime = (token: string): number => {
  try {
    const decoded = decodeToken(token);
    if (!decoded || !decoded.exp) {
      return 0;
    }

    const now = Math.floor(Date.now() / 1000);
    return Math.max(0, decoded.exp - now);
  } catch (error) {
    logger.error('Error getting token remaining time:', error);
    return 0;
  }
};