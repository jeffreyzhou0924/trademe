export declare class WalletService {
    static allocateWalletsForNewUser(userId: number, userEmail: string): Promise<void>;
    static getUserWallets(userId: number): Promise<any>;
    static checkWalletServiceHealth(): Promise<boolean>;
}
//# sourceMappingURL=wallet.service.d.ts.map