"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.decryptSensitiveField = exports.encryptSensitiveField = exports.generateAPIKeyPair = exports.verifyHMAC = exports.generateHMAC = exports.calculateSHA256 = exports.calculateMD5 = exports.calculateFileHash = exports.generateOrderNumber = exports.generateUUID = exports.generateVerificationCode = exports.generateRandomString = exports.verifyPassword = exports.hashPassword = exports.decrypt = exports.encrypt = void 0;
const crypto_1 = __importDefault(require("crypto"));
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const logger_1 = require("./logger");
const ENCRYPTION_ALGORITHM = 'aes-256-gcm';
const ENCRYPTION_KEY = process.env.ENCRYPTION_KEY || 'your_32_character_encryption_key';
const BCRYPT_SALT_ROUNDS = 12;
const encrypt = (text) => {
    try {
        const iv = crypto_1.default.randomBytes(16);
        const cipher = crypto_1.default.createCipher(ENCRYPTION_ALGORITHM, ENCRYPTION_KEY);
        cipher.setAAD(Buffer.from('trademe-encryption', 'utf8'));
        let encrypted = cipher.update(text, 'utf8', 'hex');
        encrypted += cipher.final('hex');
        const authTag = cipher.getAuthTag();
        return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
    }
    catch (error) {
        logger_1.logger.error('Encryption error:', error);
        throw new Error('Encryption failed');
    }
};
exports.encrypt = encrypt;
const decrypt = (encryptedData) => {
    try {
        const parts = encryptedData.split(':');
        if (parts.length !== 3) {
            throw new Error('Invalid encrypted data format');
        }
        const [ivHex, authTagHex, encrypted] = parts;
        const iv = Buffer.from(ivHex, 'hex');
        const authTag = Buffer.from(authTagHex, 'hex');
        const decipher = crypto_1.default.createDecipher(ENCRYPTION_ALGORITHM, ENCRYPTION_KEY);
        decipher.setAAD(Buffer.from('trademe-encryption', 'utf8'));
        decipher.setAuthTag(authTag);
        let decrypted = decipher.update(encrypted, 'hex', 'utf8');
        decrypted += decipher.final('utf8');
        return decrypted;
    }
    catch (error) {
        logger_1.logger.error('Decryption error:', error);
        throw new Error('Decryption failed');
    }
};
exports.decrypt = decrypt;
const hashPassword = async (password) => {
    try {
        return await bcryptjs_1.default.hash(password, BCRYPT_SALT_ROUNDS);
    }
    catch (error) {
        logger_1.logger.error('Password hashing error:', error);
        throw new Error('Password hashing failed');
    }
};
exports.hashPassword = hashPassword;
const verifyPassword = async (password, hashedPassword) => {
    try {
        return await bcryptjs_1.default.compare(password, hashedPassword);
    }
    catch (error) {
        logger_1.logger.error('Password verification error:', error);
        throw new Error('Password verification failed');
    }
};
exports.verifyPassword = verifyPassword;
const generateRandomString = (length = 32) => {
    return crypto_1.default.randomBytes(length).toString('hex');
};
exports.generateRandomString = generateRandomString;
const generateVerificationCode = (length = 6) => {
    const digits = '0123456789';
    let code = '';
    for (let i = 0; i < length; i++) {
        code += digits[Math.floor(Math.random() * digits.length)];
    }
    return code;
};
exports.generateVerificationCode = generateVerificationCode;
const generateUUID = () => {
    return crypto_1.default.randomUUID();
};
exports.generateUUID = generateUUID;
const generateOrderNumber = () => {
    const timestamp = Date.now().toString();
    const random = Math.random().toString(36).substring(2, 8).toUpperCase();
    return `TM${timestamp}${random}`;
};
exports.generateOrderNumber = generateOrderNumber;
const calculateFileHash = (buffer) => {
    return crypto_1.default.createHash('sha256').update(buffer).digest('hex');
};
exports.calculateFileHash = calculateFileHash;
const calculateMD5 = (text) => {
    return crypto_1.default.createHash('md5').update(text).digest('hex');
};
exports.calculateMD5 = calculateMD5;
const calculateSHA256 = (text) => {
    return crypto_1.default.createHash('sha256').update(text).digest('hex');
};
exports.calculateSHA256 = calculateSHA256;
const generateHMAC = (data, secret) => {
    return crypto_1.default.createHmac('sha256', secret).update(data).digest('hex');
};
exports.generateHMAC = generateHMAC;
const verifyHMAC = (data, signature, secret) => {
    const expectedSignature = (0, exports.generateHMAC)(data, secret);
    return crypto_1.default.timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expectedSignature, 'hex'));
};
exports.verifyHMAC = verifyHMAC;
const generateAPIKeyPair = () => {
    const apiKey = 'tk_' + (0, exports.generateRandomString)(24);
    const secretKey = (0, exports.generateRandomString)(32);
    return { apiKey, secretKey };
};
exports.generateAPIKeyPair = generateAPIKeyPair;
const encryptSensitiveField = (value) => {
    return (0, exports.encrypt)(value);
};
exports.encryptSensitiveField = encryptSensitiveField;
const decryptSensitiveField = (encryptedValue) => {
    return (0, exports.decrypt)(encryptedValue);
};
exports.decryptSensitiveField = decryptSensitiveField;
//# sourceMappingURL=encryption.js.map