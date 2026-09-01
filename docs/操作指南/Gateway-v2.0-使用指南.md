# YYC³ Gateway v2.0.0 使用指南

**版本**: v2.0.0  
**更新日期**: 2026-04-08  
**状态**: 生产就绪

---

## 🎯 快速开始

### 1. 基本配置

确保 `.env.local` 包含以下配置：

```bash
# 智谱GLM API密钥
ZHIPU_API_KEY=your_zhipu_api_key

# Ollama配置
OLLAMA_HOST=0.0.0.0
OLLAMA_PORT=11434
OLLAMA_MODELS=/mnt/models

# 数据库配置
POSTGRES_PASSWORD=your_password
REDIS_PASSWORD=your_redis_password
```

### 2. 启动服务

```bash
cd /Volumes/Development/项目提示词/0379-world/core/api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 验证服务

```bash
# 健康检查
curl https://api.0379.world/health

# 获取模型列表
curl -H "X-API-Key: yyc3_api_key_dev_2026" \
  https://api.0379.world/v1/models
```

---

## 📖 API文档

### 访问地址

- **Swagger UI**: https://api.0379.world/docs
- **ReDoc**: https://api.0379.world/redoc

### 主要接口

#### 1. 健康检查

```bash
GET /health
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2026-04-08T10:30:00",
  "version": "2.0.0",
  "uptime_seconds": 86400,
  "services": {
    "ollama": {"status": "healthy", "latency_ms": 85},
    "zhipu": {"status": "configured"},
    "redis": {"status": "healthy"},
    "postgresql": {"status": "healthy"}
  },
  "system": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "disk_percent": 35.8
  }
}
```

#### 2. 获取模型列表

```bash
GET /v1/models
Headers: X-API-Key: your_api_key
```

**响应示例**:
```json
[
  {
    "id": "glm-4-flash",
    "display_name": "智谱GLM-4 Flash",
    "backend": "zhipu",
    "enabled": true,
    "max_tokens": 128000,
    "cost_per_1k_tokens": 0.001
  },
  {
    "id": "llama3.2",
    "display_name": "Llama 3.2 (本地)",
    "backend": "ollama",
    "enabled": true,
    "max_tokens": 128000,
    "cost_per_1k_tokens": 0.0
  }
]
```

#### 3. 聊天完成

```bash
POST /v1/chat/completions
Headers: 
  Content-Type: application/json
  X-API-Key: your_api_key

