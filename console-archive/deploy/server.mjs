#!/usr/bin/env node
/**
 * YYC³ CloudPivot Intelli-Matrix — 本地部署服务器
 * ================================================
 *
 * 功能:
 *   1. 静态文件托管 (Vite build 产物 dist/)
 *   2. Ollama API 反向代理 (/api/v1/llm/ollama/* → localhost:11434/api/*)
 *   3. SPA 路由回退 (所有非 API/非文件路由 → index.html)
 *   4. CORS 收敛 (默认仅同源; ALLOW_ORIGIN / ALLOW_ORIGIN_CIDR 按需放行)
 *   5. Gzip 压缩 (可选)
 *
 * 拓扑: 本文件 = LAN 形态入口（`pnpm serve:local`）；公网形态入口见 ./console-server.mjs
 *       （带 /console/auth 鉴权 + gw/ollama 代理门控）。改动托管行为时须同步评估另一份。
 *
 * 零依赖 — 仅使用 Node.js 内置模块 (http, fs, path, url)
 *
 * 用法:
 *   node deploy/server.mjs                    # 默认 0.0.0.0:3118
 *   PORT=8080 node deploy/server.mjs          # 自定义端口
 *   OLLAMA_HOST=192.168.3.10 node deploy/mjs  # 自定义 Ollama 地址
 *
 * 环境变量:
 *   PORT               — 监听端口 (默认 3118)
 *   HOST               — 监听地址 (默认 0.0.0.0, 局域网可访问)
 *   OLLAMA_HOST        — Ollama 主机 (默认 127.0.0.1)
 *   OLLAMA_PORT        — Ollama 端口 (默认 11434)
 *   DIST_DIR           — 静态文件目录 (默认 ../dist, 相对于此脚本)
 *   ALLOW_ORIGIN       — 逗号分隔的跨域来源白名单 (如 https://a.example.com,http://192.168.3.5:5173);
 *                        特殊值 "*" 放行任意来源; 未设置 = 仅同源 (不回 CORS 头, 默认安全)
 *   ALLOW_ORIGIN_CIDR  — 逗号分隔的 IPv4 网段 (CIDR, 如 192.168.3.0/24,10.0.0.0/8);
 *                        请求 Origin 的 IP 主机命中网段即放行 (内网网段场景)
 */

import fs, { createReadStream } from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ============================================================
// 配置
// ============================================================

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = parseInt(process.env.PORT || "3118", 10);
const HOST = process.env.HOST || "0.0.0.0";
const OLLAMA_HOST = process.env.OLLAMA_HOST || "127.0.0.1";
const OLLAMA_PORT = parseInt(process.env.OLLAMA_PORT || "11434", 10);
const DIST_DIR = path.resolve(__dirname, process.env.DIST_DIR || "../dist");

/** Ollama 代理前缀 */
const OLLAMA_PROXY_PREFIX = "/api/v1/llm/ollama";

/** MIME 类型映射 */
const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".map": "application/json",
  ".webmanifest": "application/manifest+json",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "text/xml; charset=utf-8",
};

// ============================================================
// CORS 收敛 (默认仅同源; 白名单 + CIDR 网段按需放行)
// ============================================================

/** 明确放行任意来源 (需显式设置 ALLOW_ORIGIN=*, 与旧行为等价) */
const ALLOW_ANY = process.env.ALLOW_ORIGIN === "*";

/** 精确来源白名单 (协议+主机+端口 必须完全一致) */
const ALLOWED_ORIGINS = new Set(
  (process.env.ALLOW_ORIGIN || "")
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s && s !== "*")
);

/** IPv4 → 32 位无符号整数 (非法输入返回 null) */
function ipv4ToInt(ip) {
  const parts = String(ip).split(".");
  if (parts.length !== 4) return null;
  let out = 0;
  for (const part of parts) {
    const n = Number(part);
    if (!Number.isInteger(n) || n < 0 || n > 255 || !/^\d+$/.test(part)) return null;
    out = out * 256 + n;
  }
  return out >>> 0;
}

