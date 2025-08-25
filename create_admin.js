const bcrypt = require('bcryptjs');
const sqlite3 = require('sqlite3').verbose();

async function createAdminUser() {
  try {
    // 生成密码哈希
    const password = 'Admin123!';
    const hashedPassword = await bcrypt.hash(password, 12);
    
    // 连接数据库
    const db = new sqlite3.Database('./data/trademe.db');
    
    // 插入管理员用户
    const query = `
      INSERT INTO users (
        username, email, password_hash, membership_level, 
        email_verified, is_active, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
    `;
    
    db.run(query, [
      'admin',
      'admin@trademe.com',
      hashedPassword,
      'professional', // 最高等级会员
      true,           // 邮箱已验证
      true            // 账户激活
    ], function(err) {
      if (err) {
        if (err.message.includes('UNIQUE constraint failed')) {
          console.log('管理员账户已存在');
        } else {
          console.error('创建管理员账户失败:', err.message);
        }
      } else {
        console.log('✅ 管理员账户创建成功！');
        console.log('邮箱: admin@trademe.com');
        console.log('密码: Admin123!');
        console.log('用户ID:', this.lastID);
      }
      
      db.close();
    });
    
  } catch (error) {
    console.error('创建管理员账户时出错:', error);
  }
}

createAdminUser();