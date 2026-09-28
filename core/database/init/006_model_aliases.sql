-- YYC³ 别名热切换（Phase C）：model_aliases 表 Schema
-- 作者: YanYuCloudCube Team | 创建: 2026-09-28
-- 规范: docs/模型接入与注册/03-热切换与版本管理.md §3.1/§3.5
-- 语义: model_alias（公网 API 调用名）→ model_id（含版本）；版本切换 = 改别名指向，
--       不中断公网 API。同一别名可先后映射不同 model_id（切换历史走 model_audit_log
--       与 model_events(alias_switched) 追溯，本表只存当前指向——热路径单查询语义）。
-- 方言: 与 005 一致，结构化列 TEXT 存 JSON（本表无结构化列，纯标量，双端零差异）。

CREATE TABLE IF NOT EXISTS model_aliases (
    alias VARCHAR(200) PRIMARY KEY,
    model_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_aliases_model ON model_aliases(model_id);
