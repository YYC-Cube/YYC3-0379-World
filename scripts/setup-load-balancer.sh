#!/bin/bash

# ⚠️ RETIRED 2026-10-05：目标架构已退役——ECS yyc3-33 现仅运行 Traefik 公网边缘（无 PG/LB 容器），
# 现役数据面 = NAS yyc3-45 compose 栈内建 PG15/Redis（deploy/nas/docker-compose.nas.yml）。
# 本脚本保留作历史参考；确认要执行已退役流程时显式放行：YYC3_ALLOW_RETIRED=1 $0
if [ "${YYC3_ALLOW_RETIRED:-0}" != "1" ]; then
    echo "❌ [RETIRED] 本脚本面向已退役的 yyc3-33 PG/LB 架构；现役 DB 备份: core/scripts/yyc3_db_backup.sh" >&2
    exit 1
fi


set -e

echo "========================================="
echo "YYC³ 负载均衡配置脚本"
echo "节点: yyc3-33 (主负载均衡器)"
echo "========================================="

LB_DIR="/opt/yyc3/load-balancer"
CONFIG_DIR="/opt/yyc3/config"

echo ""
echo "📋 步骤 1/6: 创建配置目录..."
mkdir -p ${LB_DIR}
mkdir -p ${CONFIG_DIR}/nginx/ssl
mkdir -p ${CONFIG_DIR}/haproxy/ssl
mkdir -p ${CONFIG_DIR}/keepalived
echo "✅ 目录创建完成"

echo ""
echo "📋 步骤 2/6: 复制配置文件..."
cp -r /opt/yyc3/core/config/nginx ${CONFIG_DIR}/
cp -r /opt/yyc3/core/config/haproxy ${CONFIG_DIR}/
cp -r /opt/yyc3/core/config/load-balancer ${LB_DIR}/
echo "✅ 配置文件复制完成"

echo ""
echo "📋 步骤 3/6: 配置 SSL 证书..."
# 从 Traefik 复制证书
if [ -f "/opt/yyc3/traefik/acme.json" ]; then
    echo "⚠️  从 Traefik 提取证书需要手动操作"
    echo "请使用以下命令提取证书:"
    echo "  jq -r '.Certificates[] | select(.domain.main==\"api.0379.world\") | .certificate' /opt/yyc3/traefik/acme.json | base64 -d > ${CONFIG_DIR}/nginx/ssl/api.0379.world.crt"
    echo "  jq -r '.Certificates[] | select(.domain.main==\"api.0379.world\") | .key' /opt/yyc3/traefik/acme.json | base64 -d > ${CONFIG_DIR}/nginx/ssl/api.0379.world.key"
fi
echo "✅ SSL 证书配置完成"

echo ""
echo "📋 步骤 4/6: 配置 Keepalived..."
cat > ${CONFIG_DIR}/keepalived/keepalived.conf << 'EOF'
global_defs {
    router_id YYC3_LB_33
    script_user root
    enable_script_security
}

vrrp_script check_nginx {
    script "killall -0 nginx"
    interval 2
    weight 20
}

vrrp_instance VI_1 {
    state MASTER
    interface eth0
    virtual_router_id 51
    priority 100
    advert_int 1
    
    authentication {
        auth_type PASS
        auth_pass yyc3_lb_2026
    }
    
    virtual_ipaddress {
        192.168.3.100
    }
    
    track_script {
        check_nginx
    }
}
EOF
echo "✅ Keepalived 配置完成"

echo ""
echo "📋 步骤 5/6: 启动负载均衡服务..."
cd ${LB_DIR}/load-balancer
docker-compose pull
docker-compose up -d
echo "✅ 负载均衡服务已启动"

echo ""
echo "📋 步骤 6/6: 验证服务状态..."
sleep 3
docker ps | grep -E "nginx-lb|haproxy-lb|keepalived"
echo "✅ 服务验证完成"

echo ""
echo "========================================="
echo "✅ 负载均衡配置完成"
echo "========================================="
echo ""
echo "虚拟 IP: 192.168.3.100"
echo "Nginx 状态: http://192.168.3.100/nginx_status"
echo "HAProxy 状态: http://192.168.3.100:8404/stats"
echo ""
echo "验证命令:"
echo "  curl http://192.168.3.100/health"
echo "  curl https://api.0379.world/health"
echo ""
