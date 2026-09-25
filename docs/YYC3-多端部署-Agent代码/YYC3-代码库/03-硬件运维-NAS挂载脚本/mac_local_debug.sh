#!/bin/zsh
# ==============================================================
# YYC³ AI FAmily MacMAX 本地调试启动脚本 v1.0
# 功能：本地轻量模型栈 + RAG调试环境 + Agent工作流调试 + NAS一键同步
# 命令：./mac_local_debug.sh [start|stop|sync|status]
# 适用环境：macOS 13+（Apple Silicon / Intel）
# 前置依赖：Docker Desktop 4.30+、Python 3.11+、NAS已通过SMB挂载至 /Volumes/YYC3-NAS
# 核心设计：本地模型接口与DGX生产NIM完全兼容（OpenAI格式），调试通过后零修改上线
# ==============================================================

# -------------------------- 配置项 --------------------------
# 本地工作目录
LOCAL_WORKSPACE="$HOME/YYC3-Agent-Dev"
# 本地模型缓存目录
LOCAL_MODEL_CACHE="$LOCAL_WORKSPACE/model-cache"
# NAS挂载路径（SMB挂载后对应RAID1/RAID6分区）
NAS_RAID1_CORE="/Volumes/YYC3-NAS/RAID1/yyc3-core"
NAS_RAID6_DATA="/Volumes/YYC3-NAS/RAID6/yyc3-data"
# 本地服务端口（与生产环境完全一致，无缝切换）
PORT_LLM=8000       # 轻量基座模型
PORT_EMBED=8001     # 嵌入模型
PORT_RERANK=8002    # 重排模型
PORT_SAFETY=8003    # 安全检测
PORT_MILVUS=19530   # 本地向量库

# -------------------------- 环境检查 --------------------------
check_env() {
    echo "🔍 环境依赖检查中..."
    # Docker检查
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker Desktop 未启动，请先启动后重试"
        exit 1
    fi
    # NAS挂载检查
    if [ ! -d "$NAS_RAID1_CORE" ]; then
        echo "⚠️  NAS未挂载，仅支持本地离线调试，同步功能不可用"
        NAS_READY=false
    else
        NAS_READY=true
        echo "✅ NAS存储已连接"
    fi
    # 创建工作目录
    mkdir -p $LOCAL_WORKSPACE/{prompt-templates,agent-code,dataset,model-cache,logs}
    echo "✅ 环境检查完成"
}

# -------------------------- 启动本地调试栈 --------------------------
start_local() {
    check_env
    echo "🚀 启动 AI FAmily 本地调试环境..."

    # 1. 启动本地轻量基座模型（nemotron-mini-4b，接口兼容NIM OpenAI格式）
    # 用于调试言启千行、知遇伯乐、轻量推理逻辑
    docker run -d --name local-nemotron-mini \
        -p $PORT_LLM:8000 \
        -v $LOCAL_MODEL_CACHE:/opt/nim/.cache \
        -e NIM_MODEL_PRECISION=fp16 \
        --restart unless-stopped \
        nvcr.io/nim/nvidia/nemotron-mini-4b-instruct:latest > /dev/null 2>&1
    echo "✅ 轻量基座模型(nemotron-mini-4b)启动，端口$PORT_LLM"

    # 2. 启动嵌入模型（与生产环境完全一致）
    docker run -d --name local-embed \
        -p $PORT_EMBED:8000 \
        -v $LOCAL_MODEL_CACHE:/opt/nim/.cache \
        --restart unless-stopped \
        nvcr.io/nim/nvidia/nemotron-3-embed-1b:latest > /dev/null 2>&1
    echo "✅ 嵌入模型(nemotron-3-embed-1b)启动，端口$PORT_EMBED"

    # 3. 启动重排模型
    docker run -d --name local-rerank \
        -p $PORT_RERANK:8000 \
        -v $LOCAL_MODEL_CACHE:/opt/nim/.cache \
        --restart unless-stopped \
        nvcr.io/nim/nvidia/llama-nemotron-rerank-1b-v2:latest > /dev/null 2>&1
    echo "✅ 重排模型启动，端口$PORT_RERANK"

    # 4. 启动安全检测模型
    docker run -d --name local-safety \
        -p $PORT_SAFETY:8000 \
        -v $LOCAL_MODEL_CACHE:/opt/nim/.cache \
        --restart unless-stopped \
        nvcr.io/nim/nvidia/nemoguard-jailbreak-detect:latest > /dev/null 2>&1
    echo "✅ 安全检测模型启动，端口$PORT_SAFETY"

    # 5. 启动本地Milvus向量库（RAG调试专用）
    docker run -d --name local-milvus \
        -p $PORT_MILVUS:19530 \
        -v $LOCAL_WORKSPACE/milvus-data:/var/lib/milvus \
        -e ETCD_USE_EMBED=true \
        -e MILVUS_STANDALONE=true \
        --restart unless-stopped \
        milvusdb/milvus:v2.4.5 > /dev/null 2>&1
    echo "✅ 本地Milvus向量库启动，端口$PORT_MILVUS"

    echo ""
    echo "🎉 本地调试环境启动完成"
    echo "📌 调试提示：修改Agent代码/提示词后，直接调用本地接口验证，无需占用DGX生产算力"
    echo "📌 生产切换：仅需将接口地址改为DGX集群地址，无需修改业务代码"
}

