// 启动脚本 - 修复路径别名问题
const Module = require('module');
const path = require('path');
const fs = require('fs');

// 注册路径别名
const originalRequire = Module.prototype.require;
Module.prototype.require = function(id) {
  if (id.startsWith('@/')) {
    const relativePath = id.substring(2);
    let fullPath = path.resolve(__dirname, 'dist', relativePath);
    
    // 如果没有扩展名，尝试添加.js
    if (!path.extname(fullPath)) {
      const jsPath = fullPath + '.js';
      const indexPath = path.join(fullPath, 'index.js');
      
      if (fs.existsSync(jsPath)) {
        fullPath = jsPath;
      } else if (fs.existsSync(indexPath)) {
        fullPath = indexPath;
      }
    }
    
    try {
      return originalRequire.call(this, fullPath);
    } catch (error) {
      console.error(`Failed to require ${id} -> ${fullPath}:`, error.message);
      throw error;
    }
  }
  return originalRequire.call(this, id);
};

// 启动应用
try {
  require('./dist/app.js');
} catch (error) {
  console.error('Failed to start application:', error);
  process.exit(1);
}