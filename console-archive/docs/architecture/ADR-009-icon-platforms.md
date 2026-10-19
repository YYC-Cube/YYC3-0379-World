# ADR-009: 5 平台图标体系对齐（29 PNG 实测口径）

- 状态：Accepted
- 日期：2026-10-16（S13 chain-verify 固化实测口径；图标体系自项目奠基）
- 决策者：首席架构师
- 关联：public/yyc3-icons/ · index.html · manifest.json · scripts/chain-verify.mjs · e2e PWA 资产用例

## 背景 Context

PWA 安装、各 OS 快捷方式、商店提交对图标有**各自独立的尺寸/格式要求**，缺一个就在对应平台降级（模糊图标/无安装横幅）。图标散落生成的通病是「加了新尺寸忘了同步 manifest / index.html / CDN 回退」三处之一。

## 决策 Decision

1. **5 平台目录制**：`public/yyc3-icons/{Web App,Android,iOS,macOS,watchOS}/`，共 **29 PNG**（Web App 5 / Android 6 / iOS 7 / macOS 7 / watchOS 4）——以 chain-verify 实测为准（历史口径"36"未随仓库演进，S13 更正）。
2. **三处对齐纪律**：index.html favicon 链（10 处，**相对路径**——S11 判例：绝对路径在 /console/ 子路径形态全 404）↔ manifest.json icons（13 项）↔ useYYC3Head 运行时注入 + onerror CDN 三档回退（yyc3-icons.ts iconsCDN）。
3. **机器校验**：`scripts/chain-verify.mjs` 对 dist 实证——manifest 6 必需字段完整 + 13 icons 与文件 100% 对齐 + 5 平台目录全覆盖；e2e PWA 资产用例逐图标断言 200。

## 备选方案 Alternatives

| 方案 | 优点 | 缺点 | 为何未选 |
|---|---|---|---|
| 单一 SVG favicon | 极简 | PWA 安装/PWA 资产审计仍要 PNG 位图；旧平台兼容差 | 平台要求硬性 |
| 图标生成器全自动（pwa-asset-generator） | 一次生成全尺寸 | 生成器依赖+品牌微调仍需手工 | 可作为辅助，不替代对齐校验 |
| 目录制 + 三处对齐 + 机器校验（选定） | 链路可审计、断点即 FAIL | 加图标要动三处 | 校验脚本兜底 |

## 后果 Consequences

- 正面：S13 三链路零断点（manifest/链接/文件三方一致）；S11 的相对路径缺陷被 e2e 资产用例当场抓获——校验体系有效。
- 负面：新尺寸需手动三处同步（chain-verify 会抓漏但不会代做）。
- 中性：CDN 回退是叠加保险（本地 404 才走 CDN），主链路仍以本地为准。

## 验证方式 Verification

`node scripts/chain-verify.mjs`（dist 实证）+ e2e PWA 资产链路用例 + S13 三链路 153 用例中的图标域。

## 回滚路径 Rollback

删除 chain-verify 即解除校验；图标文件本身回滚 = git checkout 对应目录。风险极低。
