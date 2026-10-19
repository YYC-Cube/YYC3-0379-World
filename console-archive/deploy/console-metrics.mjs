// @ts-check
/// <reference types="node" />
/**
 * console-metrics.mjs
 * ====================
 * Console 服务端指标聚合与设置持久化 — 纯逻辑模块（零副作用，可单测）。
 *
 * 架构先例: console-auth.mjs（逻辑与 server 接线分离，测试 import 不启监听）。
 * 消费方: console-server.mjs
 *   - GET  /console/metrics   → collectNodeMetrics() 聚合 OLLAMA_NODES 各节点 Ollama /api/ps
 *   - GET  /console/settings  → loadConsoleSettings() 服务端持久化设置读取
 *   - PUT  /console/settings  → filterSettingsPayload() 白名单校验后落盘
 *
 * 真实数据接入 P0 + P4 后端下发共批 (2026-10-05)。
 */

import { promises as fs } from "node:fs";

// ── 服务端设置: 白名单键（P4 下发面 — 仅收敛「服务端行为」相关项，前端展示类设置不下发）──
export const CONSOLE_SETTINGS_KEYS = [
  "corsOrigins",        // 允许来源清单（逗号分隔 CIDR/域名）
  "sessionTimeoutMin",  // 会话超时（分钟）
  "ipWhitelist",        // IP 白名单（换行分隔 CIDR）
  "alertEmailAddr",     // 告警通知邮箱
  "webhookUrl",         // 告警 Webhook
  "ollamaNodes",        // Ollama 节点表 { id: origin }（双端联通 R2: B端设备管理可编辑增减）
];

/** 白名单键类型契约（校验+收敛，未知键丢弃，类型不符置默认并标记） */
const KEY_TYPES = {
  corsOrigins: "string",
  sessionTimeoutMin: "number",
  ipWhitelist: "string",
  alertEmailAddr: "string",
  webhookUrl: "string",
  ollamaNodes: "nodes",
};

