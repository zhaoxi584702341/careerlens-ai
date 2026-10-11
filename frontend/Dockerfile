# ==================== frontend/Dockerfile ====================
# 多阶段构建：编译阶段用 Node 生成静态资源，运行阶段用 Nginx 托管

# ---------- 阶段一：构建静态资源 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 先复制依赖清单并安装，利用层缓存
COPY package.json package-lock.json ./
RUN npm ci

# 复制源码与配置，执行生产构建（vue-tsc + vite build → dist/）
COPY . .
RUN npm run build

# ---------- 阶段二：Nginx 托管 ----------
FROM nginx:alpine

# 覆盖默认站点配置：监听 80，托管 dist，反代 /api/ 到 bff:3000
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物到 Nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
