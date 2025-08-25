import crypto from 'crypto';
import bcrypt from 'bcryptjs';
import { logger } from './logger';

// 加密配置
const ENCRYPTION_ALGORITHM = 'aes-256-gcm';
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'your_32_character_encryption_key';
const BCRYPT_SALT_ROUNDS = 12;

/**
 * 加密数据
 */
export const encrypt = (text: string): string => {
  try {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipher(ENCRYPTION_ALGORITHM, ENCRYPTION_KEY);
    cipher.setAAD(Buffer.from('trademe-encryption', 'utf8'));
    
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    const authTag = cipher.getAuthTag();
    
    // 返回格式: iv:authTag:encryptedData
    return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
  } catch (error) {
    logger.error('Encryption error:', error);
    throw new Error('Encryption failed');
  }
};

/**
 * 解密数据
 */
export const decrypt = (encryptedData: string): string => {
  try {
    const parts = encryptedData.split(':');
    if (parts.length !== 3) {
      throw new Error('Invalid encrypted data format');
    }

    const [ivHex, authTagHex, encrypted] = parts;
    const iv = Buffer.from(ivHex, 'hex');
    const authTag = Buffer.from(authTagHex, 'hex');
    
    const decipher = crypto.createDecipher(ENCRYPTION_ALGORITHM, ENCRYPTION_KEY);
    decipher.setAAD(Buffer.from('trademe-encryption', 'utf8'));
    decipher.setAuthTag(authTag);
    
    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    
    return decrypted;
  } catch (error) {
    logger.error('Decryption error:', error);
    throw new Error('Decryption failed');
  }
};

/**
 * 哈希密码
 */
export const hashPassword = async (password: string): Promise<string> => {
  try {
    return await bcrypt.hash(password, BCRYPT_SALT_ROUNDS);
  } catch (error) {
    logger.error('Password hashing error:', error);
    throw new Error('Password hashing failed');
  }
};

/**
 * 验证密码
 */
export const verifyPassword = async (password: string, hashedPassword: string): Promise<boolean> => {
  try {
    return await bcrypt.compare(password, hashedPassword);
  } catch (error) {
    logger.error('Password verification error:', error);
    throw new Error('Password verification failed');
  }
};

/**
 * 生成随机字符串
 */
export const generateRandomString = (length: number = 32): string => {
  return crypto.randomBytes(length).toString('hex');
};

/**
 * 生成数字验证码
 */
export const generateVerificationCode = (length: number = 6): string => {
  const digits = '0123456789';
  let code = '';
  
  for (let i = 0; i < length; i++) {
    code += digits[Math.floor(Math.random() * digits.length)];
  }
  
  return code;
};

/**
 * 生成UUID
 */
export const generateUUID = (): string => {
  return crypto.randomUUID();
};

/**
 * 生成订单号
 */
export const generateOrderNumber = (): string => {
  const timestamp = Date.now().toString();
  const random = Math.random().toString(36).substring(2, 8).toUpperCase();
  return `TM${timestamp}${random}`;
};

/**
 * 计算文件哈希
 */
export const calculateFileHash = (buffer: Buffer): string => {
  return crypto.createHash('sha256').update(buffer).digest('hex');
};

/**
 * 计算字符串MD5
 */
export const calculateMD5 = (text: string): string => {
  return crypto.createHash('md5').update(text).digest('hex');
};

/**
 * 计算字符串SHA256
 */
export const calculateSHA256 = (text: string): string => {
  return crypto.createHash('sha256').update(text).digest('hex');
};

/**
 * 生成HMAC签名
 */
export const generateHMAC = (data: string, secret: string): string => {
  return crypto.createHmac('sha256', secret).update(data).digest('hex');
};

/**
 * 验证HMAC签名
 */
export const verifyHMAC = (data: string, signature: string, secret: string): boolean => {
  const expectedSignature = generateHMAC(data, secret);
  return crypto.timingSafeEqual(
    Buffer.from(signature, 'hex'),
    Buffer.from(expectedSignature, 'hex')
  );
};

/**
 * 生成API密钥对
 */
export const generateAPIKeyPair = (): { apiKey: string; secretKey: string } => {
  const apiKey = 'tk_' + generateRandomString(24);
  const secretKey = generateRandomString(32);
  
  return { apiKey, secretKey };
};

/**
 * 加密敏感字段（如API密钥）
 */
export const encryptSensitiveField = (value: string): string => {
  return encrypt(value);
};

/**
 * 解密敏感字段
 */
export const decryptSensitiveField = (encryptedValue: string): string => {
  return decrypt(encryptedValue);
};