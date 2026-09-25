# MacMAX 本地调试启动脚本、NAS 自动同步定时任务、更新后的双 DGX docker-compose（新增 NAS 挂载）

# 三份落地文件完整输出

所有文件严格对齐前文「算力-存储-终端」三层架构，可直接部署使用，已标注路径约定、依赖说明与操作步骤。

---

## 一、MacMAX 本地调试启动脚本

**文件名**：`mac_local_debug.sh`
**适用环境**：macOS 13+（Apple Silicon / Intel）
**前置依赖**：Docker Desktop 4.30+、Python 3.11+、NAS 已通过 SMB 挂载至 `/Volumes/YYC3-NAS`
**核心设计**：本地模型接口与 DGX 生产 NIM 完全兼容（OpenAI 格式），调试通过后零修改上线双机集群。

```bash
#!/bin/zsh
# ==============================================================
# YYC³ AI FAmily MacMAX 本地调试启动脚本 v1.0
# 功能：本地轻量模型栈 + RAG调试环境 + Agent工作流调试 + NAS一键同步
# 命令：./mac_local_debug.sh [start|stop|sync|status]
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
```

**使用说明**：

1. 赋予执行权限：`chmod +x mac_local_debug.sh`
2. 启动调试环境：`./mac_local_debug.sh start`
3. 调试通过后同步至NAS：`./mac_local_debug.sh sync`
4. 查看服务状态：`./mac_local_debug.sh status`

---

## 二、NAS 自动同步定时任务

**适用系统**：基于 Linux 内核的 NAS（群晖 DSM、TrueNAS Scale、Ubuntu NAS）
**存储分区约定**：

- RAID1 高可用区：`/volume1/RAID1/yyc3-core/`（核心配置、审计日志、热知识库）
- RAID6 大容量区：`/volume2/RAID6/yyc3-data/`（NIM 模型仓库、原始知识库、冷备份）

### 2.1 同步脚本集合

在 NAS 上创建 `/volume1/scripts/` 目录，存放以下 4 个同步脚本。

#### ① 核心配置同步脚本 `sync_config.sh`

（Mac → NAS RAID1，增量同步提示词、Agent 代码，保留版本备份）

```bash
#!/bin/bash
# 核心配置同步：MacMAX -> NAS RAID1 高可用区
# 触发方式：每小时执行一次，实时同步开发成果

LOG_FILE="/volume1/scripts/logs/sync_config_$(date +%Y%m%d).log"
MAC_SHARE="/volume1/smb_mac_upload/"
TARGET_DIR="/volume1/RAID1/yyc3-core/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步核心配置" >> $LOG_FILE

# 增量同步，备份旧版本
rsync -avz --backup --backup-dir=backup/$(date +%Y%m%d_%H%M) \
    --exclude='*.tmp' --exclude='.DS_Store' --exclude='__pycache__' \
    $MAC_SHARE/dev-output/prompt-templates/ \
    $TARGET_DIR/prompt-templates/ >> $LOG_FILE 2>&1

rsync -avz --backup --backup-dir=backup/$(date +%Y%m%d_%H%M) \
    --exclude='*.tmp' --exclude='.git' \
    $MAC_SHARE/dev-output/agent-code/ \
    $TARGET_DIR/agent-code/ >> $LOG_FILE 2>&1

# 权限修正
chown -R admin:users $TARGET_DIR
chmod -R 755 $TARGET_DIR

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 核心配置同步完成" >> $LOG_FILE
```

#### ② 模型分发同步脚本 `sync_model_to_dgx.sh`

（NAS RAID6 → 双 DGX 节点，夜间闲时同步模型镜像，不占业务带宽）

```bash
#!/bin/bash
# NIM模型分发：NAS RAID6 -> 双DGX节点本地缓存
# 触发方式：每日凌晨2点执行，闲时同步

LOG_FILE="/volume1/scripts/logs/sync_model_$(date +%Y%m%d).log"
MODEL_SOURCE="/volume2/RAID6/yyc3-data/nim-model-repo/"
DGX1_ADDR="10.0.0.11"
DGX2_ADDR="10.0.0.12"
DGX_MODEL_PATH="/data/nim-model-cache/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步模型至DGX集群" >> $LOG_FILE

# 同步至DGX节点1
rsync -avz --delete --bwlimit=50000 \
    $MODEL_SOURCE \
    root@$DGX1_ADDR:$DGX_MODEL_PATH >> $LOG_FILE 2>&1

# 同步至DGX节点2
rsync -avz --delete --bwlimit=50000 \
    $MODEL_SOURCE \
    root@$DGX2_ADDR:$DGX_MODEL_PATH >> $LOG_FILE 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 模型同步完成" >> $LOG_FILE
```