/** 启动时解析 CIDR 网段配置 (非法条目告警并跳过, 不阻断启动) */
const ALLOWED_CIDRS = (process.env.ALLOW_ORIGIN_CIDR || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean)
  .map((cidr) => {
    const [ip, bitsRaw] = cidr.split("/");
    const base = ipv4ToInt(ip);
    const bits = Number(bitsRaw ?? 32);
    if (base === null || !Number.isInteger(bits) || bits < 0 || bits > 32) {
      console.warn(`  ⚠️ ALLOW_ORIGIN_CIDR 非法条目已忽略: "${cidr}"`);
      return null;
    }
    const mask = bits === 0 ? 0 : (0xffffffff << (32 - bits)) >>> 0;
    return { network: (base & mask) >>> 0, mask };
  })
  .filter(Boolean);

/**
 * 判定请求 Origin 是否被放行。
 * 安全基线: 未配置任何放行项时返回 false (仅同源 — 浏览器同源请求本就不需要 CORS 头)。
 */
function isOriginAllowed(origin) {
  if (ALLOW_ANY) return true;
  if (!origin) return false;
  if (ALLOWED_ORIGINS.has(origin)) return true;
  if (ALLOWED_CIDRS.length === 0) return false;

  // CIDR: Origin 主机须为 IPv4 字面量 (http://192.168.3.5:3118 形态)
  let host;
  try {
    host = new URL(origin).hostname;
  } catch {
    return false;
  }
  // 去掉 IPv6 字面量方括号后仍非 IPv4 则直接拒绝 (网段策略只针对 IPv4)
  const ip = ipv4ToInt(host.replace(/^\[|\]$/g, ""));
  if (ip === null) return false;
  return ALLOWED_CIDRS.some(({ network, mask }) => (ip & mask) >>> 0 === network);
}

/** 命中放行时写入 CORS 头; 未命中时不写 (浏览器将按跨域无授权处理) */
function setCorsHeaders(req, res) {
  const origin = req.headers.origin;
  if (origin && isOriginAllowed(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Accept, Origin, Api-Key");
    res.setHeader("Access-Control-Max-Age", "86400");
  }
}

// ============================================================
// Ollama 反向代理
// ============================================================

/**
 * 将 /api/v1/llm/ollama/xxx 代理到 http://OLLAMA_HOST:OLLAMA_PORT/api/xxx
 */
function proxyToOllama(req, res, subPath) {
  const ollamaPath = `/api/${subPath}`;
  const ollamaUrl = `http://${OLLAMA_HOST}:${OLLAMA_PORT}${ollamaPath}`;

  const proxyOptions = {
    hostname: OLLAMA_HOST,
    port: OLLAMA_PORT,
    path: ollamaPath,
    method: req.method,
    headers: {
      ...req.headers,
      host: `${OLLAMA_HOST}:${OLLAMA_PORT}`,
    },
  };

  // 移除浏览器自动添加的不需要的头
  delete proxyOptions.headers["origin"];
  delete proxyOptions.headers["referer"];

  const proxyReq = http.request(proxyOptions, (proxyRes) => {
    setCorsHeaders(req, res);
    res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on("error", (err) => {
    console.error(`[PROXY ERROR] ${req.method} ${ollamaUrl} → ${err.message}`);
    setCorsHeaders(req, res);
    res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      error: "Ollama proxy error",
      message: err.message,
      target: ollamaUrl,
      suggestion: "请确认 Ollama 已启动: ollama serve",
    }));
  });

  // 转发请求体 (POST/PUT)
  req.pipe(proxyReq, { end: true });
}

// ============================================================
// 静态文件服务
// ============================================================

function serveStatic(req, res) {
  const urlPath = new URL(req.url || "/", `http://${HOST}`).pathname;

  // 安全: 防止路径遍历
  const safePath = path.normalize(urlPath).replace(/^(\.\.(\/|\\|$))+/, "");
  let filePath = path.join(DIST_DIR, safePath);

  // 检查文件是否存在
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";

    // 缓存策略: 带 hash 的资源长缓存, 其他短缓存
    const isHashed = /\.[a-f0-9]{8,}\./i.test(path.basename(filePath));
    const cacheControl = isHashed
      ? "public, max-age=31536000, immutable"
      : "public, max-age=60";

    res.writeHead(200, {
      "Content-Type": contentType,
      "Cache-Control": cacheControl,
    });
    createReadStream(filePath).pipe(res);
    return true;
  }

  return false;
}

// ============================================================
// SPA 回退 (index.html)
// ============================================================

