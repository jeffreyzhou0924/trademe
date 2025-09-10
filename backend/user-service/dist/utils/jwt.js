"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getTokenRemainingTime = exports.isTokenExpiringSoon = exports.decodeToken = exports.verifyRefreshToken = exports.verifyAccessToken = exports.generateTokenPair = exports.generateRefreshToken = exports.generateAccessToken = void 0;
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const logger_1 = require("./logger");
const JWT_SECRET = process.env.JWT_SECRET || 'your_super_secret_jwt_key_here';
const JWT_REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || 'your_super_secret_refresh_key_here';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '24h';
const JWT_REFRESH_EXPIRES_IN = process.env.JWT_REFRESH_EXPIRES_IN || '30d';
const generateAccessToken = (payload) => {
    try {
        const tokenPayload = {
            ...payload,
            type: 'access',
        };
        return jsonwebtoken_1.default.sign(tokenPayload, JWT_SECRET, {
            expiresIn: JWT_EXPIRES_IN,
            issuer: 'trademe-user-service',
            audience: 'trademe-app',
        });
    }
    catch (error) {
        logger_1.logger.error('Error generating access token:', error);
        throw new Error('Failed to generate access token');
    }
};
exports.generateAccessToken = generateAccessToken;
const generateRefreshToken = (payload) => {
    try {
        const tokenPayload = {
            ...payload,
            type: 'refresh',
        };
        return jsonwebtoken_1.default.sign(tokenPayload, JWT_REFRESH_SECRET, {
            expiresIn: JWT_REFRESH_EXPIRES_IN,
            issuer: 'trademe-user-service',
            audience: 'trademe-app',
        });
    }
    catch (error) {
        logger_1.logger.error('Error generating refresh token:', error);
        throw new Error('Failed to generate refresh token');
    }
};
exports.generateRefreshToken = generateRefreshToken;
const generateTokenPair = (payload) => {
    const accessToken = (0, exports.generateAccessToken)(payload);
    const refreshToken = (0, exports.generateRefreshToken)(payload);
    let expiresIn = 24 * 60 * 60;
    if (JWT_EXPIRES_IN.includes('h')) {
        expiresIn = parseInt(JWT_EXPIRES_IN.replace('h', '')) * 60 * 60;
    }
    else if (JWT_EXPIRES_IN.includes('d')) {
        expiresIn = parseInt(JWT_EXPIRES_IN.replace('d', '')) * 24 * 60 * 60;
    }
    return {
        accessToken,
        refreshToken,
        expiresIn,
    };
};
exports.generateTokenPair = generateTokenPair;
const verifyAccessToken = (token) => {
    try {
        const decoded = jsonwebtoken_1.default.verify(token, JWT_SECRET, {
            issuer: 'trademe-user-service',
            audience: 'trademe-app',
        });
        if (decoded.type !== 'access') {
            throw new Error('Invalid token type');
        }
        return decoded;
    }
    catch (error) {
        if (error instanceof jsonwebtoken_1.default.TokenExpiredError) {
            throw new Error('Token expired');
        }
        else if (error instanceof jsonwebtoken_1.default.JsonWebTokenError) {
            throw new Error('Invalid token');
        }
        else {
            logger_1.logger.error('Error verifying access token:', error);
            throw new Error('Token verification failed');
        }
    }
};
exports.verifyAccessToken = verifyAccessToken;
const verifyRefreshToken = (token) => {
    try {
        const decoded = jsonwebtoken_1.default.verify(token, JWT_REFRESH_SECRET, {
            issuer: 'trademe-user-service',
            audience: 'trademe-app',
        });
        if (decoded.type !== 'refresh') {
            throw new Error('Invalid token type');
        }
        return decoded;
    }
    catch (error) {
        if (error instanceof jsonwebtoken_1.default.TokenExpiredError) {
            throw new Error('Refresh token expired');
        }
        else if (error instanceof jsonwebtoken_1.default.JsonWebTokenError) {
            throw new Error('Invalid refresh token');
        }
        else {
            logger_1.logger.error('Error verifying refresh token:', error);
            throw new Error('Refresh token verification failed');
        }
    }
};
exports.verifyRefreshToken = verifyRefreshToken;
const decodeToken = (token) => {
    try {
        return jsonwebtoken_1.default.decode(token);
    }
    catch (error) {
        logger_1.logger.error('Error decoding token:', error);
        return null;
    }
};
exports.decodeToken = decodeToken;
const isTokenExpiringSoon = (token, minutesBefore = 30) => {
    try {
        const decoded = (0, exports.decodeToken)(token);
        if (!decoded || !decoded.exp) {
            return true;
        }
        const now = Math.floor(Date.now() / 1000);
        const timeUntilExpiry = decoded.exp - now;
        const minutesUntilExpiry = timeUntilExpiry / 60;
        return minutesUntilExpiry <= minutesBefore;
    }
    catch (error) {
        logger_1.logger.error('Error checking token expiry:', error);
        return true;
    }
};
exports.isTokenExpiringSoon = isTokenExpiringSoon;
const getTokenRemainingTime = (token) => {
    try {
        const decoded = (0, exports.decodeToken)(token);
        if (!decoded || !decoded.exp) {
            return 0;
        }
        const now = Math.floor(Date.now() / 1000);
        return Math.max(0, decoded.exp - now);
    }
    catch (error) {
        logger_1.logger.error('Error getting token remaining time:', error);
        return 0;
    }
};
exports.getTokenRemainingTime = getTokenRemainingTime;
//# sourceMappingURL=jwt.js.map