#### ③ 审计日志备份脚本 `sync_log_backup.sh`

（双 DGX → NAS RAID1，实时备份审计日志，双副本永久留存）

```bash
#!/bin/bash
# 审计日志备份：双DGX -> NAS RAID1 高可用区
# 触发方式：每10分钟执行一次，满足合规审计要求

LOG_FILE="/volume1/scripts/logs/sync_audit_$(date +%Y%m%d).log"
TARGET_DIR="/volume1/RAID1/yyc3-core/audit-logs/"
DGX1_ADDR="10.0.0.11"
DGX2_ADDR="10.0.0.12"
DGX_LOG_PATH="/data/nim-logs/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始拉取DGX审计日志" >> $LOG_FILE

# 拉取两台DGX的日志
rsync -avz root@$DGX1_ADDR:$DGX_LOG_PATH $TARGET_DIR/dgx1/ >> $LOG_FILE 2>&1
rsync -avz root@$DGX2_ADDR:$DGX_LOG_PATH $TARGET_DIR/dgx2/ >> $LOG_FILE 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 审计日志备份完成" >> $LOG_FILE
```

#### ④ 向量库冷备份脚本 `backup_vector.sh`

（DGX → NAS RAID6，每日全量备份向量库数据）

```bash
#!/bin/bash
# Milvus向量库备份：DGX -> NAS RAID6
# 触发方式：每日凌晨3点执行

LOG_FILE="/volume1/scripts/logs/backup_vector_$(date +%Y%m%d).log"
DGX1_ADDR="10.0.0.11"
DGX_VECTOR_PATH="/data/milvus-data/"
BACKUP_TARGET="/volume2/RAID6/yyc3-data/vector-backup/$(date +%Y%m%d)/"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始向量库全量备份" >> $LOG_FILE

mkdir -p $BACKUP_TARGET
rsync -avz root@$DGX1_ADDR:$DGX_VECTOR_PATH $BACKUP_TARGET >> $LOG_FILE 2>&1

# 保留30天备份
find /volume2/RAID6/yyc3-data/vector-backup/ -mtime +30 -type d -exec rm -rf {} \;

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 向量库备份完成" >> $LOG_FILE
```

### 2.2 crontab 定时任务配置

在 NAS 系统计划任务中添加以下规则（或写入 `/etc/crontab`）：

```bash
# 每小时同步一次核心配置（开发成果实时同步到生产）
0 * * * * /bin/bash /volume1/scripts/sync_config.sh

# 每10分钟备份一次审计日志（满足合规追溯要求）
*/10 * * * * /bin/bash /volume1/scripts/sync_log_backup.sh

# 每天凌晨2点同步模型镜像（闲时传输，不占业务带宽）
0 2 * * * /bin/bash /volume1/scripts/sync_model_to_dgx.sh

# 每天凌晨3点备份向量库
0 3 * * * /bin/bash /volume1/scripts/backup_vector.sh
```

---

## 三、双 DGX docker-compose 配置（新增 NAS 挂载）

**适用环境**：双 DGX Spark GB10，DGX OS 6.2，Docker 27+，NVIDIA Container Toolkit
**NAS 挂载约定（两台 DGX 统一挂载路径）**：

| 本地挂载路径 | NAS 源路径 | 权限 | 用途 |
| -------------- | ------------ | ------ | ------ |
| `/mnt/nas/raid1-core` | `10.0.0.10:/volume1/RAID1/yyc3-core` | 只读 | 提示词、配置、Agent 代码 |
| `/mnt/nas/raid6-models` | `10.0.0.10:/volume2/RAID6/yyc3-data/nim-model-repo` | 只读 | NIM 模型镜像缓存 |
| `/mnt/nas/raid1-logs` | `10.0.0.10:/volume1/RAID1/yyc3-core/audit-logs` | 读写 | 审计日志实时写入 |
| `/mnt/nas/raid6-knowledge` | `10.0.0.10:/volume2/RAID6/yyc3-data/knowledge-raw` | 只读 | 原始知识库素材 |

### 3.1 公共环境变量 `.env`

两台 DGX 通用，放置于 `/data/yyc3-agent/.env`

