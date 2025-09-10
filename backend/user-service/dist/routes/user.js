"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const validation_1 = require("../utils/validation");
const validation_2 = require("../middleware/validation");
const errorHandler_1 = require("../middleware/errorHandler");
const auth_1 = require("../middleware/auth");
const rateLimit_1 = require("../middleware/rateLimit");
const upload_1 = require("../middleware/upload");
const user_1 = __importDefault(require("../controllers/user"));
const router = (0, express_1.Router)();
router.use(auth_1.authenticateToken);
router.get('/profile', (0, errorHandler_1.asyncHandler)(user_1.default.getProfile));
router.put('/profile', (0, validation_2.validateBody)(validation_1.updateProfileSchema), (0, errorHandler_1.asyncHandler)(user_1.default.updateProfile));
router.put('/change-password', (0, validation_2.validateBody)(validation_1.changePasswordSchema), (0, errorHandler_1.asyncHandler)(user_1.default.changePassword));
router.post('/bind-google', (0, validation_2.validateBody)(validation_1.googleAuthSchema), (0, errorHandler_1.asyncHandler)(user_1.default.bindGoogle));
router.delete('/unbind-google', (0, errorHandler_1.asyncHandler)(user_1.default.unbindGoogle));
router.post('/upload-avatar', rateLimit_1.fileUploadRateLimit, upload_1.cleanupOnError, upload_1.avatarUpload, upload_1.validateImage, (0, errorHandler_1.asyncHandler)(user_1.default.uploadAvatar));
router.get('/usage-stats', (0, errorHandler_1.asyncHandler)(user_1.default.getUsageStats));
router.get('/membership', (0, errorHandler_1.asyncHandler)(user_1.default.getMembershipInfo));
exports.default = router;
//# sourceMappingURL=user.js.map