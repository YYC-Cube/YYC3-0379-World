# DeepSeek API配置指南

## 📋 配置步骤

### 1. 获取API Key

1. 访问：https://platform.deepseek.com/
2. 登录你的账号
3. 进入"API Keys"页面
4. 点击"创建新密钥"
5. 复制生成的API Key

### 2. 配置环境变量

**方式一：更新 .env.local**

```bash
# 编辑配置文件
nano /Volumes/Development/项目提示词/0379-world/.env.local

# 添加以下内容
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

**方式二：更新 .env**

```bash
# 编辑配置文件
nano /Volumes/Development/项目提示词/0379-world/core/api/.env

# 添加以下内容
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

**方式三：直接修改config.py（不推荐）**

```python
# 编辑文件
nano /Volumes/Development/项目提示词/0379-world/core/api/config.py

# 修改这行
deepseek_api_key: str = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
```

### 3. 重启服务

```bash
# 如果使用Docker
cd /Volumes/Development/项目提示词/0379-world/core/database/docker
docker-compose restart gateway

# 如果直接运行
cd /Volumes/Development/项目提示词/0379-world/core/api
# 停止当前进程，然后重新启动
python main.py
```

## 🧪 测试API

### 测试DeepSeek Chat

```bash
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: yyc3_api_key_dev_2026" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 测试DeepSeek Coder

```bash
curl -X POST https://api.0379.world/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: yyc3_api_key_dev_2026" \
  -d '{
    "model": "deepseek-coder",
    "messages": [{"role": "user", "content": "写一个Python函数"}]
  }'
```

## 📊 模型对比

| 模型 | 用途 | 价格 | 最大Token |
|------|------|------|-----------|
| deepseek-chat | 通用对话 | ¥0.001/千tokens | 64000 |
| deepseek-coder | 代码生成 | ¥0.001/千tokens | 16000 |

## 🎯 推荐使用场景

### DeepSeek Chat
- ✅ 日常对话
- ✅ 中文理解
- ✅ 知识问答
- ✅ 文本生成

### DeepSeek Coder
- ✅ 代码生成
- ✅ 代码补全
- ✅ 代码审查
- ✅ Bug修复

## 💰 成本估算

### 月度成本（预估）

| 使用量 | 成本 |
|--------|------|
| 10万tokens | ¥0.1 |
| 100万tokens | ¥1 |
| 1000万tokens | ¥10 |
| 1亿tokens | ¥100 |

**对比智谱GLM**：
- DeepSeek：¥0.001/千tokens
- 智谱GLM-4-Flash：¥0.001/千tokens
- 智谱GLM-4-Plus：¥0.05/千tokens

**结论**：DeepSeek性价比极高！

## 🔧 故障排查

### 问题1：API Key未配置

**错误信息**：
```json
{
  "error": "DeepSeek API Key未配置",
  "details": "请配置DEEPSEEK_API_KEY环境变量"
}
```

**解决方案**：
- 检查.env.local或.env文件
- 确认DEEPSEEK_API_KEY已添加
- 重启服务

### 问题2：API Key无效

**错误信息**：
```json
{
  "error": "DeepSeek API调用失败",
  "status_code": 401
}
```

**解决方案**：
- 检查API Key是否正确
- 确认API Key未过期
- 检查账户余额

### 问题3：余额不足

**错误信息**：
```json
{
  "error": "DeepSeek API调用失败",
  "status_code": 402
}
```

**解决方案**：
- 登录DeepSeek平台充值
- 检查账户余额

## 📞 需要帮助？

如果遇到问题，请告诉我：
1. 具体的错误信息
2. 你的配置方式
3. 测试的命令

我会立即帮你解决！
