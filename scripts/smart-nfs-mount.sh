#!/bin/bash

# @file smart-nfs-mount.sh
# @description 智能NFS挂载脚本 - 自动检测、挂载、验证
# @author YanYuCloudCube Team <admin@0379.email>
# @version: v1.0.0
# @created: 2026-04-08
# @updated: 2026-04-08
# @status: active
# @tags: nfs,mount,automation

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

# NFS配置
NFS_SERVER="192.168.3.45"
NFS_EXPORT="/Volume2/yyc3-33"
MOUNT_POINT="$HOME/nfs_vpn_mount"

# 检测NFS服务器
detect_nfs_server() {
    log_step "检测NFS服务器..."
    
    if ping -c 1 -W 2 $NFS_SERVER > /dev/null 2>&1; then
        log_info "NFS服务器 $NFS_SERVER 可达"
        return 0
    else
        log_error "NFS服务器 $NFS_SERVER 不可达"
        return 1
    fi
}

# 检测NFS导出
detect_nfs_exports() {
    log_step "检测NFS导出..."
    
    if showmount -e $NFS_SERVER > /dev/null 2>&1; then
        log_info "NFS导出检测成功"
        showmount -e $NFS_SERVER
        return 0
    else
        log_error "NFS导出检测失败"
        return 1
    fi
}

# 创建挂载点
create_mount_point() {
    log_step "创建挂载点..."
    
    if [ -d "$MOUNT_POINT" ]; then
        log_info "挂载点已存在: $MOUNT_POINT"
    else
        mkdir -p "$MOUNT_POINT"
        log_info "创建挂载点: $MOUNT_POINT"
    fi
}

# 挂载NFS
mount_nfs() {
    log_step "挂载NFS..."
    
    # 检查是否已挂载
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        log_info "NFS已挂载: $MOUNT_POINT"
        return 0
    fi
    
    # 挂载NFS
    if mount -t nfs -o resvport,rw $NFS_SERVER:$NFS_EXPORT "$MOUNT_POINT"; then
        log_info "NFS挂载成功: $MOUNT_POINT"
        return 0
    else
        log_error "NFS挂载失败"
        return 1
    fi
}

# 验证挂载
verify_mount() {
    log_step "验证挂载..."
    
    if mountpoint -q "$MOUNT_POINT"; then
        log_info "挂载验证成功"
        df -h "$MOUNT_POINT"
        return 0
    else
        log_error "挂载验证失败"
        return 1
    fi
}

# 检查模型目录
check_models() {
    log_step "检查模型目录..."
    
    if [ -d "$MOUNT_POINT/models" ]; then
        log_info "模型目录存在"
        ls -lh "$MOUNT_POINT/models" 2>/dev/null || log_warn "无法列出模型目录"
    else
        log_warn "模型目录不存在: $MOUNT_POINT/models"
    fi
    
    if [ -d "$MOUNT_POINT/ollama" ]; then
        log_info "Ollama模型目录存在"
        ls -lh "$MOUNT_POINT/ollama" 2>/dev/null || log_warn "无法列出Ollama目录"
    else
        log_warn "Ollama模型目录不存在: $MOUNT_POINT/ollama"
    fi
}

# 配置自动挂载
setup_auto_mount() {
    log_step "配置自动挂载..."
    
    # macOS使用autofs或fstab
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # 检查/etc/fstab
        if grep -q "$NFS_SERVER:$NFS_EXPORT" /etc/fstab 2>/dev/null; then
            log_info "自动挂载已配置"
        else
            log_info "添加自动挂载配置到 /etc/fstab"
            echo "$NFS_SERVER:$NFS_EXPORT $MOUNT_POINT nfs resvport,rw 0 0" | sudo tee -a /etc/fstab
            log_info "自动挂载配置完成"
        fi
    else
        # Linux使用fstab
        if grep -q "$NFS_SERVER:$NFS_EXPORT" /etc/fstab 2>/dev/null; then
            log_info "自动挂载已配置"
        else
            log_info "添加自动挂载配置到 /etc/fstab"
            echo "$NFS_SERVER:$NFS_EXPORT $MOUNT_POINT nfs defaults 0 0" | sudo tee -a /etc/fstab
            log_info "自动挂载配置完成"
        fi
    fi
}

# 主函数
main() {
    log_info "=========================================="
    log_info "YYC³ 智能NFS挂载脚本"
    log_info "=========================================="
    echo ""
    
    # 1. 检测NFS服务器
    if ! detect_nfs_server; then
        log_error "NFS服务器不可达，退出"
        exit 1
    fi
    echo ""
    
    # 2. 检测NFS导出
    if ! detect_nfs_exports; then
        log_error "NFS导出检测失败，退出"
        exit 1
    fi
    echo ""
    
    # 3. 创建挂载点
    create_mount_point
    echo ""
    
    # 4. 挂载NFS
    if ! mount_nfs; then
        log_error "NFS挂载失败，退出"
        exit 1
    fi
    echo ""
    
    # 5. 验证挂载
    if ! verify_mount; then
        log_error "挂载验证失败，退出"
        exit 1
    fi
    echo ""
    
    # 6. 检查模型目录
    check_models
    echo ""
    
    # 7. 配置自动挂载
    setup_auto_mount
    echo ""
    
    log_info "=========================================="
    log_info "NFS挂载完成！"
    log_info "挂载点: $MOUNT_POINT"
    log_info "=========================================="
}

# 执行主函数
main "$@"
