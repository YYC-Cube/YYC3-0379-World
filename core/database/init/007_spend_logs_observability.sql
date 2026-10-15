-- YYC³ 消费流水可观测性扩列（双端联通 P1 / BL-A1）
-- 来源: Token-Console 双端联通方案 §6（后端自家 Backlog BL-01/06/07 收敛）
-- 作者: YanYuCloudCube Team
-- 创建: 2026-10-15
--
-- 目标: /v1/logs 请求级日志查询（B端 /audit 请求级审计与实时操作流数据源）
-- 语义: status 默认 'ok'（历史行回填默认值）; error_code/request_id 由记账管道
--       在上游可提供时写入（vk 记账载荷透传, 缺省 NULL 不伪造）

ALTER TABLE spend_logs ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'ok';
ALTER TABLE spend_logs ADD COLUMN IF NOT EXISTS error_code VARCHAR(100);
ALTER TABLE spend_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_spend_logs_status ON spend_logs(status, created_at);
