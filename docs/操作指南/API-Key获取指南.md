---
file: API-Key获取指南.md
description: 消费者视角速查——如何申请/获取/验证/保管/换新 YYC³ 统一 API Key（vk），与《统一API使用与Key签发指南》配套
author: YanYuCloudCube Team <admin@0379.email>
version: v1.0.0
created: 2026-11-16
updated: 2026-11-16
status: active
tags: [api-key],[vk],[consumer],[quickref]
category: 操作指南
language: zh-CN
priority: high
---

# API Key 获取指南（消费者视角速查）

> **你是谁**：想接入 YYC³ 统一 API 的消费方（家臣/脚本/面板/外部服务）。
> **你将得到**：一把 `vk-` 开头的虚拟密钥（含预算/限速/模型白名单/用量计量）。
> 管理员侧签发操作见《[统一API使用与Key签发指南](统一API使用与Key签发指南.md)》§四——本文只讲"怎么拿到、怎么用、丢了怎么办"。

## 一、三步获取（给管理员发申请即可）

**第 1 步 · 提供四要素**（发给管理员/贴给签发命令）：

| 要素 | 说明 | 示例 |
|---|---|---|
| name | Key 用途名（唯一） | `ts-family` / `ops-panel` |
| owner | 归属方 | `TS仓` / `Mac面板` |
| 预算 | 月上限 USD（0=不限） | `5` |
| TPM | 每分钟 token 上限（0=不限） | `60000` |
| 模型白名单 | 只能用哪些模型（空=全部） | `nemotron-3.5-super-vl` |

**第 2 步 · 管理员一键签发**：

```bash
python3 scripts/ops_vkey.py issue --name <用途名> --owner <归属方> \
  --budget <月预算> --tpm <限速> --whitelist "<模型1,模型2>"
```

**第 3 步 · 你收到明文 Key**：`vk-xxxxxxxx…`——**只显示这一次**，立即保存到自己的密钥保管处（`~/.yyc3-keybackup/` 600 权限；绝不进 git/聊天记录/截图）。

## 二、立即验证（30 秒自检）

```bash
curl -s http://100.65.172.88:8000/v1/models -H "X-API-Key: <你的vk>"   # 列出可用模型
curl -s http://100.65.172.88:8000/v1/chat/completions -H "X-API-Key: <你的vk>" \
  -H "Content-Type: application/json" \
  -d '{"model":"nemotron-3.5-super-vl","messages":[{"role":"user","content":"回复ok即可"}],"max_tokens":16}'
```

三入口任选：LAN `192.168.3.45:8000` / TS `100.65.172.88:8000` / 公网 `https://api.0379.world`（同 Key 全通）。

## 三、日常自 service（无需找管理员）

| 操作 | 命令（需管理员 Key 代执行/或看板） |
|---|---|
| 查自己的用量 | `python3 scripts/ops_vkey.py usage <key_id>` |
| 临时停用 | `python3 scripts/ops_vkey.py patch <key_id> --status disabled` |
| 调预算/白名单 | `python3 scripts/ops_vkey.py patch <key_id> --budget 10 --whitelist "…"` |
| 吊销换新 | `revoke <旧key_id>` → 重新 `issue`（Key 轮换标准流程） |

网页看板（管理员）：`GET /v1/admin/dashboard`——用量进度条/按模型分桶。

## 四、错误信号对照（遇到先查这张表）

| 响应 | 含义 | 动作 |
|---|---|---|
| 401 | Key 无效/已吊销/已停用 | 联系管理员 `list` 核状态；轮换场景直接拿新 Key |
| 403 "Admin privileges required" | 业务 Key 打了 `/v1/admin/**` | 管理操作请走管理员通道 |
| 429 | 预算/TPM 触顶 | `usage` 看明细 → 申请调额或等月窗口 |
| 500 且模型不在白名单 | vk 白名单闸 | 申请扩白名单（只加你真用的模型——精一） |

## 五、保管纪律（红线）

1. **明文只出现一次**：签发响应即唯一机会，当场入 `~/.yyc3-keybackup/`（600）；
2. **一把 Key 一个用途**：跨脚本共享 = 计量失真 + 泄露面扩大；
3. **轮换即吊销**：换新 Key 后旧 Key 立即 revoke，不留双活；
4. **泄露即报**：任何疑似泄露 → 管理员立刻 revoke（计量终止，攻击面关闭）。

---

> **YYC³ AI Family** | 言启象限 · 语枢未来
> 配套：《[统一API使用与Key签发指南](统一API使用与Key签发指南.md)》（管理员侧全量）· `scripts/ops_vkey.py --help`
