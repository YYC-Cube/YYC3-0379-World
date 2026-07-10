#!/bin/bash

# deploy-high-availability.sh - 高可用部署脚本
# @file: deploy-high-availability.sh
# @description: 自动化部署YYC³高可用架构
# @author: YanYuCloudCube Team <admin@0379.email>
# @version: v1.0.0
# @created: 2026-04-08
# @updated: 2026-04-08
# @status: active
# @tags: deployment,high-availability,automation

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

# 配置
DEPLOY_DIR="/Volumes/Development/项目提示词/0379-world/deploy"
COMPOSE_FILE="docker-compose.ha.yml"
ENV_FILE=".env"

# 检查环境
check_environment() {
    log_step "Checking environment..."

    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found! Please install Docker first."
        exit 1
    fi

    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose not found! Please install Docker Compose first."
        exit 1
    fi

    # 检查环境变量文件
    if [ ! -f "$DEPLOY_DIR/$ENV_FILE" ]; then
        log_warn "Environment file not found, creating from template..."
        create_env_file
    fi

    log_info "Environment check passed!"
}

# 创建环境变量文件
create_env_file() {
    cat > "$DEPLOY_DIR/$ENV_FILE" << EOF
# YYC³ High Availability Environment Variables
# Generated at $(date)

# JWT Configuration
JWT_SECRET_KEY=${JWT_SECRET_KEY:?must_set_JWT_SECRET_KEY}

# API Keys (comma-separated)
API_KEYS=${API_KEYS:?must_set_API_KEYS}

# Grafana Configuration
GRAFANA_PASSWORD=admin123

# Database Configuration
DB_PASSWORD=yyc3_password

# Redis Configuration
REDIS_PASSWORD=yyc3_redis_password
EOF

    log_info "Created environment file: $DEPLOY_DIR/$ENV_FILE"
    log_warn "Please update the environment variables with secure values!"
}

# 拉取镜像
pull_images() {
    log_step "Pulling Docker images..."

    cd "$DEPLOY_DIR"
    docker-compose -f "$COMPOSE_FILE" pull

    log_info "Images pulled successfully!"
}

# 启动服务
start_services() {
    log_step "Starting services..."

    cd "$DEPLOY_DIR"
    docker-compose -f "$COMPOSE_FILE" up -d

    log_info "Services started!"
}

# 健康检查
health_check() {
    log_step "Performing health check..."

    # 等待服务启动
    log_info "Waiting for services to start..."
    sleep 15

    # 检查Gateway Primary
    if curl -f http://localhost:3200/health > /dev/null 2>&1; then
        log_info "✓ Gateway Primary (yyc3-33) is healthy"
    else
        log_error "✗ Gateway Primary health check failed"
    fi

    # 检查Gateway Backup
    if curl -f http://localhost:3202/health > /dev/null 2>&1; then
        log_info "✓ Gateway Backup (yyc3-45) is healthy"
    else
        log_warn "✗ Gateway Backup health check failed (non-critical)"
    fi

    # 检查Ollama
    if curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_info "✓ Ollama is healthy"
    else
        log_warn "✗ Ollama health check failed (non-critical)"
    fi

    # 检查Model Router
    if curl -f http://localhost:3205/health > /dev/null 2>&1; then
        log_info "✓ Model Router is healthy"
    else
        log_warn "✗ Model Router health check failed"
    fi

    # 检查Prometheus
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_info "✓ Prometheus is healthy"
    else
        log_warn "✗ Prometheus health check failed"
    fi

    # 检查Grafana
    if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
        log_info "✓ Grafana is healthy"
    else
        log_warn "✗ Grafana health check failed"
    fi

    log_info "Health check completed!"
}

# 验证部署
verify_deployment() {
    log_step "Verifying deployment..."

    # 测试API
    log_info "Testing API endpoints..."

    # 测试模型列表
    response=$(curl -s http://localhost:3200/v1/models)

    if echo "$response" | grep -q "data"; then
        log_info "✓ API is working correctly"
    else
        log_error "✗ API verification failed"
        return 1
    fi

    # 测试认证
    response=$(curl -s -H "X-API-Key: invalid_key" http://localhost:3200/v1/models)

    if echo "$response" | grep -q "Forbidden"; then
        log_info "✓ Authentication is working correctly"
    else
        log_warn "✗ Authentication verification failed"
    fi

    log_info "Deployment verified successfully!"
}

# 显示服务状态
show_status() {
    log_step "Service Status:"

    cd "$DEPLOY_DIR"
    docker-compose -f "$COMPOSE_FILE" ps

    echo ""
    log_info "Access URLs:"
    echo "  - API Gateway (Primary): http://localhost:3200"
    echo "  - API Gateway (Backup):  http://localhost:3202"
    echo "  - Ollama:                http://localhost:11434"
    echo "  - Model Router:          http://localhost:3205"
    echo "  - Failover Manager:      http://localhost:3206"
    echo "  - Prometheus:            http://localhost:9090"
    echo "  - Grafana:               http://localhost:3000"
}

# 停止服务
stop_services() {
    log_step "Stopping services..."

    cd "$DEPLOY_DIR"
    docker-compose -f "$COMPOSE_FILE" down

    log_info "Services stopped!"
}

# 重启服务
restart_services() {
    log_step "Restarting services..."

    stop_services
    sleep 5
    start_services
    health_check

    log_info "Services restarted!"
}

# 查看日志
view_logs() {
    local service=$1

    cd "$DEPLOY_DIR"
    docker-compose -f "$COMPOSE_FILE" logs -f "$service"
}

# 主流程
main() {
    case "${1:-deploy}" in
        deploy)
            log_info "Starting YYC³ High Availability Deployment..."
            check_environment
            pull_images
            start_services
            health_check
            verify_deployment
            show_status
            log_info "Deployment completed successfully!"
            ;;

        stop)
            stop_services
            ;;

        restart)
            restart_services
            ;;

        status)
            show_status
            ;;

        logs)
            view_logs "${2:-}"
            ;;

        health)
            health_check
            ;;

        verify)
            verify_deployment
            ;;

        *)
            echo "Usage: $0 {deploy|stop|restart|status|logs [service]|health|verify}"
            exit 1
            ;;
    esac
}

main "$@"