# -------------------------- 停止本地环境 --------------------------
stop_local() {
    echo "⏹️  停止本地调试环境..."
    docker stop local-nemotron-mini local-embed local-rerank local-safety local-milvus > /dev/null 2>&1
    docker rm local-nemotron-mini local-embed local-rerank local-safety local-milvus > /dev/null 2>&1
    echo "✅ 所有本地服务已停止"
}

# -------------------------- 同步配置至NAS --------------------------
sync_to_nas() {
    if [ "$NAS_READY" = false ]; then
        echo "❌ NAS未连接，无法同步"
        exit 1
    fi
    echo "📤 同步开发配置至NAS RAID1核心区..."

    # 1. 同步提示词模板（增量同步，保留版本备份）
    rsync -avz --backup --backup-dir=backup/$(date +%Y%m%d_%H%M) \
        --exclude='*.tmp' --exclude='.DS_Store' \
        $LOCAL_WORKSPACE/prompt-templates/ \
        $NAS_RAID1_CORE/prompt-templates/
    echo "✅ 提示词模板同步完成"

    # 2. 同步Agent编排代码
    rsync -avz --backup --backup-dir=backup/$(date +%Y%m%d_%H%M) \
        --exclude='__pycache__' --exclude='.git' \
        $LOCAL_WORKSPACE/agent-code/ \
        $NAS_RAID1_CORE/agent-code/
    echo "✅ Agent代码同步完成"

    # 3. 同步预处理后的知识库素材至RAID6冷存储
    rsync -avz --exclude='*.tmp' \
        $LOCAL_WORKSPACE/dataset/cleaned/ \
        $NAS_RAID6_DATA/knowledge-raw/
    echo "✅ 知识库素材同步至RAID6完成"

    echo ""
    echo "✅ 全量同步完成，DGX集群将自动拉取最新配置"
}

# -------------------------- 服务状态检查 --------------------------
status_check() {
    echo "📊 本地调试服务状态："
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "local-|NAMES"
}

# -------------------------- 主入口 --------------------------
case "$1" in
    start)
        start_local
        ;;
    stop)
        stop_local
        ;;
    sync)
        sync_to_nas
        ;;
    status)
        status_check
        ;;
    *)
        echo "用法: ./mac_local_debug.sh [start|stop|sync|status]"
        echo "  start   - 启动本地调试环境"
        echo "  stop    - 停止本地调试环境"
        echo "  sync    - 同步配置/代码至NAS"
        echo "  status  - 查看服务运行状态"
        ;;
esac
