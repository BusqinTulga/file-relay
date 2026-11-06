# 第一阶段：构建前端主题
# 前端产物与 CPU 架构无关，使用原生构建平台避免在 QEMU 中运行 Node/pnpm。
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-builder

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate
WORKDIR /build/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --prod=false
COPY frontend/ ./
ARG VCS_REF=unknown
RUN VITE_GIT_COMMIT="$VCS_REF" pnpm run build

# 第二阶段：构建最终镜像
FROM python:3.12-slim-bookworm
ARG APP_VERSION
ARG VCS_REF=unknown
LABEL author="Lan"
LABEL email="xzu@live.com"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.revision="${VCS_REF}"

WORKDIR /app

COPY requirements.lock.txt ./

# 分支镜像使用带提交号的开发版本；正式镜像使用 VERSION 中的版本。
ENV APP_VERSION="${APP_VERSION}"

# 设置时区
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo 'Asia/Shanghai' > /etc/timezone

# 安装系统安全更新 + Python 依赖
# 依赖从带哈希的锁定文件安装（--require-hashes），保证构建可复现、防供应链篡改。
# 清理 apt 缓存，降低镜像噪音与扫描面
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --require-hashes -r requirements.lock.txt \
 && pip cache purge

COPY . .
COPY --from=frontend-builder /build/themes/2024 ./themes/2024

# 环境变量配置
ENV HOST="0.0.0.0" \
    PORT=12345 \
    WORKERS=1 \
    APP_ENV="production" \
    LOG_LEVEL="warning" \
    ACCESS_LOG="false" \
    FORWARDED_ALLOW_IPS="" \
    TIMEOUT_KEEP_ALIVE=5 \
    MALLOC_TRIM_THRESHOLD_=65536

EXPOSE 12345

# 生产环境启动命令
# FORWARDED_ALLOW_IPS 默认为空：仅信任直连 IP，避免任意客户端伪造 X-Forwarded-*。
# 若前面有反向代理，请显式设置为代理网段，例如 "10.0.0.0/8,172.16.0.0/12"。
# 容器以 root 运行：兼容存量 root 属主的数据卷，以及 NAS/只读 bind mount。
CMD ["sh", "-c", "access_log_arg=--no-access-log; if [ \"${APP_ENV:-development}\" != \"production\" ] || [ \"${ACCESS_LOG:-false}\" = \"true\" ]; then access_log_arg=--access-log; fi; exec uvicorn main:app --host \"$HOST\" --port \"$PORT\" --workers \"$WORKERS\" --log-level \"$LOG_LEVEL\" \"$access_log_arg\" --timeout-keep-alive \"${TIMEOUT_KEEP_ALIVE:-5}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-}\""]
