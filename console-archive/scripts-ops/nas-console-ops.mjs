#!/usr/bin/env node
/**
 * nas-console-ops.mjs — NAS 本机 console 运维交互台 (R10 / 2026-10-16)
 * ==========================================================
 * 背景: 2026-10-16 08:08 NAS 重启后 PM2 守护进程消亡, console (0.0.0.0:3210) 拒连 —
 *       「打不开」事件。人工排查链: 拒连(exit 7) → pm2 ls 触发 Spawning daemon →
 *       resurrect 救活 + crontab @reboot 自愈钩子补位。本脚本把该链固化为可交互命令。
 *
 * 用法 (在 NAS 上运行, 零依赖纯 Node):
 *   node scripts/nas-console-ops.mjs              # 交互菜单 (TTY 默认)
 *   node scripts/nas-console-ops.mjs status       # 只读体检: 进程/端口/鉴权/开机钩子
 *   node scripts/nas-console-ops.mjs verify       # 七项验证 (只读; 需凭据文件)
 *   node scripts/nas-console-ops.mjs heal         # 自愈: resurrect → 缺失则全新拉起
 *   node scripts/nas-console-ops.mjs logs [n]     # 最近 n 行日志 (默认 30)
 *   node scripts/nas-console-ops.mjs restart|stop
 *   node scripts/nas-console-ops.mjs boot         # 开机自愈钩子体检
 * 退出码: 0 = 健康/成功 / 1 = 存在 FAIL / 2 = 用法错误
 *
 * 环境变量 (可选覆盖):
 *   CONSOLE_BASE  默认 http://127.0.0.1:3210
 *   CONSOLE_DIR   默认 /Volume2/yyc3-console
 *   PM2_BIN       默认 /mnt/volume2/.nvm/versions/node/v24.18.0/bin/pm2
 *   CONSOLE_CRED  默认 ~/.yyc3-console-cred (登录密码, 600 权限)
 *
 * 安全约束:
 *   - 目标主机固定白名单 {127.0.0.1, ::1, 192.168.3.45}, 非白名单直接拒绝
 *     (运维探针的显式目的地校验, 不接受任意 URL 输入, 无 SSRF 面)
 *   - 凭据只从凭据文件读取, 源码零凭据字面量
 *   - WS 探测用 http upgrade 原生握手断言 101, 不实例化 WebSocket
 */
import { spawnSync } from "node:child_process";
import { createInterface } from "node:readline";
import http from "node:http";
import net from "node:net";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

const BASE = process.env.CONSOLE_BASE || "http://127.0.0.1:3210";
const CONSOLE_DIR = process.env.CONSOLE_DIR || "/Volume2/yyc3-console";
const PM2_BIN = process.env.PM2_BIN || "/mnt/volume2/.nvm/versions/node/v24.18.0/bin/pm2";
const CRED_FILE = process.env.CONSOLE_CRED || path.join(homedir(), ".yyc3-console-cred");
const PROC_NAME = "yyc3-console-nas";
const HOST_ALLOWLIST = new Set(["127.0.0.1", "::1", "192.168.3.45"]);

const target = new URL(BASE);
if (target.protocol !== "http:" || !HOST_ALLOWLIST.has(target.hostname)) {
  console.error(`[ops] 拒绝目标 ${BASE} — 仅允许白名单主机 ${[...HOST_ALLOWLIST].join("/")} (http)`);
  process.exit(2);
}
const HOST = target.hostname;
const PORT = Number(target.port) || 80;

const ok = (s) => `\x1b[32m${s}\x1b[0m`;
const bad = (s) => `\x1b[31m${s}\x1b[0m`;
const dim = (s) => `\x1b[2m${s}\x1b[0m`;

/** spawnSync 包装: 返回 { code, out } */
function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: "utf8", timeout: 30_000, ...opts });
  return { code: r.status ?? 1, out: `${r.stdout || ""}${r.stderr || ""}`.trim() };
}

function hasPm2() {
  return existsSync(PM2_BIN);
}

/** TCP 端口探测 (promise) */
function tcpUp(timeoutMs = 3000) {
  return new Promise((resolve) => {
    const s = net.connect({ host: HOST, port: PORT });
    const done = (v) => { s.destroy(); resolve(v); };
    s.setTimeout(timeoutMs, () => done(false));
    s.once("connect", () => done(true));
    s.once("error", () => done(false));
  });
}

