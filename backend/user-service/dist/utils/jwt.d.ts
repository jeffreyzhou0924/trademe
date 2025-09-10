export interface JwtPayload {
    userId: string;
    email: string;
    membershipLevel: string;
    type: 'access' | 'refresh';
    iat?: number;
    exp?: number;
}
export interface TokenPair {
    accessToken: string;
    refreshToken: string;
    expiresIn: number;
}
export declare const generateAccessToken: (payload: Omit<JwtPayload, "type" | "iat" | "exp">) => string;
export declare const generateRefreshToken: (payload: Omit<JwtPayload, "type" | "iat" | "exp">) => string;
export declare const generateTokenPair: (payload: Omit<JwtPayload, "type" | "iat" | "exp">) => TokenPair;
export declare const verifyAccessToken: (token: string) => JwtPayload;
export declare const verifyRefreshToken: (token: string) => JwtPayload;
export declare const decodeToken: (token: string) => JwtPayload | null;
export declare const isTokenExpiringSoon: (token: string, minutesBefore?: number) => boolean;
export declare const getTokenRemainingTime: (token: string) => number;
//# sourceMappingURL=jwt.d.ts.map