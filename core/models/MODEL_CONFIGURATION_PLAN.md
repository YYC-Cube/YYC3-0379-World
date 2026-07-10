---
file: MODEL_CONFIGURATION_PLAN.md
description: 模型配置方案文档
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-03-21
updated: 2026-04-04
status: stable
tags: [model],[ai],[configuration]
category: model
language: zh-CN
---

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

---

- **芯片**: Apple M4 Max
- **CPU**: 16核 (12性能核 + 4能效核)
- **内存**: 128 GB 统一内存
- **GPU**: 40核
- **Metal**: Metal 4 支持
- **存储**: 2TB + 2TB SN850X

### 性能特点
- ✅ 统一内存架构：CPU和GPU共享内存，无需数据拷贝
- ✅ 高内存带宽：适合大模型推理
- ✅ 强大的GPU：40核GPU提供出色的推理性能
- ✅ Metal 4支持：优化的机器学习框架

## 🎯 模型搭配策略

### 内存分配原则
- **总内存**: 128 GB
- **系统预留**: 8 GB
- **模型可用**: 120 GB
- **安全阈值**: 80% 使用率 = 96 GB
- **推荐配置**: 70% 使用率 = 84 GB

### 并发策略
- **单模型模式**: 运行1个大模型（70B+）
- **双模型模式**: 运行2个中型模型（30B-70B）
- **多模型模式**: 运行3-4个小模型（7B-14B）

## 📋 推荐模型搭配方案

### 方案一：代码开发专用（推荐）

#### 配置
```bash
# 主力模型：CodeGeeX4 (9B, Q8_0)
codegeex4-all-9b-Q8_0.gguf  # 9.3 GB
用途：代码生成、补全、重构

# 辅助模型：CodeLlama (34B, Q4_K_M)
CodeLlama-34b-Instruct.Q4_K_M.gguf  # ~20 GB
用途：复杂代码推理、架构设计

# 对话模型：Llama 3.2 (3B)
llama3.2:latest  # 2.0 GB
用途：快速对话、简单任务

总计：~31 GB
内存占用：24%
剩余内存：97 GB
```

#### 优势
- ✅ 代码能力强
- ✅ 响应速度快
- ✅ 内存占用低
- ✅ 可同时运行多个模型

#### 适用场景
- 日常代码开发
- 代码审查和重构
- 技术文档编写
- API设计和调试

---

### 方案二：全栈开发（均衡）

#### 配置
```bash
# 主力模型：CodeGeeX4 (9B, Q8_0)
codegeex4-all-9b-Q8_0.gguf  # 9.3 GB
用途：代码生成

# 推理模型：DeepSeek-Coder-V2 (33B, Q4_K_M)
DeepSeek-Coder-V2-Instruct.Q4_K_M.gguf  # ~19 GB
用途：复杂推理、架构设计

# 对话模型：Qwen2.5 (32B, Q4_K_M)
Qwen2.5-32B-Instruct.Q4_K_M.gguf  # ~18 GB
用途：中文对话、文档生成

# 快速模型：Llama 3.2 (3B)
llama3.2:latest  # 2.0 GB
用途：快速响应

总计：~48 GB
内存占用：38%
剩余内存：80 GB
```

#### 优势
- ✅ 中英文支持好
- ✅ 推理能力强
- ✅ 功能全面
- ✅ 适合团队协作

#### 适用场景
- 全栈开发
- 前后端开发
- 文档编写
- 项目管理

---

### 方案三：AI研究专用（高性能）

#### 配置
```bash
# 主力模型：Llama 3.3 (70B, Q4_K_M)
Llama-3.3-70B-Instruct.Q4_K_M.gguf  # ~40 GB
用途：复杂推理、研究

# 代码模型：CodeGeeX4 (9B, Q8_0)
codegeex4-all-9b-Q8_0.gguf  # 9.3 GB
用途：代码生成

# 快速模型：Llama 3.2 (3B)
llama3.2:latest  # 2.0 GB
用途：快速测试

总计：~51 GB
内存占用：40%
剩余内存：77 GB
```

#### 优势
- ✅ 推理能力最强
- ✅ 适合复杂任务
- ✅ 研究级性能
- ✅ 支持长上下文

#### 适用场景
- AI研究
- 复杂推理
- 算法设计
- 技术探索

---

### 方案四：多模型并发（最大利用）

#### 配置
```bash
# 代码模型1：CodeGeeX4 (9B, Q8_0)
codegeex4-all-9b-Q8_0.gguf  # 9.3 GB
用途：代码生成

# 代码模型2：StarCoder2 (15B, Q5_K_M)
StarCoder2-15B.Q5_K_M.gguf  # ~10 GB
用途：代码补全

# 对话模型：Qwen2.5 (14B, Q5_K_M)
Qwen2.5-14B-Instruct.Q5_K_M.gguf  # ~10 GB
用途：中文对话

# 推理模型：Mistral (7B, Q5_K_M)
Mistral-7B-Instruct.Q5_K_M.gguf  # ~5 GB
用途：快速推理

# 快速模型：Llama 3.2 (3B)
llama3.2:latest  # 2.0 GB
用途：轻量任务

总计：~36 GB
内存占用：28%
剩余内存：92 GB
```