/** 校验单个节点表项: id 非空短字符串, origin 为 http/https URL（scheme 白名单, 无 SSRF 面——目标仍是内网白名单语义由运维把关） */
function validNodeEntry(id, origin) {
  if (typeof id !== "string" || !id || id.length > 64 || !/^[\w.-]+$/.test(id)) return false;
  if (typeof origin !== "string" || origin.length > 512) return false;
  try {
    const u = new URL(origin);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * 过滤并校验设置载荷 — 仅白名单键通过，其余丢弃。
 * @param {unknown} obj 任意输入（请求体 JSON）
 * @returns {{ ok: boolean, settings: Record<string, string|number|Record<string,string>>, rejected: string[] }}
 */
export function filterSettingsPayload(obj) {
  const rejected = [];
  const settings = {};
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return { ok: false, settings, rejected: ["payload"] };
  }
  for (const [key, want] of Object.entries(KEY_TYPES)) {
    if (!(key in obj)) continue;
    const raw = obj[key];
    if (want === "number") {
      const n = typeof raw === "number" ? raw : Number.parseInt(String(raw), 10);
      if (Number.isFinite(n) && n >= 1 && n <= 1440) settings[key] = Math.round(n);
      else rejected.push(key);
    } else if (want === "nodes") {
      // 节点表: 非数组对象, 全量校验每项; 任一非法 → 整键拒绝（desired-state 语义, 不做部分合并）
      if (raw !== null && typeof raw === "object" && !Array.isArray(raw)
        && Object.keys(raw).length <= 32
        && Object.entries(raw).every(([id, origin]) => validNodeEntry(id, origin))) {
        settings[key] = raw;
      } else {
        rejected.push(key);
      }
    } else {
      if (typeof raw === "string" && raw.length <= 2048) settings[key] = raw;
      else rejected.push(key);
    }
  }
  return { ok: true, settings, rejected };
}

/**
 * 生效 Ollama 节点表（双端联通 R2）: 设置含 ollamaNodes 时完全接管（desired-state）,
 * 否则回退内置白名单常量。
 * @param {Record<string, string>} baseMap 内置节点表
 * @param {Record<string, string|number|Record<string,string>>} settings 已过滤设置
 * @returns {Record<string, string>}
 */
export function effectiveOllamaNodes(baseMap, settings) {
  const custom = settings && typeof settings === "object" ? settings.ollamaNodes : null;
  if (custom && typeof custom === "object" && !Array.isArray(custom) && Object.keys(custom).length > 0) {
    /** @type {Record<string, string>} */
    const map = {};
    for (const [id, origin] of Object.entries(custom)) {
      if (typeof origin === "string") map[id] = origin;
    }
    return map;
  }
  return { ...baseMap };
}

/** 服务端设置落盘路径（deploy/ 运行时旁，不入 git） */
export function consoleSettingsFile(dirname) {
  return `${dirname}/console-settings.json`;
}

/**
 * 读取服务端设置（文件缺失/损坏 → 空对象）
 * @param {string} file
 * @returns {Promise<Record<string, string|number>>}
 */
export async function loadConsoleSettings(file) {
  try {
    const raw = await fs.readFile(file, "utf8");
    const parsed = JSON.parse(raw);
    const { settings } = filterSettingsPayload(parsed);
    return settings;
  } catch {
    return {};
  }
}

/**
 * 写入服务端设置（原子写 tmp→rename）
 * @param {string} file
 * @param {Record<string, string|number>} settings 已过滤的设置
 */
export async function saveConsoleSettings(file, settings) {
  const tmp = `${file}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(settings, null, 2), "utf8");
  await fs.rename(tmp, file);
}

/**
 * 聚合各节点 Ollama 运行指标 — 真实数据接入 P0 生产者。
 * 每节点 GET /api/ps（运行中模型=真实负载），计时得延迟；不可达节点 status=inactive。
 *
 * @param {Record<string, string>} nodesMap 节点白名单 { id: origin }
 * @param {typeof fetch} [fetchImpl] 可注入 fetch（测试）
 * @param {number} [timeoutMs=2500] 单节点超时
 * @returns {Promise<{
 *   ts: number,
 *   activeCount: string,
 *   nodes: Array<{ id: string, status: "active"|"inactive", latencyMs: number, models: string[] }>,
 * }>}
 */
export async function collectNodeMetrics(nodesMap, fetchImpl = fetch, timeoutMs = 2500) {
  const entries = Object.entries(nodesMap || {});
  const results = await Promise.allSettled(
    entries.map(async ([id, origin]) => {
      const started = Date.now();
      const r = await fetchImpl(`${origin}/api/ps`, { signal: AbortSignal.timeout(timeoutMs) });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const latencyMs = Date.now() - started;
      /** @type {{ models?: Array<{ name?: string }> }} */
      const body = await r.json();
      const models = (body.models || []).map((m) => String(m.name || "")).filter(Boolean);
      return { id, status: "active", latencyMs, models };
    })
  );
  const nodes = entries.map(([id], i) => {
    const r = results[i];
    return r.status === "fulfilled"
      ? r.value
      : { id, status: "inactive", latencyMs: -1, models: [] };
  });
  const active = nodes.filter((n) => n.status === "active").length;
  return {
    ts: Date.now(),
    activeCount: `${active}/${nodes.length}`,
    nodes,
  };
}

/**
 * 网关快照聚合（双端联通 P0-3 / 硬约束①）— 并发拉取网关三端点:
 *   GET /health（免认证: services 探测 + system 磁盘/内存 + 网关指标）
 *   GET /v1/router/stats（X-API-Key: 上游池快照 + 熔断态）
 *   GET /v1/models/stats（X-API-Key: 模型用量/tokens, 供前端差分）
 * 各部分独立降级（任一失败不拖垮其余）; GW_ADMIN_KEY 未配置时跳过鉴权端点。
 *
 * 目标 origin 仅来自服务端常量（GW_ORIGIN, http/https）, 密钥仅服务端环境变量 — 无 SSRF/泄露面。
 *
 * @param {string} gwOrigin
 * @param {string} adminKey
 * @param {typeof fetch} [fetchImpl]
 * @param {number} [timeoutMs=4000]
 * @returns {Promise<{ ok: boolean, health?: unknown, router?: unknown, models?: unknown, error?: string }>}
 */
export async function collectGatewaySnapshot(gwOrigin, adminKey, fetchImpl = fetch, timeoutMs = 4000) {
  if (typeof gwOrigin !== "string" || !/^https?:\/\//.test(gwOrigin)) {
    return { ok: false, error: "gwOrigin 非法（须 http/https）" };
  }
  const headers = adminKey ? { "X-API-Key": adminKey } : {};
  const grab = async (path, needKey) => {
    if (needKey && !adminKey) throw new Error("GW_ADMIN_KEY 未配置");
    const r = await fetchImpl(`${gwOrigin}${path}`, {
      headers,
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  };
  const [health, router, models] = await Promise.allSettled([
    grab("/health", false),
    grab("/v1/router/stats", true),
    grab("/v1/models/stats", true),
  ]);
  const val = (p) => (p.status === "fulfilled" ? p.value : null);
  const gotAny = health.status === "fulfilled" || router.status === "fulfilled" || models.status === "fulfilled";
  return {
    ok: gotAny,
    health: val(health),
    router: val(router),
    models: val(models),
    error: gotAny ? undefined : "网关三端点全部不可达",
  };
}
