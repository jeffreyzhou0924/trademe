"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const errorHandler_1 = require("../middleware/errorHandler");
const config_1 = __importDefault(require("../controllers/config"));
const router = (0, express_1.Router)();
router.get('/', (0, errorHandler_1.asyncHandler)(config_1.default.getSystemConfig));
exports.default = router;
//# sourceMappingURL=config.js.map