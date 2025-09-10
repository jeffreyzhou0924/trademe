"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const validation_1 = require("../utils/validation");
const validation_2 = require("../middleware/validation");
const rateLimit_1 = require("../middleware/rateLimit");
const errorHandler_1 = require("../middleware/errorHandler");
const auth_1 = require("../middleware/auth");
const auth_2 = __importDefault(require("../controllers/auth"));
const router = (0, express_1.Router)();
router.post('/register', rateLimit_1.authRateLimit, (0, validation_2.validateBody)(validation_1.registerSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.register));
router.post('/send-verification', rateLimit_1.verificationCodeRateLimit, (0, validation_2.validateBody)(validation_1.sendVerificationSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.sendVerificationCode));
router.post('/verify-email', (0, validation_2.validateBody)(validation_1.verifyEmailSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.verifyEmail));
router.post('/login', rateLimit_1.authRateLimit, (0, validation_2.validateBody)(validation_1.loginSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.login));
router.post('/google', rateLimit_1.authRateLimit, (0, validation_2.validateBody)(validation_1.googleAuthSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.googleAuth));
router.post('/refresh', (0, validation_2.validateBody)(validation_1.refreshTokenSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.refreshToken));
router.post('/reset-password', rateLimit_1.passwordResetRateLimit, (0, validation_2.validateBody)(validation_1.resetPasswordSchema), (0, errorHandler_1.asyncHandler)(auth_2.default.resetPassword));
router.post('/logout', auth_1.authenticateToken, (0, errorHandler_1.asyncHandler)(auth_2.default.logout));
router.get('/me', auth_1.authenticateToken, (0, errorHandler_1.asyncHandler)(auth_2.default.getCurrentUser));
exports.default = router;
//# sourceMappingURL=auth.js.map