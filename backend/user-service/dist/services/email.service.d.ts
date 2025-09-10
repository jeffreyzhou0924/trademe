export interface EmailTemplate {
    subject: string;
    html: string;
    text?: string;
}
export interface EmailConfig {
    from: string;
    replyTo?: string;
}
declare class EmailService {
    private static instance;
    private transporter;
    private config;
    private constructor();
    static getInstance(): EmailService;
    private verifyConnection;
    sendEmail(to: string | string[], template: EmailTemplate, options?: {
        cc?: string | string[];
        bcc?: string | string[];
        attachments?: any[];
    }): Promise<boolean>;
    sendVerificationCode(email: string, code: string, type?: 'register' | 'login' | 'reset_password'): Promise<boolean>;
    sendWelcomeEmail(email: string, username: string): Promise<boolean>;
    sendPasswordResetNotification(email: string, username: string): Promise<boolean>;
    private getVerificationEmailHtml;
    private getWelcomeEmailHtml;
    private getPasswordResetNotificationHtml;
    close(): Promise<void>;
    healthCheck(): Promise<boolean>;
}
export declare const emailService: EmailService;
export {};
//# sourceMappingURL=email.service.d.ts.map