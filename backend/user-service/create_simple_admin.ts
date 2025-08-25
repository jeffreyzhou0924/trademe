import { PrismaClient } from '@prisma/client';
import { hashPassword } from './src/utils/encryption';

const prisma = new PrismaClient();

async function createSimpleAdminUser() {
  try {
    // 使用简单密码避免特殊字符问题
    const password = 'Admin123';
    const hashedPassword = await hashPassword(password);
    
    // 删除旧的管理员账户（如果存在）
    await prisma.user.deleteMany({
      where: { email: 'admin@trademe.com' }
    });
    
    // 创建新的管理员用户
    const adminUser = await prisma.user.create({
      data: {
        username: 'admin',
        email: 'admin@trademe.com',
        passwordHash: hashedPassword,
        membershipLevel: 'professional', // 最高等级会员
        emailVerified: true,             // 邮箱已验证
        isActive: true,                  // 账户激活
        createdAt: new Date(),
        updatedAt: new Date()
      }
    });
    
    console.log('✅ 管理员账户创建成功！');
    console.log('邮箱: admin@trademe.com');
    console.log('密码: Admin123');
    console.log('用户ID:', adminUser.id);
    console.log('用户名:', adminUser.username);
    console.log('会员等级:', adminUser.membershipLevel);
    
  } catch (error) {
    console.error('创建管理员账户时出错:', error);
  } finally {
    await prisma.$disconnect();
  }
}

createSimpleAdminUser();