#### 优势
- ✅ 模型数量多
- ✅ 功能覆盖全
- ✅ 响应速度快
- ✅ 灵活性高

#### 适用场景
- 多任务处理
- 团队协作
- API服务
- 实验测试

## 🔧 模型配置建议

### 量化等级选择

#### Q8_0 (推荐用于主力模型)
- **优点**: 精度最高，性能最好
- **缺点**: 文件较大
- **适用**: 代码生成、复杂推理

#### Q5_K_M (推荐用于辅助模型)
- **优点**: 平衡精度和大小
- **缺点**: 精度略低于Q8
- **适用**: 对话、文档生成

#### Q4_K_M (推荐用于大模型)
- **优点**: 文件最小，内存占用低
- **缺点**: 精度较低
- **适用**: 70B+模型

### 上下文长度配置

```bash
# 代码模型：长上下文
PARAMETER num_ctx 131072  # 128K context

# 对话模型：中等上下文
PARAMETER num_ctx 32768   # 32K context

# 快速模型：短上下文
PARAMETER num_ctx 8192    # 8K context
```

### 并发配置

```bash
# Ollama 环境变量
OLLAMA_NUM_PARALLEL=4      # 并行请求数
OLLAMA_MAX_LOADED_MODELS=3 # 最大加载模型数
OLLAMA_KEEP_ALIVE=24h      # 模型保持时间
```

## 📦 模型下载建议

### 必备模型（优先下载）
```bash
# 1. CodeGeeX4 (已安装)
ollama create codegeex4 -f Modelfile.codegeex4

# 2. Llama 3.2 (已安装)
ollama pull llama3.2

# 3. Qwen2.5 14B (推荐)
ollama pull qwen2.5:14b

# 4. DeepSeek-Coder-V2 (推荐)
ollama pull deepseek-coder-v2:33b
```

### 可选模型（按需下载）
```bash
# 代码模型
ollama pull starcoder2:15b
ollama pull codellama:34b

# 对话模型
ollama pull mistral:7b
ollama pull gemma2:27b

# 大模型（需要更多内存）
ollama pull llama3.3:70b
ollama pull qwen2.5:72b
```

## 🚀 快速启动脚本

### 创建模型启动脚本

```bash
#!/bin/bash
# ~/ai_models/start-models.sh

echo "启动 YYC³ 模型服务..."

# 启动代码模型（后台运行）
ollama run codegeex4 &

# 等待模型加载
sleep 5

# 启动对话模型
ollama run llama3.2 &

echo "模型服务已启动"
echo "可用模型："
ollama list
```

### 创建模型切换脚本

```bash
#!/bin/bash
# ~/ai_models/switch-models.sh

MODE=$1

case $MODE in
  "code")
    echo "切换到代码开发模式..."
    ollama run codegeex4
    ;;
  "chat")
    echo "切换到对话模式..."
    ollama run qwen2.5:14b
    ;;
  "research")
    echo "切换到研究模式..."
    ollama run llama3.3:70b
    ;;
  *)
    echo "用法: $0 {code|chat|research}"
    ;;
esac
```

## 📊 性能监控

### 内存监控
```bash
# 实时监控内存使用
watch -n 1 'sudo memory_pressure'

# 查看模型内存占用
ollama ps
```

### 性能测试
```bash
# 测试模型响应速度
time ollama run codegeex4 "写一个Python函数"

# 测试并发性能
for i in {1..10}; do
  ollama run codegeex4 "测试 $i" &
done
wait
```

## 🎯 推荐配置（最终建议）

基于您的设备和需求，我推荐：

### **方案一：代码开发专用** ✅

**理由**：
1. ✅ 您已经有 CodeGeeX4 (9B, Q8_0)
2. ✅ 内存占用低（24%），留有充足空间
3. ✅ 响应速度快，适合日常开发
4. ✅ 可以同时运行多个模型

**下一步操作**：
```bash
# 1. 测试 CodeGeeX4
ollama run codegeex4

# 2. 下载辅助模型（可选）
ollama pull codellama:34b

# 3. 下载中文对话模型（可选）
ollama pull qwen2.5:14b
```

## 📞 使用建议

### 日常开发
- 使用 CodeGeeX4 进行代码生成
- 使用 Llama 3.2 进行快速对话
- 保持 2-3 个模型同时运行

### 性能优化
- 定期清理不用的模型：`ollama rm <model>`
- 调整模型参数：`PARAMETER num_ctx`
- 监控内存使用：`ollama ps`

### 故障排查
- 内存不足：减少并发模型数
- 响应慢：降低量化等级或使用小模型
- 模型崩溃：检查系统日志

---

**生成时间**: 2026-04-04
**设备**: Apple M4 Max (128GB)
**推荐方案**: 方案一 - 代码开发专用
**内存占用**: 24% (31GB / 128GB)
