import Joi from 'joi';
export declare const registerSchema: Joi.ObjectSchema<any>;
export declare const loginSchema: Joi.ObjectSchema<any>;
export declare const googleAuthSchema: Joi.ObjectSchema<any>;
export declare const sendVerificationSchema: Joi.ObjectSchema<any>;
export declare const verifyEmailSchema: Joi.ObjectSchema<any>;
export declare const refreshTokenSchema: Joi.ObjectSchema<any>;
export declare const resetPasswordSchema: Joi.ObjectSchema<any>;
export declare const updateProfileSchema: Joi.ObjectSchema<any>;
export declare const changePasswordSchema: Joi.ObjectSchema<any>;
export declare const paginationSchema: Joi.ObjectSchema<any>;
export declare const usageStatsSchema: Joi.ObjectSchema<any>;
export declare const idSchema: Joi.ObjectSchema<any>;
export declare const isValidEmail: (email: string) => boolean;
export declare const validatePasswordStrength: (password: string) => {
    isValid: boolean;
    score: number;
    feedback: string[];
};
export declare const isValidUsername: (username: string) => boolean;
export declare const isValidPhone: (phone: string) => boolean;
//# sourceMappingURL=validation.d.ts.map