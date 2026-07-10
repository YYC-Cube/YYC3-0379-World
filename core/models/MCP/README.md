---
file: README.md
description: MCP 工具配置说明文档
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-03-21
updated: 2026-04-04
status: stable
tags: [mcp],[tools],[configuration]
category: mcp
language: zh-CN
---

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

---

本目录包含从 `yyc3_mcp` 数据库迁移的高价值高可用的 MCP 服务器配置文件，以及集成的四种核心 MCP（联网搜索、开源仓库、网页读取、视觉理解）。

## 🎯 核心集成 MCP

### 1. 联网搜索 MCP (Brave Search)

**功能**: 全网搜索，获取最新的网络信息和资源

**配置文件**: [mcp-brave-search.json](./mcp-brave-search.json)

**环境变量**:

- `BRAVE_API_KEY`: Brave 搜索 API 密钥

**使用场景**:

- 搜索技术文档和教程
- 获取最新的行业资讯
- 查找代码解决方案
- 搜索 API 文档

**详细文档**: [联网搜索-MCP.md](../BigModel/联网搜索-MCP.md)

---

### 2. 开源仓库 MCP (GitHub)

**功能**: GitHub 代码仓库检索文档、代码与注释

**配置文件**: [mcp-github-yyc3.json](./mcp-github-yyc3.json)

**环境变量**:

- `GITHUB_PERSONAL_ACCESS_TOKEN`: GitHub 个人访问令牌

**使用场景**:

- 阅读开源项目代码
- 查找特定文件的内容
- 获取仓库的文档和注释
- 分析项目结构

**详细文档**: [开源仓库-MCP.md](../BigModel/开源仓库-MCP.md)

---

### 3. 文件系统 MCP (Filesystem)

**功能**: 访问本地文件系统，读取文件和目录

**配置文件**: [mcp-filesystem.json](./mcp-filesystem.json)

**环境变量**: 无

**使用场景**:

- 读取本地配置文件
- 访问项目代码
- 查看日志文件
- 分析文档内容

---

### 4. 网页读取 MCP (Web Reader)

**功能**: 网页内容抓取，获取网页的完整内容

**部署方式**: 远程服务（智谱开放平台）

**环境变量**:

- `Authorization`: Bearer Token（智谱 API Key）

**使用场景**:

- 获取在线文档
- 抓取网页内容
- 分析网页结构
- 提取网页数据

**详细文档**: [网页读取-MCP.md](../BigModel/网页读取-MCP.md)

---

### 5. 视觉理解 MCP (Vision)

**功能**: 图像和视频理解，GLM-4.6V 视觉能力

**部署方式**: 本地服务（@z_ai/mcp-server）

**环境变量**:

- `Z_AI_API_KEY`: 智谱 API KEY
- `Z_AI_MODE`: 服务平台选择 (ZHIPU 或 ZAI)

**使用场景**:

- UI 截图转代码
- 错误截图诊断
- 技术图表理解
- 数据可视化分析
- 图像和视频内容理解

**详细文档**: [视觉理解-MCP.md](../BigModel/视觉理解-MCP.md)

---

## 📋 配置文件列表

### Claude 类 MCP (8个)

| 配置文件 | MCP 名称 | 类型 | 功能描述 |
|----------|----------|------|----------|
| [claude-prompts.json](./claude-prompts.json) | claude-prompts | stdio | Claude 提示词管理 |
| [MCP_DOCKER.json](./MCP_DOCKER.json) | MCP_DOCKER | stdio | Docker 网关 MCP |
| [mcp-brave-search.json](./mcp-brave-search.json) | mcp-brave-search | stdio | Brave 搜索 MCP |
| [mcp-docker.json](./mcp-docker.json) | mcp-docker | stdio | Docker 容器管理 MCP |
| [mcp-filesystem.json](./mcp-filesystem.json) | mcp-filesystem | stdio | 文件系统访问 MCP |
| [mcp-github-yyc3.json](./mcp-github-yyc3.json) | mcp-github-yyc3 | stdio | GitHub 仓库访问 MCP |
| [mcp-postgres.json](./mcp-postgres.json) | mcp-postgres | stdio | PostgreSQL 数据库访问 MCP |
| [yyc3-cn-assistant.json](./yyc3-cn-assistant.json) | yyc3-cn-assistant | stdio | YYC³ 中文助手 MCP |

### Development 类 MCP (1个)

| 配置文件 | MCP 名称 | 类型 | 功能描述 |
|----------|----------|------|----------|
| [figma-developer-mcp.json](./figma-developer-mcp.json) | figma-developer-mcp | stdio | Figma 开发者 MCP |

### Other 类 MCP (1个)

| 配置文件 | MCP 名称 | 类型 | 功能描述 |
|----------|----------|------|----------|
| [github.json](./github.json) | github | stdio | GitHub 通用访问 MCP |

## 🚀 使用方法

### 方法一：单独配置

将单个 MCP 配置文件的内容复制到您的 Claude Code 配置文件中：

```bash
# Claude Code 配置文件位置
~/.claude.json
```

