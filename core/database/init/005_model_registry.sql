-- YYC³ 模型注册中心（Model Registry）五表 Schema（Phase A：Registry MVP）
-- 作者: YanYuCloudCube Team | 创建: 2026-09-27
-- 规范: docs/模型接入与注册/02-Registry目标架构.md §3.1
-- 语义: model_registry 为存量表（db.py ORM 建，6 基础列），此处 ADD COLUMN IF NOT EXISTS
--       增量扩展（禁止 DROP 重建——NAS 网关栈已有生产数据）；其余四表全新建。
-- 方言: capabilities/tags/manifest/payload 等结构化列统一 TEXT 存 JSON 串
--       （PG JSONB 在 asyncpg 绑定层有类型坑，见 7bf98c8 TEXT[] 教训；MVP 查询
--       过滤走 enabled/state 标量列，不依赖 GIN）。
-- 兼容: 现有 OPENAI_COMPATIBLE_UPSTREAMS env 通道 100% 保留（REGISTRY_ENABLED 双通道共存，
--       Registry 优先 env 兜底，见 services/model_registry_svc.py）。

-- ── ① 模型主表（增量扩展列）────────────────────────────────────
ALTER TABLE model_registry
    ADD COLUMN IF NOT EXISTS version VARCHAR(50) DEFAULT 'v1.0.0',
    ADD COLUMN IF NOT EXISTS capabilities TEXT NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS tags TEXT NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS max_tokens INTEGER DEFAULT 4096,
    ADD COLUMN IF NOT EXISTS context_window INTEGER DEFAULT 8192,
    ADD COLUMN IF NOT EXISTS temperature_default NUMERIC(3,2) DEFAULT 0.7,
    ADD COLUMN IF NOT EXISTS top_p_default NUMERIC(3,2) DEFAULT 0.9,
    ADD COLUMN IF NOT EXISTS cost_per_1k_tokens NUMERIC(10,6) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS avg_latency_ms NUMERIC(10,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS throughput_tps NUMERIC(10,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_concurrency INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS node_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS node_role VARCHAR(20) DEFAULT 'primary',
    ADD COLUMN IF NOT EXISTS base_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS fallback_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS weights_path VARCHAR(500),
    ADD COLUMN IF NOT EXISTS weights_size_gb NUMERIC(10,2),
    ADD COLUMN IF NOT EXISTS quantization VARCHAR(20),
    ADD COLUMN IF NOT EXISTS model_type VARCHAR(20) DEFAULT 'chat',      -- chat/embedding/rerank/asr/ocr
    ADD COLUMN IF NOT EXISTS state VARCHAR(20) DEFAULT 'offline',       -- offline/loading/ready/draining
    ADD COLUMN IF NOT EXISTS health_status VARCHAR(20) DEFAULT 'unknown', -- healthy/degraded/unreachable/unknown
    ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS breaker_state VARCHAR(20) DEFAULT 'closed',
    ADD COLUMN IF NOT EXISTS manifest_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS owner VARCHAR(200),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_registry_node ON model_registry(node_id);
CREATE INDEX IF NOT EXISTS idx_registry_state ON model_registry(state);

-- ── ② 版本历史表（不可变：UNIQUE(model_id, version)）────────────
CREATE TABLE IF NOT EXISTS model_versions (
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    manifest TEXT NOT NULL DEFAULT '{}',
    manifest_hash VARCHAR(64) NOT NULL DEFAULT '',
    action VARCHAR(20) NOT NULL,             -- register/update/rollback/deprecate
    actor VARCHAR(200) NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_versions_action CHECK (action IN ('register','update','rollback','deprecate'))
);

CREATE INDEX IF NOT EXISTS idx_versions_model ON model_versions(model_id, created_at DESC);

-- ── ③ 心跳表（TTL 检测：三级阶梯 90s/180s/300s，见规范 02 §4.4）──
CREATE TABLE IF NOT EXISTS model_heartbeats (
    model_id VARCHAR(100) PRIMARY KEY,
    last_beat_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consecutive_miss INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);

-- ── ④ 事件表（网关 Watch / SSE 推送源）────────────────────────
CREATE TABLE IF NOT EXISTS model_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(30) NOT NULL,          -- registered/updated/deprecated/deregistered
    model_id VARCHAR(100) NOT NULL,
    version VARCHAR(50),
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_created ON model_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_model ON model_events(model_id, created_at DESC);

-- ── ⑤ 审计日志表（保留 365 天；pg_cron 清理见规范 02 §3.1）──────
CREATE TABLE IF NOT EXISTS model_audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor VARCHAR(200) NOT NULL,
    action VARCHAR(50) NOT NULL,
    model_id VARCHAR(100),
    before_state TEXT,
    after_state TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_actor ON model_audit_log(actor, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_model ON model_audit_log(model_id, created_at DESC);
