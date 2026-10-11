# ==================== python-service/Dockerfile ====================
# 基础镜像：轻量版 Python 3.12
FROM python:3.12-slim

# Python 运行时优化：不生成 .pyc、日志不缓冲、禁止 pip 缓存
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 工作目录
WORKDIR /app

# 先复制依赖清单并安装，充分利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用源码
COPY . .

# 创建非 root 用户运行，遵循最小权限原则
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# 服务端口
EXPOSE 8000

# 启动命令：生产模式（不加 --reload），监听所有网卡
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