示例配置：

```json
{
  "mcpServers": {
    "mcp-brave-search": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### 方法二：一键安装（Claude Code）

使用以下命令快速安装单个 MCP 服务器：

```bash
# 安装 Brave 搜索 MCP
claude mcp add -s user mcp-brave-search --env BRAVE_API_KEY=your_api_key -- npx -y "@modelcontextprotocol/server-brave-search"

# 安装 GitHub MCP
claude mcp add -s user mcp-github --env GITHUB_TOKEN=your_token -- npx -y "@modelcontextprotocol/server-github"

# 安装文件系统 MCP
claude mcp add -s user mcp-filesystem -- npx -y "@modelcontextprotocol/server-filesystem" /Users/yanyu

# 安装网页读取 MCP（远程服务）
claude mcp add -s user -t http web-reader https://open.bigmodel.cn/api/mcp/web_reader/mcp --header "Authorization: Bearer your_api_key"

# 安装视觉理解 MCP（本地服务）
claude mcp add -s user zai-mcp-server --env Z_AI_API_KEY=your_api_key -- npx -y "@z_ai/mcp-server"
```

### 方法三：使用集成配置

使用已集成的配置文件 [integrated-mcp-config.json](./integrated-mcp-config.json)：

```bash
# 查看集成配置
cat integrated-mcp-config.json

# 手动合并到 ~/.claude.json
jq -s '.[0] * .[1]' ~/.claude.json integrated-mcp-config.json > ~/.claude.json.tmp
mv ~/.claude.json.tmp ~/.claude.json
```

### 方法四：批量导入

如果您需要同时配置多个 MCP 服务器，可以手动合并所有配置文件：

```bash
# 合并所有配置
jq -s 'add' *.json > combined-config.json

# 然后将 combined-config.json 的内容复制到 ~/.claude.json
```

## ⚙️ 环境变量说明

### Brave 搜索 MCP

- `BRAVE_API_KEY`: Brave 搜索 API 密钥
- 获取地址：<https://brave.com/search/api>

### GitHub MCP

- `GITHUB_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN`: GitHub 访问令牌
- 获取地址：<https://github.com/settings/tokens>

### PostgreSQL MCP

- 连接字符串：`postgresql://user@host:port/database`
- 示例：`postgresql://yanyu@localhost:5433/yyc3_mcp`

### Docker MCP

- `DOCKER_HOST`: Docker 守护进程地址
- 默认值：`unix:///var/run/docker.sock`

### YYC³ 中文助手 MCP

- `NODE_ENV`: Node.js 运行环境
- `TRAE_CN_MODE`: 运行模式
- 默认值：`development`

## 📝 配置示例

### Claude Code 完整配置示例

```json
{
  "mcpServers": {
    "claude-prompts": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yanyu/yyc3-claude/claude-prompts-mcp/server/dist/index.js"
      ],
      "env": {}
    },
    "mcp-brave-search": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    },
    "mcp-filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/yanyu"
      ],
      "env": {}
    },
    "mcp-github-yyc3": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-github"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    },
    "mcp-postgres": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://yanyu@localhost:5433/yyc3_mcp"
      ],
      "env": {}
    },
    "yyc3-cn-assistant": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yanyu/YYC3-Mac-Max/YYC3-Mcp/API文档/YYC3-CN/代码/yyc3-cn-mcp-server.js"
      ],
      "env": {
        "NODE_ENV": "development",
        "TRAE_CN_MODE": "development"
      }
    },
    "figma-developer-mcp": {
      "type": "stdio",
      "command": "node",
      "args": [
        "figma-developer-mcp",
        "--stdio"
      ],
      "env": {}
    }
  }
}
```

## 🔧 管理命令

### 查看已安装的 MCP 服务器

```bash
claude mcp list
```

### 卸载 MCP 服务器

```bash
claude mcp remove <server-name>
```

### 重新安装 MCP 服务器

```bash
# 先卸载
claude mcp remove <server-name>

# 再安装
claude mcp add -s user <server-name> --env KEY=value -- <command>
```

