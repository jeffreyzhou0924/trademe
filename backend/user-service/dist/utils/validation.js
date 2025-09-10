"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.isValidPhone = exports.isValidUsername = exports.validatePasswordStrength = exports.isValidEmail = exports.idSchema = exports.usageStatsSchema = exports.paginationSchema = exports.changePasswordSchema = exports.updateProfileSchema = exports.resetPasswordSchema = exports.refreshTokenSchema = exports.verifyEmailSchema = exports.sendVerificationSchema = exports.googleAuthSchema = exports.loginSchema = exports.registerSchema = void 0;
const joi_1 = __importDefault(require("joi"));
exports.registerSchema = joi_1.default.object({
    username: joi_1.default.string()
        .alphanum()
        .min(3)
        .max(20)
        .required()
        .messages({
        'string.alphanum': '用户名只能包含字母和数字',
        'string.min': '用户名长度至少3位',
        'string.max': '用户名长度最多20位',
        'any.required': '用户名不能为空',
    }),
    email: joi_1.default.string()
        .email()
        .required()
        .messages({
        'string.email': '邮箱格式不正确',
        'any.required': '邮箱不能为空',
    }),
    password: joi_1.default.string()
        .min(8)
        .max(50)
        .pattern(/^(?=.*[a-zA-Z])(?=.*\d)/)
        .required()
        .messages({
        'string.min': '密码长度至少8位',
        'string.max': '密码长度最多50位',
        'string.pattern.base': '密码必须包含字母和数字',
        'any.required': '密码不能为空',
    }),
    confirm_password: joi_1.default.string()
        .valid(joi_1.default.ref('password'))
        .required()
        .messages({
        'any.only': '确认密码与密码不一致',
        'any.required': '确认密码不能为空',
    }),
});
exports.loginSchema = joi_1.default.object({
    email: joi_1.default.string()
        .email()
        .required()
        .messages({
        'string.email': '邮箱格式不正确',
        'any.required': '邮箱不能为空',
    }),
    password: joi_1.default.string()
        .required()
        .messages({
        'any.required': '密码不能为空',
    }),
});
exports.googleAuthSchema = joi_1.default.object({
    google_token: joi_1.default.string()
        .required()
        .messages({
        'any.required': 'Google令牌不能为空',
    }),
});
exports.sendVerificationSchema = joi_1.default.object({
    email: joi_1.default.string()
        .email()
        .required()
        .messages({
        'string.email': '邮箱格式不正确',
        'any.required': '邮箱不能为空',
    }),
    type: joi_1.default.string()
        .valid('register', 'login', 'reset_password', 'change_email')
        .default('register')
        .messages({
        'any.only': '验证码类型无效',
    }),
});
exports.verifyEmailSchema = joi_1.default.object({
    email: joi_1.default.string()
        .email()
        .required()
        .messages({
        'string.email': '邮箱格式不正确',
        'any.required': '邮箱不能为空',
    }),
    code: joi_1.default.string()
        .length(6)
        .pattern(/^\d{6}$/)
        .required()
        .messages({
        'string.length': '验证码必须是6位数字',
        'string.pattern.base': '验证码必须是6位数字',
        'any.required': '验证码不能为空',
    }),
});
exports.refreshTokenSchema = joi_1.default.object({
    refresh_token: joi_1.default.string()
        .required()
        .messages({
        'any.required': '刷新令牌不能为空',
    }),
});
exports.resetPasswordSchema = joi_1.default.object({
    email: joi_1.default.string()
        .email()
        .required()
        .messages({
        'string.email': '邮箱格式不正确',
        'any.required': '邮箱不能为空',
    }),
    code: joi_1.default.string()
        .length(6)
        .pattern(/^\d{6}$/)
        .required()
        .messages({
        'string.length': '验证码必须是6位数字',
        'string.pattern.base': '验证码必须是6位数字',
        'any.required': '验证码不能为空',
    }),
    new_password: joi_1.default.string()
        .min(8)
        .max(50)
        .pattern(/^(?=.*[a-zA-Z])(?=.*\d)/)
        .required()
        .messages({
        'string.min': '新密码长度至少8位',
        'string.max': '新密码长度最多50位',
        'string.pattern.base': '新密码必须包含字母和数字',
        'any.required': '新密码不能为空',
    }),
    confirm_password: joi_1.default.string()
        .valid(joi_1.default.ref('new_password'))
        .required()
        .messages({
        'any.only': '确认密码与新密码不一致',
        'any.required': '确认密码不能为空',
    }),
});
exports.updateProfileSchema = joi_1.default.object({
    username: joi_1.default.string()
        .alphanum()
        .min(3)
        .max(20)
        .optional()
        .messages({
        'string.alphanum': '用户名只能包含字母和数字',
        'string.min': '用户名长度至少3位',
        'string.max': '用户名长度最多20位',
    }),
    phone: joi_1.default.string()
        .pattern(/^(\+\d{1,3}[- ]?)?\d{10,11}$/)
        .optional()
        .allow('')
        .messages({
        'string.pattern.base': '手机号格式不正确',
    }),
    avatar_url: joi_1.default.string()
        .uri()
        .optional()
        .allow('')
        .messages({
        'string.uri': '头像URL格式不正确',
    }),
    preferences: joi_1.default.object({
        language: joi_1.default.string()
            .valid('zh-CN', 'en-US')
            .default('zh-CN'),
        timezone: joi_1.default.string()
            .default('Asia/Shanghai'),
        theme: joi_1.default.string()
            .valid('light', 'dark')
            .default('light'),
    }).optional(),
});
exports.changePasswordSchema = joi_1.default.object({
    current_password: joi_1.default.string()
        .required()
        .messages({
        'any.required': '当前密码不能为空',
    }),
    new_password: joi_1.default.string()
        .min(8)
        .max(50)
        .pattern(/^(?=.*[a-zA-Z])(?=.*\d)/)
        .required()
        .messages({
        'string.min': '新密码长度至少8位',
        'string.max': '新密码长度最多50位',
        'string.pattern.base': '新密码必须包含字母和数字',
        'any.required': '新密码不能为空',
    }),
    confirm_password: joi_1.default.string()
        .valid(joi_1.default.ref('new_password'))
        .required()
        .messages({
        'any.only': '确认密码与新密码不一致',
        'any.required': '确认密码不能为空',
    }),
});
exports.paginationSchema = joi_1.default.object({
    page: joi_1.default.number()
        .integer()
        .min(1)
        .default(1)
        .messages({
        'number.integer': '页码必须是整数',
        'number.min': '页码必须大于0',
    }),
    limit: joi_1.default.number()
        .integer()
        .min(1)
        .max(100)
        .default(20)
        .messages({
        'number.integer': '每页数量必须是整数',
        'number.min': '每页数量必须大于0',
        'number.max': '每页数量不能超过100',
    }),
    search: joi_1.default.string()
        .optional()
        .allow(''),
    membership_level: joi_1.default.string()
        .valid('basic', 'premium', 'professional')
        .optional(),
    is_active: joi_1.default.boolean()
        .optional(),
});
exports.usageStatsSchema = joi_1.default.object({
    period: joi_1.default.string()
        .valid('day', 'week', 'month')
        .default('day')
        .messages({
        'any.only': '统计周期必须是 day、week 或 month',
    }),
});
exports.idSchema = joi_1.default.object({
    id: joi_1.default.string()
        .pattern(/^\d+$/)
        .required()
        .messages({
        'string.pattern.base': 'ID必须是数字',
        'any.required': 'ID不能为空',
    }),
});
const isValidEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
};
exports.isValidEmail = isValidEmail;
const validatePasswordStrength = (password) => {
    const feedback = [];
    let score = 0;
    if (password.length >= 8) {
        score += 1;
    }
    else {
        feedback.push('密码长度至少8位');
    }
    if (/[a-z]/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('密码应包含小写字母');
    }
    if (/[A-Z]/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('密码应包含大写字母');
    }
    if (/\d/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('密码应包含数字');
    }
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        score += 1;
    }
    else {
        feedback.push('密码应包含特殊字符');
    }
    if (password.length >= 12) {
        score += 1;
    }
    return {
        isValid: score >= 3 && password.length >= 8,
        score,
        feedback,
    };
};
exports.validatePasswordStrength = validatePasswordStrength;
const isValidUsername = (username) => {
    const usernameRegex = /^[a-zA-Z0-9_]{3,20}$/;
    return usernameRegex.test(username);
};
exports.isValidUsername = isValidUsername;
const isValidPhone = (phone) => {
    const phoneRegex = /^(\+\d{1,3}[- ]?)?\d{10,11}$/;
    return phoneRegex.test(phone);
};
exports.isValidPhone = isValidPhone;
//# sourceMappingURL=validation.js.map