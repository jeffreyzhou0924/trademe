"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const errorHandler_1 = require("../middleware/errorHandler");
const auth_1 = require("../middleware/auth");
const membership_1 = __importDefault(require("../controllers/membership"));
const router = (0, express_1.Router)();
router.get('/plans', auth_1.optionalAuth, (0, errorHandler_1.asyncHandler)(membership_1.default.getPlans));
exports.default = router;
//# sourceMappingURL=membership.js.map