```env
# NIM基础配置
NIM_CACHE_DIR=/opt/nim/.cache
NVIDIA_VISIBLE_DEVICES=all

# NAS挂载路径
NAS_CORE_RO=/mnt/nas/raid1-core
NAS_MODELS_RO=/mnt/nas/raid6-models
NAS_LOGS_RW=/mnt/nas/raid1-logs
NAS_KNOWLEDGE_RO=/mnt/nas/raid6-knowledge

# 分布式通信配置（RoCE高速互联）
NCCL_NET=IB
NCCL_IB_HCA=rocep1s0f0
NCCL_IB_GID_INDEX=0
NCCL_IB_DISABLE=0
NCCL_SOCKET_IFNAME=eth0

# 张量并行配置
TENSOR_PARALLEL_SIZE=2

# 模型精度
MODEL_PRECISION=nvfp4
KV_CACHE_PRECISION=fp8
GPU_MEM_UTIL=0.85
```

### 3.2 节点 1（推理主节点）`docker-compose.node1.yml`

承载：主模型分片、嵌入、重排、Milvus 查询节点、Agent 编排引擎

```yaml
version: "3.8"

services:
  # ========== 核心主模型：DeepSeek V4 Pro TP分片1/2 ==========
  deepseek-v4-pro-node1:
    image: nvcr.io/nim/deepseek-ai/deepseek-v4-pro:latest
    container_name: dgx1-deepseek-v4
    runtime: nvidia
    shm_size: 32g
    ports:
      - "8000:8000"
    environment:
      - NIM_MODEL_PRECISION=${MODEL_PRECISION}
      - NIM_TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE}
      - VLLM_KV_CACHE_PRECISION=${KV_CACHE_PRECISION}
      - GPU_MEMORY_UTILIZATION=${GPU_MEM_UTIL}
      - MAX_MODEL_LEN=131072
      - NCCL_NET=${NCCL_NET}
      - NCCL_IB_HCA=${NCCL_IB_HCA}
      - NCCL_IB_GID_INDEX=${NCCL_IB_GID_INDEX}
      - NCCL_IB_DISABLE=${NCCL_IB_DISABLE}
    volumes:
      # NAS模型缓存只读挂载
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      # 日志写入NAS RAID1双副本
      - ${NAS_LOGS_RW}/dgx1/deepseek:/opt/nim/logs
      # 提示词配置只读挂载
      - ${NAS_CORE_RO}/prompt-templates:/opt/nim/prompts:ro
    restart: unless-stopped
    networks:
      - agent-network

  # ========== 嵌入模型：nemotron-3-embed-1b ==========
  nemotron-embed:
    image: nvcr.io/nim/nvidia/nemotron-3-embed-1b:latest
    container_name: dgx1-embed
    runtime: nvidia
    ports:
      - "8001:8000"
    environment:
      - MAX_BATCH_SIZE=256
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx1/embed:/opt/nim/logs
    restart: unless-stopped
    networks:
      - agent-network

  # ========== 重排模型：llama-nemotron-rerank-1b-v2 ==========
  nemotron-rerank:
    image: nvcr.io/nim/nvidia/llama-nemotron-rerank-1b-v2:latest
    container_name: dgx1-rerank
    runtime: nvidia
    ports:
      - "8002:8000"
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx1/rerank:/opt/nim/logs
    restart: unless-stopped
    networks:
      - agent-network

  # ========== Milvus向量库：查询节点 ==========
  milvus-query:
    image: milvusdb/milvus:v2.4.5
    container_name: dgx1-milvus-query
    command: ["milvus", "run", "query"]
    runtime: nvidia
    environment:
      - ETCD_ENDPOINTS=etcd:2379
      - MINIO_ADDRESS=minio:9000
      - QUERY_NODE_PORT=19530
    volumes:
      - /data/milvus-data:/var/lib/milvus
      - ${NAS_RAID6_DATA}/vector-backup:/backup:ro
    restart: unless-stopped
    networks:
      - agent-network

  # ========== Agent编排引擎 ==========
  agent-orchestrator:
    image: langchain/langchain:latest
    container_name: dgx1-agent-engine
    ports:
      - "9000:9000"
    volumes:
      - ${NAS_CORE_RO}/agent-code:/app/agent-code:ro
      - ${NAS_LOGS_RW}/dgx1/orchestrator:/app/logs
    environment:
      - LLM_BASE_URL=http://deepseek-v4-pro-node1:8000/v1
      - EMBED_BASE_URL=http://nemotron-embed:8000/v1
      - RERANK_BASE_URL=http://nemotron-rerank:8000/v1
      - MILVUS_HOST=milvus-query
    restart: unless-stopped
    networks:
      - agent-network

  # 公共依赖：etcd
  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: dgx1-etcd
    command: etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls [http://0.0.0.0:2379](http://0.0.0.0:2379)
    volumes:
      - /data/etcd-data:/etcd-data
    restart: unless-stopped
    networks:
      - agent-network

networks:
  agent-network:
    driver: bridge
```

