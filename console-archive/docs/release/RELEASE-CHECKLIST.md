# 发布清单 — RELEASE CHECKLIST（S20）

> 用法：复制本清单到 PR 描述 / Release 正文逐项勾选；C 级决定勾选范围（[] 内标注适用级别）。
> 门槛基线：CI 六阶段（typecheck→lint→unit+coverage→security→e2e→build）本地绿 = CI 绿。

## 前置（全部级别）

- [ ] 所有 CI 阶段绿（ci.yml：typecheck / lint / unit+coverage / security-scan / build）
- [ ] `pnpm run doctor` 12/12
- [ ] 覆盖率四维达标（≥90/85/80/88；实测 95.19/90.92/86.22/93.21）
- [ ] 元门禁通过：`pnpm guardrail-probe` 20/20（无假绿）
- [ ] `gitleaks` 双模式 0（全历史 + 工作树）
- [ ] 变更日志已写（Conventional Commits + CHANGELOG 条目 [C0+]）
- [ ] 标签齐备：1 类型 + 1 模块（+优先级，issue 侧）

## 分级附加（按 CHANGE-MANAGEMENT 矩阵）

- [ ] [C1+] 行数/断言语义不变证明（重构类：`git diff --stat` 与测试 diff 对照）
- [ ] [C2+] 回滚剧本已备（ROLLBACK.md 对应节复制到 Release）+ 部署单端实测
- [ ] [C3+] ADR 已更新（一决策一文件 + INDEX 登记 + 守护门禁落地）
- [ ] [C3+] 新规则/基线已入 guardrail-probe 或棘轮（附 FP 评估）
- [ ] [C4] 迁移说明 + 回滚演练记录（沙箱实测输出）

## 构建（产物级）

- [ ] `pnpm build` 成功（dist/）+ `build:console` 成功（dist-console/）
- [ ] 产物体积在预算内（precache 2.92MB ≤ 6MB；bundle-stats 无异常增长）
- [ ] dist/ 无 source map（`find dist -name "*.map" | wc -l` = 0）
- [ ] dist/ 零密钥（`gitleaks detect --no-git --source dist` no leaks）
- [ ] `pnpm size:check` / `color:check` / `dup:check` / knip 全 0

## 部署（按形态勾选）

- [ ] [LAN] server.mjs :3118 启动 + `/` 200 + `/healthz` 200
- [ ] [公网-NAS] console-server :3210 + 七项 verify（ops.mjs）
- [ ] [公网-ECS] console-server :3100 + 八点验证（L-01 步骤）
- [ ] [Pages] pages.yml 自动部署 token.yyc3.vip（深链回退抽查一条）
- [ ] Ollama 代理可达（LAN `/proxy/ollama/tags` 200）
- [ ] gzip 生效（`curl -H "Accept-Encoding: gzip" -o /dev/null -w %{size_download}` ≈ 908B 壳）

## 验证（功能级）

- [ ] e2e 13/13（auth 3 + models 3 + fullchain 5 + lighthouse 1 + 离线 1）
- [ ] Lighthouse Performance ≥ 90（趋势 JSONL 追加）
- [ ] PWA 安装可用 + 离线多路由 200
- [ ] 双语切换无残留（zh↔en + 正文宽检）
- [ ] 全端图标正常（chain-verify ok:true）
- [ ] 登录→gw 穿门→登出→旧 Cookie 401（jti 链）

## 发布（仪式）

- [ ] tag `v*.*.*`（VERSIONING.md 规则）→ release.yml 流水线
- [ ] GitHub Release 正文 = CHANGELOG 条目 + 已勾选清单
- [ ] 制品归档（release.yml 自动）+ 审计目录引用
- [ ] 通知相关方（issue 关联 / 群公告）

## 发布后（48h）

- [ ] 24h 无 P0/P1（监控 + audit 流巡检）
- [ ] 用户反馈收集（issue/群）
- [ ] 事故复盘归档（如有 → docs/ops/incidents/）
- [ ] [C2+] 双端/ECS 推广完成核销（backlog L-01 型登记销项）
