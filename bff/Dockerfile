# ==================== bff/Dockerfile ====================
# 基础镜像：轻量 alpine 版 Node 20
FROM node:20-alpine

# 生产模式
ENV NODE_ENV=production \
    PORT=3000

WORKDIR /app

# 先复制依赖清单，利用层缓存安装依赖
COPY package.json package-lock.json ./

# npm ci 严格按 lock 文件安装（含编译 TS 所需的 devDependencies）
# better-sqlite3 为原生模块，需构建工具链编译
RUN apk add --no-cache python3 make g++ \
    && npm ci \
    && apk del python3 make g++

# 复制源码与 TS 配置，执行编译
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# 创建数据目录并交给非 root 用户，遵循最小权限原则
RUN mkdir -p /app/data && chown -R node:node /app
USER node

EXPOSE 3000

# 启动编译产物
CMD ["node", "dist/index.js"]
