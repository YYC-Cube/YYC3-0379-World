#!/bin/bash

# setup-model-mounts.sh - 模型挂载管理脚本
# @file: setup-model-mounts.sh
# @description: 在所有节点上配置NFS模型挂载
# @author: YanYuCloudCube Team <admin@0379.email>
# @version: v1.0.0
# @created: 2026-04-08
# @updated: 2026-04-08
# @status: active
# @tags: deployment,nfs,mounts

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# NFS服务器配置
NFS_SERVER="192.168.3.45"
NFS_EXPORT="/volume1/models"

# 挂载点配置
declare -A MOUNT_POINTS=(
    ["ollama"]="/models/ollama"
    ["huggingface"]="/models/huggingface"
    ["checkpoints"]="/models/checkpoints"
    ["lora"]="/models/lora"
    ["config"]="/models/config"
)

# 节点列表
NODES=("yyc3-22" "yyc3-33" "yyc3-45" "yyc3-77")

# 检查NFS服务器连接
check_nfs_server() {
    log_step "Checking NFS server connectivity..."
    
    if ping -c 1 $NFS_SERVER > /dev/null 2>&1; then
        log_info "NFS server $NFS_SERVER is reachable"
    else
        log_error "NFS server $NFS_SERVER is not reachable!"
        exit 1
    fi
}

# 在单个节点上设置挂载
setup_node_mounts() {
    local node=$1
    
    log_step "Setting up model mounts on $node..."
    
    ssh $node << 'EOF'
        # 创建挂载点目录
        for mount_point in /models/ollama /models/huggingface /models/checkpoints /models/lora /models/config; do
            mkdir -p $mount_point
        done
        
        # 检查是否已挂载
        if mountpoint -q /models/ollama; then
            echo "[INFO] Models already mounted"
            exit 0
        fi
        
        # 挂载NFS
        mount -t nfs 192.168.3.45:/volume1/models/ollama /models/ollama
        mount -t nfs 192.168.3.45:/volume1/models/huggingface /models/huggingface
        mount -t nfs 192.168.3.45:/volume1/models/checkpoints /models/checkpoints
        mount -t nfs 192.168.3.45:/volume1/models/lora /models/lora
        mount -t nfs 192.168.3.45:/volume1/models/config /models/config
        
        # 验证挂载
        df -h | grep /models
        
        echo "[INFO] Model mounts setup completed"
EOF
    
    if [ $? -eq 0 ]; then
        log_info "Successfully setup mounts on $node"
    else
        log_error "Failed to setup mounts on $node"
    fi
}

# 配置自动挂载
configure_automount() {
    local node=$1
    
    log_step "Configuring automount on $node..."
    
    ssh $node << 'EOF'
        # 备份fstab
        cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)
        
        # 添加NFS挂载到fstab
        cat >> /etc/fstab << FSTAB
# YYC³ Model Mounts
192.168.3.45:/volume1/models/ollama /models/ollama nfs defaults 0 0
192.168.3.45:/volume1/models/huggingface /models/huggingface nfs defaults 0 0
192.168.3.45:/volume1/models/checkpoints /models/checkpoints nfs defaults 0 0
192.168.3.45:/volume1/models/lora /models/lora nfs defaults 0 0
192.168.3.45:/volume1/models/config /models/config nfs defaults 0 0
FSTAB
        
        echo "[INFO] Automount configured"
EOF
    
    log_info "Automount configured on $node"
}

# 验证挂载
verify_mounts() {
    local node=$1
    
    log_step "Verifying mounts on $node..."
    
    ssh $node << 'EOF'
        for mount_point in /models/ollama /models/huggingface /models/checkpoints /models/lora /models/config; do
            if mountpoint -q $mount_point; then
                echo "[OK] $mount_point is mounted"
            else
                echo "[FAIL] $mount_point is not mounted"
            fi
        done
EOF
}

# 主流程
main() {
    log_info "Starting YYC³ Model Mount Setup..."
    log_info "NFS Server: $NFS_SERVER"
    log_info "Nodes: ${NODES[*]}"
    
    # 检查NFS服务器
    check_nfs_server
    
    # 在所有节点上设置挂载
    for node in "${NODES[@]}"; do
        log_info "Processing node: $node"
        
        # 设置挂载
        setup_node_mounts $node
        
        # 配置自动挂载
        configure_automount $node
        
        # 验证挂载
        verify_mounts $node
        
        echo ""
    done
    
    log_info "Model mount setup completed successfully!"
    log_info "Mount points:"
    for name in "${!MOUNT_POINTS[@]}"; do
        echo "  - ${MOUNT_POINTS[$name]} ($name)"
    done
}

# 运行主流程
main "$@"