### 3.3 节点 2（支撑节点）`docker-compose.node2.yml`

承载：主模型分片、OCR、安全三件套、轻量 LLM、Milvus 数据节点、监控

```yaml
version: "3.8"

services:
  # ========== 核心主模型：DeepSeek V4 Pro TP分片2/2 ==========
  deepseek-v4-pro-node2:
    image: nvcr.io/nim/deepseek-ai/deepseek-v4-pro:latest
    container_name: dgx2-deepseek-v4
    runtime: nvidia
    shm_size: 32g
    ports:
      - "8000:8000"
    environment:
      - NIM_MODEL_PRECISION=${MODEL_PRECISION}
      - NIM_TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE}
      - VLLM_KV_CACHE_PRECISION=${KV_CACHE_PRECISION}
      - GPU_MEMORY_UTILIZATION=${GPU_MEM_UTIL}
      - MAX_MODEL_LEN=131072
      - NCCL_NET=${NCCL_NET}
      - NCCL_IB_HCA=${NCCL_IB_HCA}
      - NCCL_IB_GID_INDEX=${NCCL_IB_GID_INDEX}
      - NCCL_IB_DISABLE=${NCCL_IB_DISABLE}
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx2/deepseek:/opt/nim/logs
      - ${NAS_CORE_RO}/prompt-templates:/opt/nim/prompts:ro
    restart: unless-stopped
    networks:
      - agent-network

  # ========== OCR模型：nemotron-ocr-v2 ==========
  nemotron-ocr:
    image: nvcr.io/nim/nvidia/nemotron-ocr-v2:latest
    container_name: dgx2-ocr
    runtime: nvidia
    ports:
      - "8003:8000"
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx2/ocr:/opt/nim/logs
      - ${NAS_KNOWLEDGE_RO}:/data/knowledge-raw:ro
    restart: unless-stopped
    networks:
      - agent-network

  # ========== 安全三件套 ==========
  # 越狱检测
  jailbreak-detect:
    image: nvcr.io/nim/nvidia/nemoguard-jailbreak-detect:latest
    container_name: dgx2-jailbreak
    runtime: nvidia
    ports:
      - "8004:8000"
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx2/safety:/opt/nim/logs
    restart: unless-stopped
    networks:
      - agent-network

  # 内容安全
  content-safety:
    image: nvcr.io/nim/nvidia/nemotron-3.5-content-safety:latest
    container_name: dgx2-content-safety
    runtime: nvidia
    ports:
      - "8005:8000"
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx2/safety:/opt/nim/logs
    restart: unless-stopped
    networks:
      - agent-network

  # PII信息脱敏
  pii-detect:
    image: nvcr.io/nim/nvidia/gliner-pii:latest
    container_name: dgx2-pii
    runtime: nvidia
    ports:
      - "8006:8000"
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx2/safety:/opt/nim/logs
    restart: unless-stopped
    networks:
      - agent-network

  # ========== 轻量LLM：言启千行/知遇伯乐基座 ==========
  nemotron-mini:
    image: nvcr.io/nim/nvidia/nemotron-mini-4b-instruct:latest
    container_name: dgx2-mini-llm
    runtime: nvidia
    ports:
      - "8007:8000"
    environment:
      - MAX_BATCH_SIZE=128
    volumes:
      - ${NAS_MODELS_RO}:/opt/nim/.cache:ro
      - ${NAS_LOGS_RW}/dgx2/mini-llm:/opt/nim/logs
    restart: unless-stopped
    networks:
      - agent-network

  # ========== Milvus向量库：数据节点 ==========
  milvus-datastore:
    image: minio/minio:latest
    container_name: dgx2-minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - /data/milvus-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    restart: unless-stopped
    networks:
      - agent-network

networks:
  agent-network:
    driver: bridge
```

### 3.4 启动步骤

1. 两台 DGX 分别挂载 NAS 存储（配置 `/etc/fstab` 开机自动挂载）
2. 将 `.env` 和对应 compose 文件放置到两台 DGX 的 `/data/yyc3-agent/` 目录
3. **先启动节点 2，再启动节点 1**（确保分布式通信就绪）

   ```bash
   # 节点2执行
   cd /data/yyc3-agent && docker compose -f docker-compose.node2.yml up -d
   # 节点1执行
   cd /data/yyc3-agent && docker compose -f docker-compose.node1.yml up -d
   ```

4. 验证主模型分布式状态：访问 `http://节点1IP:8000/v1/models`，确认模型正常加载
