---
file: INTEGRATION_GUIDE.md
description: MCP 集成指南文档
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-03-21
updated: 2026-04-04
status: stable
tags: [guide],[mcp],[integration]
category: guide
language: zh-CN
---

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

---

本指南说明如何使用集成的四种 MCP（联网搜索、开源仓库、网页读取、视觉理解）。

## 📋 已集成的 MCP

### 1. 联网搜索 MCP (Brave Search)

**功能**: 全网搜索，获取最新的网络信息和资源

**环境变量**:
- `BRAVE_API_KEY`: Brave 搜索 API 密钥

**调用示例**:
```
用户: 搜索最新的 AI 技术趋势
MCP: 调用 mcp-brave-search 进行搜索
返回: 返回最新的 AI 技术文章和资源链接
```

**使用场景**:
- 搜索技术文档和教程
- 获取最新的行业资讯
- 查找代码解决方案
- 搜索 API 文档

---

### 2. 开源仓库 MCP (GitHub)

**功能**: GitHub 代码仓库检索文档、代码与注释

**环境变量**:
- `GITHUB_PERSONAL_ACCESS_TOKEN`: GitHub 个人访问令牌

**调用示例**:
```
用户: 查看 yyc3-cn-assistant 仓库的代码结构
MCP: 调用 mcp-github-yyc3 访问仓库
返回: 返回仓库目录结构、文件列表和代码内容
```

**使用场景**:
- 阅读开源项目代码
- 查找特定文件的内容
- 获取仓库的文档和注释
- 分析项目结构

---

### 3. 文件系统 MCP (Filesystem)

**功能**: 访问本地文件系统，读取文件和目录

**环境变量**: 无

**调用示例**:
```
用户: 读取 /Users/yanyu/project/config.json 文件
MCP: 调用 mcp-filesystem 访问文件
返回: 返回文件内容和元数据
```

**使用场景**:
- 读取本地配置文件
- 访问项目代码
- 查看日志文件
- 分析文档内容

---

### 4. 网页读取 MCP (Web Fetch)

**功能**: 网页内容抓取，获取网页的完整内容

**环境变量**: 无（基于 HTTP 协议）

**调用示例**:
```
用户: 获取 https://docs.bigmodel.cn 的内容
MCP: 调用网页读取 MCP 抓取网页
返回: 返回网页的文本内容和结构化数据
```

**使用场景**:
- 获取在线文档
- 抓取网页内容
- 分析网页结构
- 提取网页数据

---

### 5. 视觉理解 MCP (Vision)

**功能**: 图像和视频理解，GLM-4.6V 视觉能力

**环境变量**:
- `Z_AI_API_KEY`: 智谱 API KEY
- `Z_AI_MODE`: 服务平台选择 (ZHIPU 或 ZAI)

**调用示例**:
```
用户: 分析这个截图
MCP: 调用视觉理解 MCP 处理图片
返回: 返回图片描述、OCR 文字、技术分析等
```

**使用场景**:
- UI 截图转代码
- 错误截图诊断
- 技术图表理解
- 数据可视化分析
- 图像和视频内容理解

---

## 🚀 集成使用示例

### 示例 1: 研究新技术

```
用户: 我需要了解最新的 AI 技术趋势，请帮我搜索相关资料

MCP 调用流程:
1. mcp-brave-search 搜索 "AI 技术趋势 2024"
2. 返回搜索结果和链接
3. 网页读取 MCP 获取相关文章的详细内容
4. 综合分析并总结

返回: 提供最新的 AI 技术趋势报告
```

### 示例 2: 代码分析

```
用户: 帮我分析这个 GitHub 仓库的代码质量

MCP 调用流程:
1. mcp-github-yyc3 获取仓库结构
2. mcp-github-yyc3 读取主要代码文件
3. mcp-filesystem 读取本地配置文件
4. 综合分析代码质量

返回: 提供代码质量分析报告
```

### 示例 3: UI 开发

```
用户: 我有一个 UI 设计图，需要转换成代码

MCP 调用流程:
1. 视觉理解 MCP 分析 UI 截图
2. mcp-filesystem 读取项目模板
3. 生成对应的代码

返回: 提供从 UI 截图生成的代码
```

### 示例 4: 问题诊断

```
用户: 我的程序报错了，这是错误截图

MCP 调用流程:
1. 视觉理解 MCP 读取错误截图
2. OCR 提取错误信息
3. mcp-brave-search 搜索错误解决方案
4. mcp-github-yyc3 查看相关代码

返回: 提供错误诊断和修复建议
```

---

## 🎯 最佳实践

### 1. MCP 自动调用

MCP 服务器会根据您的对话内容自动选择最合适的工具：

- **搜索相关**: 自动使用 Brave 搜索 MCP
- **GitHub 相关**: 自动使用 GitHub MCP
- **文件相关**: 自动使用文件系统 MCP
- **图片相关**: 自动使用视觉理解 MCP

### 2. 上下文管理

- 提供清晰的对话上下文
- 明确指定需要使用的 MCP
- 避免模糊的指令

### 3. 错误处理

- 如果 MCP 调用失败，提供错误信息
- 尝试使用备用 MCP
- 检查环境变量配置

### 4. 性能优化

- 避免重复调用相同的 MCP
- 合理使用缓存
- 批量处理请求

---

## 🔧 配置管理

### 查看已安装的 MCP

```bash
claude mcp list
```

### 测试 MCP 连接

```bash
# 测试 Brave 搜索
echo "测试 Brave 搜索..." | npx -y @modelcontextprotocol/server-brave-search

# 测试 GitHub MCP
echo "测试 GitHub MCP..." | npx -y @modelcontextprotocol/server-github

# 测试文件系统 MCP
echo "测试文件系统 MCP..." | npx -y @modelcontextprotocol/server-filesystem
```

### 卸载 MCP

```bash
claude mcp remove <server-name>
```

---

## 📊 MCP 统计

| MCP 类型 | 服务器名称 | 状态 | 功能 |
|----------|----------|------|------|
| 联网搜索 | mcp-brave-search | ✅ 已部署 | 全网搜索 |
| 开源仓库 | mcp-github-yyc3 | ✅ 已部署 | GitHub 访问 |
| 文件系统 | mcp-filesystem | ✅ 已部署 | 本地文件访问 |
| 网页读取 | (远程服务) | ✅ 已集成 | 网页内容抓取 |
| 视觉理解 | (远程服务) | ✅ 已集成 | 图像视频理解 |

---

## 🚨 故障排除

### 问题 1: MCP 连接失败

**解决方案**:
1. 检查网络连接
2. 验证 API 密钥是否正确
3. 检查 Node.js 版本（需要 18+）
4. 查看日志文件

### 问题 2: MCP 调用超时

**解决方案**:
1. 增加超时时间
2. 检查防火墙设置
3. 尝试使用备用 MCP

### 问题 3: 权限错误

**解决方案**:
1. 检查文件系统权限
2. 验证 API 令牌权限
3. 确认 Docker 守护进程权限

---

## 📚 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [Claude Code MCP 配置指南](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [YYC³ 项目文档](../README.md)
- [集成配置文件](./integrated-mcp-config.json)
- [部署脚本](./deploy-integrated-mcp.sh)

---

**@file**: INTEGRATION_GUIDE.md
**@description**: YYC³ MCP 集成调用指南
**@author**: YanYuCloudCube Team <admin@0379.email>
**@version**: v1.0.0
**@created**: 2026-03-21
**@status**: stable
**@license**: MIT
**@copyright**: Copyright (c) 2026 YanYuCloudCube Team
