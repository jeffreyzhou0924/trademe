import Joi from 'joi';

// 用户注册验证
export const registerSchema = Joi.object({
  username: Joi.string()
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
  email: Joi.string()
    .email()
    .required()
    .messages({
      'string.email': '邮箱格式不正确',
      'any.required': '邮箱不能为空',
    }),
  password: Joi.string()
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
  confirm_password: Joi.string()
    .valid(Joi.ref('password'))
    .required()
    .messages({
      'any.only': '确认密码与密码不一致',
      'any.required': '确认密码不能为空',
    }),
});

// 用户登录验证
export const loginSchema = Joi.object({
  email: Joi.string()
    .email()
    .required()
    .messages({
      'string.email': '邮箱格式不正确',
      'any.required': '邮箱不能为空',
    }),
  password: Joi.string()
    .required()
    .messages({
      'any.required': '密码不能为空',
    }),
});

// Google OAuth验证
export const googleAuthSchema = Joi.object({
  google_token: Joi.string()
    .required()
    .messages({
      'any.required': 'Google令牌不能为空',
    }),
});

// 发送验证码验证
export const sendVerificationSchema = Joi.object({
  email: Joi.string()
    .email()
    .required()
    .messages({
      'string.email': '邮箱格式不正确',
      'any.required': '邮箱不能为空',
    }),
  type: Joi.string()
    .valid('register', 'login', 'reset_password', 'change_email')
    .default('register')
    .messages({
      'any.only': '验证码类型无效',
    }),
});

// 邮箱验证验证
export const verifyEmailSchema = Joi.object({
  email: Joi.string()
    .email()
    .required()
    .messages({
      'string.email': '邮箱格式不正确',
      'any.required': '邮箱不能为空',
    }),
  code: Joi.string()
    .length(6)
    .pattern(/^\d{6}$/)
    .required()
    .messages({
      'string.length': '验证码必须是6位数字',
      'string.pattern.base': '验证码必须是6位数字',
      'any.required': '验证码不能为空',
    }),
});

// 刷新令牌验证
export const refreshTokenSchema = Joi.object({
  refresh_token: Joi.string()
    .required()
    .messages({
      'any.required': '刷新令牌不能为空',
    }),
});

// 重置密码验证
export const resetPasswordSchema = Joi.object({
  email: Joi.string()
    .email()
    .required()
    .messages({
      'string.email': '邮箱格式不正确',
      'any.required': '邮箱不能为空',
    }),
  code: Joi.string()
    .length(6)
    .pattern(/^\d{6}$/)
    .required()
    .messages({
      'string.length': '验证码必须是6位数字',
      'string.pattern.base': '验证码必须是6位数字',
      'any.required': '验证码不能为空',
    }),
  new_password: Joi.string()
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
  confirm_password: Joi.string()
    .valid(Joi.ref('new_password'))
    .required()
    .messages({
      'any.only': '确认密码与新密码不一致',
      'any.required': '确认密码不能为空',
    }),
});

// 更新用户信息验证
export const updateProfileSchema = Joi.object({
  username: Joi.string()
    .alphanum()
    .min(3)
    .max(20)
    .optional()
    .messages({
      'string.alphanum': '用户名只能包含字母和数字',
      'string.min': '用户名长度至少3位',
      'string.max': '用户名长度最多20位',
    }),
  phone: Joi.string()
    .pattern(/^(\+\d{1,3}[- ]?)?\d{10,11}$/)
    .optional()
    .allow('')
    .messages({
      'string.pattern.base': '手机号格式不正确',
    }),
  avatar_url: Joi.string()
    .uri()
    .optional()
    .allow('')
    .messages({
      'string.uri': '头像URL格式不正确',
    }),
  preferences: Joi.object({
    language: Joi.string()
      .valid('zh-CN', 'en-US')
      .default('zh-CN'),
    timezone: Joi.string()
      .default('Asia/Shanghai'),
    theme: Joi.string()
      .valid('light', 'dark')
      .default('light'),
  }).optional(),
});

// 修改密码验证
export const changePasswordSchema = Joi.object({
  current_password: Joi.string()
    .required()
    .messages({
      'any.required': '当前密码不能为空',
    }),
  new_password: Joi.string()
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
  confirm_password: Joi.string()
    .valid(Joi.ref('new_password'))
    .required()
    .messages({
      'any.only': '确认密码与新密码不一致',
      'any.required': '确认密码不能为空',
    }),
});

// 分页查询验证
export const paginationSchema = Joi.object({
  page: Joi.number()
    .integer()
    .min(1)
    .default(1)
    .messages({
      'number.integer': '页码必须是整数',
      'number.min': '页码必须大于0',
    }),
  limit: Joi.number()
    .integer()
    .min(1)
    .max(100)
    .default(20)
    .messages({
      'number.integer': '每页数量必须是整数',
      'number.min': '每页数量必须大于0',
      'number.max': '每页数量不能超过100',
    }),
  search: Joi.string()
    .optional()
    .allow(''),
  membership_level: Joi.string()
    .valid('basic', 'premium', 'professional')
    .optional(),
  is_active: Joi.boolean()
    .optional(),
});

// 使用量统计查询验证
export const usageStatsSchema = Joi.object({
  period: Joi.string()
    .valid('day', 'week', 'month')
    .default('day')
    .messages({
      'any.only': '统计周期必须是 day、week 或 month',
    }),
});

// 通用ID验证
export const idSchema = Joi.object({
  id: Joi.string()
    .pattern(/^\d+$/)
    .required()
    .messages({
      'string.pattern.base': 'ID必须是数字',
      'any.required': 'ID不能为空',
    }),
});

// 邮箱验证函数
export const isValidEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

// 密码强度验证
export const validatePasswordStrength = (password: string): {
  isValid: boolean;
  score: number;
  feedback: string[];
} => {
  const feedback: string[] = [];
  let score = 0;

  // 长度检查
  if (password.length >= 8) {
    score += 1;
  } else {
    feedback.push('密码长度至少8位');
  }

  // 包含小写字母
  if (/[a-z]/.test(password)) {
    score += 1;
  } else {
    feedback.push('密码应包含小写字母');
  }

  // 包含大写字母
  if (/[A-Z]/.test(password)) {
    score += 1;
  } else {
    feedback.push('密码应包含大写字母');
  }

  // 包含数字
  if (/\d/.test(password)) {
    score += 1;
  } else {
    feedback.push('密码应包含数字');
  }

  // 包含特殊字符
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    score += 1;
  } else {
    feedback.push('密码应包含特殊字符');
  }

  // 长度超过12位
  if (password.length >= 12) {
    score += 1;
  }

  return {
    isValid: score >= 3 && password.length >= 8,
    score,
    feedback,
  };
};

// 用户名验证函数
export const isValidUsername = (username: string): boolean => {
  const usernameRegex = /^[a-zA-Z0-9_]{3,20}$/;
  return usernameRegex.test(username);
};

// 手机号验证函数
export const isValidPhone = (phone: string): boolean => {
  const phoneRegex = /^(\+\d{1,3}[- ]?)?\d{10,11}$/;
  return phoneRegex.test(phone);
};