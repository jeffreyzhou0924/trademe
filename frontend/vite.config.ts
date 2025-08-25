import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react({
    // 使用新的JSX Runtime
    jsxRuntime: 'automatic',
  })],
  
  // 路径解析
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/pages': path.resolve(__dirname, './src/pages'),
      '@/hooks': path.resolve(__dirname, './src/hooks'),
      '@/store': path.resolve(__dirname, './src/store'),
      '@/services': path.resolve(__dirname, './src/services'),
      '@/utils': path.resolve(__dirname, './src/utils'),
      '@/types': path.resolve(__dirname, './src/types'),
      '@/assets': path.resolve(__dirname, './src/assets')
    }
  },
  
  // 开发服务器配置
  server: {
    port: 3000,
    host: '0.0.0.0',  // 明确监听所有地址包括IPv4
    // 使用轮询模式避免EMFILE错误
    watch: {
      usePolling: true,
      interval: 1000
    }
    // API代理已移至nginx，此处不再需要
  },
  
  // 构建配置
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // 代码分割
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['echarts'],
        }
      }
    },
    minify: 'esbuild'
  },
  
  // 测试配置
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts'
  }
})