function serveSPAFallback(req, res) {
  const indexPath = path.join(DIST_DIR, "index.html");
  if (fs.existsSync(indexPath)) {
    res.writeHead(200, {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-cache",
    });
    createReadStream(indexPath).pipe(res);
  } else {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("index.html not found. Did you run `pnpm build`?");
  }
}

// ============================================================
// 请求处理
// ============================================================

const server = http.createServer((req, res) => {
  const method = req.method || "GET";
  const urlPath = new URL(req.url || "/", `http://${HOST}`).pathname;

  // ── CORS 预检 ──
  if (method === "OPTIONS") {
    setCorsHeaders(req, res);
    res.writeHead(204);
    res.end();
    return;
  }

  // ── Ollama 代理 ──
  if (urlPath.startsWith(OLLAMA_PROXY_PREFIX)) {
    const subPath = urlPath.slice(OLLAMA_PROXY_PREFIX.length).replace(/^\//, "");
    setCorsHeaders(req, res);
    proxyToOllama(req, res, subPath);
    const ts = new Date().toISOString().slice(11, 19);
    console.log(`[${ts}] PROXY ${method} ${urlPath} → ollama:${OLLAMA_PORT}/api/${subPath}`);
    return;
  }

  // ── 静态文件 ──
  if (serveStatic(req, res)) {
    return;
  }

  // ── SPA 回退 ──
  serveSPAFallback(req, res);
});

// ============================================================
// 启动
// ============================================================

server.listen(PORT, HOST, () => {
  const interfaces = getNetworkInterfaces();

  console.log("");
  console.log("  ╔══════════════════════════════════════════════════════════╗");
  console.log("  ║  YYC³ CloudPivot Intelli-Matrix · Local Deploy Server   ║");
  console.log("  ╚══════════════════════════════════════════════════════════╝");
  console.log("");
  console.log(`  📂 静态文件:   ${DIST_DIR}`);
  console.log(`  🔗 Ollama 代理: ${OLLAMA_PROXY_PREFIX}/* → http://${OLLAMA_HOST}:${OLLAMA_PORT}/api/*`);
  // CORS 模式横幅 (审计可见性: 部署时一眼确认放行策略)
  if (ALLOW_ANY) {
    console.log("  ⚠️ CORS: 放行任意来源 (ALLOW_ORIGIN=*) — 仅限可信内网!");
  } else if (ALLOWED_ORIGINS.size > 0 || ALLOWED_CIDRS.length > 0) {
    const origins = [...ALLOWED_ORIGINS].join(", ");
    const cidrs = (process.env.ALLOW_ORIGIN_CIDR || "").split(",").map((s) => s.trim()).filter(Boolean).join(", ");
    console.log(`  🔒 CORS: 白名单 ${origins ? `[${origins}]` : ""}${origins && cidrs ? " + " : ""}${cidrs ? `网段 [${cidrs}]` : ""}`);
  } else {
    console.log("  🔒 CORS: 仅同源 (未配置 ALLOW_ORIGIN / ALLOW_ORIGIN_CIDR)");
  }
  console.log("");
  console.log("  🌐 访问地址:");
  console.log(`     Local:   http://localhost:${PORT}`);
  for (const addr of interfaces) {
    console.log(`     Network: http://${addr}:${PORT}`);
  }
  console.log("");
  console.log("  📡 Ollama 端点测试:");
  console.log(`     curl http://localhost:${PORT}${OLLAMA_PROXY_PREFIX}/tags`);
  console.log(`     curl -X POST http://localhost:${PORT}${OLLAMA_PROXY_PREFIX}/chat \\`);
  console.log(`       -H 'Content-Type: application/json' \\`);
  console.log(`       -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"hi"}],"stream":false}'`);
  console.log("");
  console.log("  按 Ctrl+C 停止服务器");
  console.log("");
});

// Graceful shutdown
process.on("SIGINT", () => {
  console.log("\n  🛑 服务器已停止\n");
  process.exit(0);
});

process.on("SIGTERM", () => {
  server.close(() => process.exit(0));
});

// ============================================================
// 工具函数
// ============================================================

function getNetworkInterfaces() {
  const addrs = [];
  try {
    const nets = os.networkInterfaces();
    for (const name of Object.keys(nets)) {
      for (const net of nets[name] || []) {
        if (net.family === "IPv4" && !net.internal) {
          addrs.push(net.address);
        }
      }
    }
  } catch {
    addrs.push("192.168.3.x");
  }
  return addrs;
}