Body:
{
  "model": "llama3.2",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**响应示例**:
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "llama3.2",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "你好！我是你的AI助手..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

---

## 🔌 WebSocket接口

### 1. 流式聊天

**连接地址**:
```
wss://api.0379.world/ws/chat?token=your_api_key
```

**JavaScript示例**:
```javascript
const ws = new WebSocket('wss://api.0379.world/ws/chat?token=your_api_key');

ws.onopen = () => {
  // 发送聊天请求
  ws.send(JSON.stringify({
    model: 'llama3.2',
    messages: [{role: 'user', content: '你好'}],
    stream: true
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.event) {
    case 'start':
      console.log('开始生成:', data.data.model);
      break;
    case 'chunk':
      console.log('流式内容:', data.data.choices[0].delta.content);
      break;
    case 'complete':
      console.log('生成完成');
      break;
    case 'error':
      console.error('错误:', data.data.error);
      break;
  }
};
```

### 2. 实时监控

**连接地址**:
```
wss://api.0379.world/ws/monitor?token=your_api_key
```

**JavaScript示例**:
```javascript
const ws = new WebSocket('wss://api.0379.world/ws/monitor?token=your_api_key');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.event === 'metrics') {
    console.log('监控数据:', data.data);
    // data.data 包含:
    // - timestamp: 时间戳
    // - active_requests: 活跃请求数
    // - total_requests: 总请求数
    // - cache_hit_rate: 缓存命中率
    // - models: 各模型状态
  }
};
```

---

## 🤖 支持的模型

### 智谱GLM（云端API）

| 模型ID | 显示名称 | 特点 | 成本 |
|--------|---------|------|------|
| `glm-4-flash` | 智谱GLM-4 Flash | 快速响应，适合简单任务 | $0.001/1K tokens |
| `glm-4-plus` | 智谱GLM-4 Plus | 高级能力，适合复杂任务 | $0.05/1K tokens |

**使用示例**:
```bash
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: yyc3_api_key_dev_2026" \
  -d '{
    "model": "glm-4-flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### Ollama（本地部署）

| 模型ID | 显示名称 | 特点 | 成本 |
|--------|---------|------|------|
| `llama3.2` | Llama 3.2 | Meta最新模型，通用能力强 | 免费 |
| `codegeex4` | CodeGeeX4 | 智谱代码模型，适合编程任务 | 免费 |
| `qwen2.5` | 通义千问 2.5 | 阿里最新模型，中文能力强 | 免费 |

**使用示例**:
```bash
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: yyc3_api_key_dev_2026" \
  -d '{
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

---

## 🔐 认证方式

### 方式1: API Key

在请求头添加 `X-API-Key`:

```bash
curl -H "X-API-Key: yyc3_api_key_dev_2026" \
  https://api.0379.world/v1/models
```

### 方式2: JWT Token

在请求头添加 `Authorization: Bearer <token>`:

```bash
# 获取JWT Token
curl -X POST https://api.0379.world/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "api_key": "yyc3_api_key_dev_2026"}'

# 使用JWT Token
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  https://api.0379.world/v1/models
```

---

## 🧪 测试脚本

### 1. HTTP接口测试

```bash
cd /Volumes/Development/项目提示词/0379-world/scripts
chmod +x test-gateway-v2.sh
./test-gateway-v2.sh
```

### 2. WebSocket测试

```bash
cd /Volumes/Development/项目提示词/0379-world/scripts
pip install websockets
python3 test-websocket.py
```

---

## 📊 监控指标

### Prometheus指标

访问 `/metrics` 端点获取Prometheus格式的指标：

```bash
curl https://api.0379.world/metrics
```

**主要指标**:
- `http_requests_total` - 总请求数
- `http_request_duration_seconds` - 请求延迟
- `active_requests` - 活跃请求数
- `cache_hits_total` - 缓存命中数
- `cache_misses_total` - 缓存未命中数

### Grafana仪表板

访问 Grafana 查看可视化监控：
- URL: http://yyc3-33:3000
- 用户名: admin
- 密码: 见 `.env.local`

---

## 🚀 性能优化建议

### 1. 启用缓存

Gateway默认启用Redis缓存，相同请求会直接返回缓存结果：

```python
# 缓存配置
CACHE_TTL = 3600  # 缓存时间1小时
CACHE_ENABLED = True
```

### 2. 连接池

使用连接池提高性能：

```python
# 在前端代码中
import httpx

# 创建连接池客户端
async with httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100),
    timeout=httpx.Timeout(30.0)
) as client:
    response = await client.post(...)
```

### 3. 批量请求

对于多个独立请求，使用批量处理：

```python
import asyncio

async def batch_requests():
    tasks = [
        call_api("model1", "prompt1"),
        call_api("model2", "prompt2"),
        call_api("model3", "prompt3"),
    ]
    results = await asyncio.gather(*tasks)
    return results
```

---

## 🐛 故障排查

### 问题1: 连接超时

**症状**: 请求超时或连接失败

**解决方案**:
```bash
# 检查服务状态
curl https://api.0379.world/health

# 检查Ollama服务
curl http://localhost:11434/api/tags

# 检查网络连接
ping api.0379.world
```

### 问题2: 认证失败

**症状**: 返回401或403错误

**解决方案**:
```bash
# 检查API Key是否正确
echo $API_KEY

# 测试认证
curl -H "X-API-Key: yyc3_api_key_dev_2026" \
  https://api.0379.world/v1/models
```

### 问题3: 模型不可用

**症状**: 返回"Model not found"错误

**解决方案**:
```bash
# 检查可用模型
curl -H "X-API-Key: yyc3_api_key_dev_2026" \
  https://api.0379.world/v1/models

# 检查Ollama模型列表
curl http://localhost:11434/api/tags
```

---

## 📝 更新日志

### v2.0.0 (2026-04-08)

**新增功能**:
- ✅ WebSocket流式聊天支持
- ✅ WebSocket实时监控支持
- ✅ Ollama流式输出
- ✅ 智谱GLM流式输出
- ✅ 增强健康检查

**优化改进**:
- ✅ 简化Provider配置（只保留智谱GLM和Ollama）
- ✅ 优化API文档
- ✅ 提高代码可维护性

**移除功能**:
- ❌ OpenAI Provider支持
- ❌ 复杂的数据库查询逻辑

---

## 📞 支持

如有问题，请联系：
- **Email**: admin@0379.email
- **GitHub**: https://github.com/YYC-Cube/YYC3-0379-World
- **文档**: https://api.0379.world/docs

---

**最后更新**: 2026-04-08  
**维护者**: YanYuCloudCube Team