/** HTTP 请求 (promise): 返回 { status, headers, body } */
function request(pathname, { method = "GET", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: HOST, port: PORT, path: pathname, method, headers }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.setTimeout(6000, () => { req.destroy(new Error("timeout")); });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

/** WS 探测: http upgrade 握手断言 101 (不实例化 WebSocket) */
function wsProbe(cookie) {
  return new Promise((resolve) => {
    const req = http.request({
      host: HOST, port: PORT, path: "/console/ws/monitor", method: "GET",
      headers: {
        Connection: "Upgrade", Upgrade: "websocket",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
        ...(cookie ? { Cookie: cookie } : {}),
      },
    });
    req.setTimeout(6000, () => { req.destroy(); resolve(0); });
    req.on("upgrade", (res) => { req.destroy(); resolve(res.statusCode); });
    req.on("response", (res) => { req.destroy(); resolve(res.statusCode); });
    req.on("error", () => resolve(0));
    req.end();
  });
}

/** 读取登录密码 (仅凭据文件) */
function readPassword() {
  if (!existsSync(CRED_FILE)) return null;
  return readFileSync(CRED_FILE, "utf8").trim() || null;
}

/** 解析 console.env → env 对象 (heal 全新拉起用, 免 shell source) */
function parseEnvFile(file) {
  if (!existsSync(file)) return {};
  const env = {};
  for (const line of readFileSync(file, "utf8").split("\n")) {
    const m = /^([A-Z_][A-Z0-9_]*)=(.*)$/.exec(line.trim());
    if (m) env[m[1]] = m[2];
  }
  return env;
}

async function waitTcp(ms = 10_000) {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    if (await tcpUp(1500)) return true;
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

// ---------------------------------------------------------- 七项验证
async function verify() {
  const rows = [];
  const push = (name, pass, detail = "") => rows.push({ name, pass, detail });
  try {
    const st = await request("/console/auth/status");
    let enabled = false;
    try { enabled = JSON.parse(st.body).enabled === true; } catch { /* 非 JSON 按未启用 */ }
    push("1 auth/status enabled", st.status === 200 && enabled, st.body.slice(0, 60));
    const unauth = await request("/console/gw/v1/ping");
    push("2 未登录 gw 401", unauth.status === 401, `code=${unauth.status}`);
    const password = readPassword();
    if (!password) {
      push("3 登录 200", false, `凭据文件缺失: ${CRED_FILE}`);
      push("4 带票 gw 200", false, "跳过");
      push("5 SPA 200", false, "跳过");
      push("6 WS 101", false, "跳过");
      push("7 admin 200", false, "跳过");
    } else {
      const login = await request("/console/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const cookie = (login.headers["set-cookie"] || [])[0]?.split(";")[0] || "";
      push("3 登录 200 + Cookie", login.status === 200 && !!cookie, `code=${login.status}`);
      const gw = await request("/console/gw/v1/ping", { headers: { Cookie: cookie } });
      push("4 带票 gw 200", gw.status === 200, `code=${gw.status}`);
      const spa = await request("/console/", { headers: { Cookie: cookie } });
      push("5 SPA 200", spa.status === 200, `code=${spa.status}`);
      const ws = await wsProbe(cookie);
      push("6 WS Upgrade 101", ws === 101, `code=${ws}`);
      const admin = await request("/console/gw/v1/admin/a2a/agents", { headers: { Cookie: cookie } });
      push("7 admin 端点 200", admin.status === 200, `code=${admin.status}`);
    }
  } catch (e) {
    push("服务可达", false, String(e.message || e));
  }
  for (const r of rows) console.log(`  ${r.pass ? ok("PASS") : bad("FAIL")}  ${r.name}  ${dim(r.detail)}`);
  const fail = rows.filter((r) => !r.pass).length;
  console.log(fail === 0 ? ok(`\n[verify] 7 项全绿 (${BASE})`) : bad(`\n[verify] ${fail} 项失败 (${BASE})`));
  return fail === 0;
}

// ---------------------------------------------------------- 只读体检
async function status() {
  console.log(`[status] 目标 ${BASE}  目录 ${CONSOLE_DIR}`);
  const boot = run("uptime", ["-s"]);
  if (boot.code === 0) console.log(`  开机时间: ${boot.out}`);
  console.log(`  端口 ${PORT}: ${await tcpUp() ? ok("监听中") : bad("无监听")}`);
  if (hasPm2()) {
    const ls = run(PM2_BIN, ["ls"]);
    const row = ls.out.split("\n").find((l) => l.includes(PROC_NAME));
    console.log(`  PM2 进程: ${row ? (/online/.test(row) ? ok("online") : bad(row.trim())) : bad("未注册")}`);
  } else {
    console.log(`  ${dim(`PM2 不可用 (${PM2_BIN}) — 本机非 NAS?`)}`);
  }
  try {
    const st = await request("/console/auth/status");
    console.log(`  服务响应: ${st.status === 200 ? ok(st.body) : bad(`code=${st.status}`)}`);
  } catch (e) {
    console.log(`  服务响应: ${bad(String(e.message || e))}`);
  }
  const cron = run("crontab", ["-l"]);
  const hooked = cron.code === 0 && cron.out.includes("yyc3-console-nas");
  console.log(`  开机自愈钩子 (@reboot): ${hooked ? ok("已装") : bad("缺失 — 重启后须手动 heal")}`);
  return true;
}

// ---------------------------------------------------------- 自愈
async function heal() {
  if (!hasPm2()) { console.error(bad(`[heal] PM2 不可用: ${PM2_BIN} (本命令须在 NAS 上运行)`)); return false; }
  console.log("[heal] 第 1 步: pm2 resurrect (从 dump 恢复)");
  run(PM2_BIN, ["resurrect"]);
  if (await waitTcp(8000)) {
    console.log(ok("[heal] resurrect 生效, 端口已恢复"));
  } else {
    console.log("[heal] resurrect 未拉起 → 全新启动 (解析 console.env 注入环境, 免 shell source)");
    const envFile = path.join(CONSOLE_DIR, "console.env");
    if (!existsSync(envFile)) { console.error(bad(`[heal] 缺 ${envFile}`)); return false; }
    run(PM2_BIN, ["delete", PROC_NAME]);
    const r = run(PM2_BIN, ["start", "console-server.mjs", "--name", PROC_NAME, "--time"], {
      cwd: CONSOLE_DIR,
      env: { ...process.env, ...parseEnvFile(envFile) },
    });
    console.log(dim(`    ${r.out.split("\n").pop() || ""}`));
    run(PM2_BIN, ["save"]);
    if (!(await waitTcp(10_000))) { console.error(bad("[heal] 拉起失败 — 执行 logs 排查")); return false; }
    console.log(ok("[heal] 全新拉起成功"));
  }
  return verify();
}

// ---------------------------------------------------------- 其余子命令
function logs(n = 30) {
  if (!hasPm2()) { console.error(bad(`[logs] PM2 不可用: ${PM2_BIN}`)); return false; }
  const r = run(PM2_BIN, ["logs", PROC_NAME, "--lines", String(n), "--nostream"], { timeout: 15_000 });
  console.log(r.out);
  return r.code === 0;
}

function pm2Action(action) {
  if (!hasPm2()) { console.error(bad(`[${action}] PM2 不可用: ${PM2_BIN}`)); return false; }
  const r = run(PM2_BIN, action === "restart" ? ["restart", PROC_NAME] : ["delete", PROC_NAME]);
  console.log(r.out.split("\n").slice(-3).join("\n"));
  return r.code === 0;
}

function boot() {
  const cron = run("crontab", ["-l"]);
  const line = cron.code === 0 ? cron.out.split("\n").find((l) => l.includes("yyc3-console-nas")) : "";
  console.log(`[boot] @reboot 钩子: ${line ? ok("已装") : bad("缺失")}`);
  if (line) console.log(dim(`  ${line.trim()}`));
  // resurrect 就绪三要素之 dump: 内含本进程定义则重启链路 (cron→pm2 resurrect→dump) 完整可期
  const dumpFile = path.join(homedir(), ".pm2", "dump.pm2");
  if (existsSync(dumpFile)) {
    const hasProc = readFileSync(dumpFile, "utf8").includes(`"name":"${PROC_NAME}"`) || readFileSync(dumpFile, "utf8").includes(`"${PROC_NAME}"`);
    console.log(`  resurrect dump 含 ${PROC_NAME}: ${hasProc ? ok("是 (重启链路完整)") : bad("否 — 先 pm2 save")}`);
    if (!hasProc) return false;
  } else {
    console.log(bad(`  resurrect dump 缺失 (~/.pm2/dump.pm2) — 先 pm2 save`));
    return false;
  }
  const logFile = path.join(homedir(), ".pm2", "boot.log");
  if (existsSync(logFile)) {
    const tail = readFileSync(logFile, "utf8").trim().split("\n").slice(-4).join("\n");
    console.log(dim(`  boot.log 尾部:\n${tail}`));
  } else {
    console.log(dim("  boot.log 尚无内容 (最近一次启动未触发 resurrect 或为直启)"));
  }
  return !!line;
}

// ---------------------------------------------------------- 交互菜单
const MENU = `
  YYC³ NAS Console 运维台  (${BASE})
  1) status  只读体检        2) verify  七项验证
  3) heal    自愈拉起        4) logs    最近日志
  5) restart 重启进程        6) boot    开机钩子体检
  q) 退出`;

async function menu() {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const ask = (q) => new Promise((r) => rl.question(q, r));
  while (true) {
    console.log(MENU);
    const c = (await ask("选择> ")).trim();
    if (c === "q") break;
    else if (c === "1") await status();
    else if (c === "2") await verify();
    else if (c === "3") await heal();
    else if (c === "4") logs();
    else if (c === "5") pm2Action("restart");
    else if (c === "6") boot();
    else console.log(dim("无效选择"));
  }
  rl.close();
}

const [cmd, arg] = process.argv.slice(2);
const dispatch = {
  status: () => status(),
  verify: async () => (process.exitCode = (await verify()) ? 0 : 1),
  heal: async () => (process.exitCode = (await heal()) ? 0 : 1),
  logs: () => (process.exitCode = logs(Number(arg) || 30) ? 0 : 1),
  restart: () => (process.exitCode = pm2Action("restart") ? 0 : 1),
  stop: () => (process.exitCode = pm2Action("stop") ? 0 : 1),
  boot: () => (process.exitCode = boot() ? 0 : 1),
};
if (cmd && !dispatch[cmd]) {
  console.error(`用法: nas-console-ops.mjs [status|verify|heal|logs|restart|stop|boot] — 未知命令 "${cmd}"`);
  process.exit(2);
}
if (cmd) await dispatch[cmd]();
else if (process.stdout.isTTY) await menu();
else { console.error("非交互环境请指定子命令 (status/verify/heal/...)"); process.exit(2); }
