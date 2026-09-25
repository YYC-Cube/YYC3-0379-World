# YYC³ NAS 部署目录专用 Dockerfile（构建上下文 = 部署目录：app/ + core/agents + requirements.txt）
# 与根 Dockerfile 等价，仅 COPY 路径适配 NAS 同步布局（deploy-nas-gateway.sh 的 rsync 产物）
# 差异说明：根 Dockerfile COPY core/api/（仓库上下文）；本文件 COPY app/（部署目录上下文）

FROM python:3.11-slim AS base

LABEL maintainer="YanYuCloudCube Team <admin@0379.email>"
LABEL description="YYC³ 0379-world NAS Gateway + A2A Worker/Orchestrator"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

FROM base AS builder
COPY requirements.txt .
# NAS 国内环境默认清华源
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --user -i $PIP_INDEX_URL -r requirements.txt

FROM base AS production
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 部署目录布局：app/（= core/api）+ core/agents（Agent Worker 依赖）
COPY app/ /app/app/
COPY core/agents/ /app/core/agents/

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/ping', timeout=5)" || exit 1

# 网关缺省命令；Worker/编排器容器经 compose command 覆盖（python -m app.worker_entry 等）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info"]