## 📚 相关文档

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [Claude Code MCP 配置指南](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [YYC³ 项目文档](../README.md)
- [集成调用指南](./INTEGRATION_GUIDE.md)
- [集成配置文件](./integrated-mcp-config.json)
- [部署脚本](./deploy-integrated-mcp.sh)

## 🎯 集成部署状态

### 已完成部署

- ✅ 联网搜索 MCP (mcp-brave-search) - 本地服务
- ✅ 开源仓库 MCP (mcp-github-yyc3) - 本地服务
- ✅ 文件系统 MCP (mcp-filesystem) - 本地服务
- ✅ 网页读取 MCP (web-reader) - 远程服务
- ✅ 视觉理解 MCP (zai-mcp-server) - 本地服务

### 部署脚本

使用统一部署脚本完成所有 MCP 的配置和部署：

```bash
# 执行统一部署脚本
bash /Volumes/Development/项目提示词/0379-world/scripts/deploy-unified.sh
```

该脚本会自动：

1. 注册智谱大模型（GLM-5, GLM-5-Turbo, GLM-4.7, GLM-4.6, GLM-4.5, GLM-4.5-Air）
2. 迁移 MCP 数据从本地数据库到项目数据库
3. 配置和部署核心集成 MCP
4. 验证 MCP 服务状态
5. 生成配置文件和文档

## 🔍 MCP 调用示例

### 研究新技术

```
用户: 我需要了解最新的 AI 技术趋势，请帮我搜索相关资料

MCP 调用流程:
1. mcp-brave-search 搜索 "AI 技术趋势 2024"
2. 返回搜索结果和链接
3. web-reader 获取相关文章的详细内容
4. 综合分析并总结

返回: 提供最新的 AI 技术趋势报告
```

### 代码分析

```
用户: 帮我分析这个 GitHub 仓库的代码质量

MCP 调用流程:
1. mcp-github-yyc3 获取仓库结构
2. mcp-github-yyc3 读取主要代码文件
3. mcp-filesystem 读取本地配置文件
4. 综合分析代码质量

返回: 提供代码质量分析报告
```

### UI 开发

```
用户: 我有一个 UI 设计图，需要转换成代码

MCP 调用流程:
1. zai-mcp-server 分析 UI 截图
2. mcp-filesystem 读取项目模板
3. 生成对应的代码

返回: 提供从 UI 截图生成的代码
```

### 问题诊断

```
用户: 我的程序报错了，这是错误截图

MCP 调用流程:
1. zai-mcp-server 读取错误截图
2. OCR 提取错误信息
3. mcp-brave-search 搜索错误解决方案
4. mcp-github-yyc3 查看相关代码

返回: 提供错误诊断和修复建议
```

## ⚠️ 注意事项

1. **API 密钥安全**：请妥善保管您的 API 密钥，不要将其提交到公共代码仓库
2. **路径配置**：确保所有本地路径（如 `/Users/yanyu`）在您的系统中存在
3. **权限问题**：某些 MCP 可能需要特定的文件系统或网络权限
4. **依赖安装**：确保已安装 Node.js 18+ 和 Docker（如需要）
5. **网络连接**：远程 MCP 服务需要稳定的网络连接

## 📊 MCP 统计

### 核心集成 MCP（5个）

| MCP 名称 | 类型 | 部署方式 | 状态 | 功能 |
|----------|------|----------|------|------|
| mcp-brave-search | stdio | 本地服务 | ✅ 已部署 | 全网搜索 |
| mcp-github-yyc3 | stdio | 本地服务 | ✅ 已部署 | GitHub 访问 |
| mcp-filesystem | stdio | 本地服务 | ✅ 已部署 | 本地文件访问 |
| web-reader | http | 远程服务 | ✅ 已集成 | 网页内容抓取 |
| zai-mcp-server | stdio | 本地服务 | ✅ 已集成 | 图像视频理解 |

### 数据库迁移 MCP（10个）

| 配置文件 | MCP 名称 | 类型 | 功能描述 |
|----------|----------|------|----------|
| [claude-prompts.json](./claude-prompts.json) | claude-prompts | stdio | Claude 提示词管理 |
| [MCP_DOCKER.json](./MCP_DOCKER.json) | MCP_DOCKER | stdio | Docker 网关 MCP |
| [mcp-brave-search.json](./mcp-brave-search.json) | mcp-brave-search | stdio | Brave 搜索 MCP |
| [mcp-docker.json](./mcp-docker.json) | mcp-docker | stdio | Docker 容器管理 MCP |
| [mcp-filesystem.json](./mcp-filesystem.json) | mcp-filesystem | stdio | 文件系统访问 MCP |
| [mcp-github-yyc3.json](./mcp-github-yyc3.json) | mcp-github-yyc3 | stdio | GitHub 仓库访问 MCP |
| [mcp-postgres.json](./mcp-postgres.json) | mcp-postgres | stdio | PostgreSQL 数据库访问 MCP |
| [yyc3-cn-assistant.json](./yyc3-cn-assistant.json) | yyc3-cn-assistant | stdio | YYC³ 中文助手 MCP |
| [figma-developer-mcp.json](./figma-developer-mcp.json) | figma-developer-mcp | stdio | Figma 开发者 MCP |
| [github.json](./github.json) | github | stdio | GitHub 通用访问 MCP |

**总计**:

- 核心集成 MCP：5 个
- 数据库迁移 MCP：10 个
- Claude 类 MCP：8 个
- Development 类 MCP：1 个
- Other 类 MCP：1 个
- 已启用状态：全部 ✅

---

**@file**: README.md
**@description**: YYC³ MCP 配置文件说明文档，包含核心集成 MCP 和数据库迁移 MCP 的完整配置和使用指南
**@author**: YanYuCloudCube Team <admin@0379.email>
**@version**: v2.0.0
**@created**: 2026-03-21
**@updated**: 2026-03-21
**@status**: stable
**@license**: MIT
**@copyright**: Copyright (c) 2026 YanYuCloudCube Team
