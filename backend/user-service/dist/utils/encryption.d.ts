export declare const encrypt: (text: string) => string;
export declare const decrypt: (encryptedData: string) => string;
export declare const hashPassword: (password: string) => Promise<string>;
export declare const verifyPassword: (password: string, hashedPassword: string) => Promise<boolean>;
export declare const generateRandomString: (length?: number) => string;
export declare const generateVerificationCode: (length?: number) => string;
export declare const generateUUID: () => string;
export declare const generateOrderNumber: () => string;
export declare const calculateFileHash: (buffer: Buffer) => string;
export declare const calculateMD5: (text: string) => string;
export declare const calculateSHA256: (text: string) => string;
export declare const generateHMAC: (data: string, secret: string) => string;
export declare const verifyHMAC: (data: string, signature: string, secret: string) => boolean;
export declare const generateAPIKeyPair: () => {
    apiKey: string;
    secretKey: string;
};
export declare const encryptSensitiveField: (value: string) => string;
export declare const decryptSensitiveField: (encryptedValue: string) => string;
//# sourceMappingURL=encryption.d.ts.map