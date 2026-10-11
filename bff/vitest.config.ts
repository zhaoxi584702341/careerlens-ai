/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'

// BFF 测试配置：使用 Node 环境 + 全局 API（describe / it / expect 等）
export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    include: ['tests/**/*.test.ts'],
    // 测试涉及 SQLite 文件读写，串行执行避免并发写冲突
    fileParallelism: false,
  },
})
