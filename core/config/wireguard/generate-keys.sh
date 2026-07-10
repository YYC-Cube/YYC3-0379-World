#!/bin/bash

# WireGuard 密钥生成脚本

KEY_DIR="$(dirname "$0")/keys"
mkdir -p "$KEY_DIR"

# 生成私钥
wg genkey > "$KEY_DIR/private.key"

# 生成公钥
wg pubkey < "$KEY_DIR/private.key" > "$KEY_DIR/public.key"

# 设置权限
chmod 600 "$KEY_DIR/private.key"
chmod 644 "$KEY_DIR/public.key"

echo "密钥已生成："
echo "私钥: $KEY_DIR/private.key"
echo "公钥: $KEY_DIR/public.key"
echo ""
echo "请将公钥发送给服务器管理员，并将私钥配置到 wg0.conf 文件中"