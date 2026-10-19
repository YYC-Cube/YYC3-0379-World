// @ts-check
/**
 * console-ws-relay.mjs
 * ====================
 * /console/ws/monitor 中继端点内核（纯逻辑，console-server.mjs 接线）
 *
 * 职责（双端联通 P0-1 / 硬约束①）:
 *   - deriveGatewayWsUrl: 网关 WS 目标 URL 派生（GW_ORIGIN 常量/env → ws(s):// + /ws/monitor?token=）
 *   - isAuthorizedUpgrade: 会话 Cookie 校验决策（复用 console-auth verifyToken 由调用方执行, 此处只收结果）
 *   - RFC 6455 最小服务端帧: acceptKey 握手应答 / 文本帧编码 / masked 客户端帧解码 / ping-pong / close
 *
 * 设计约束:
 *   - deploy/ 零 npm 依赖（供应链红线）——Node 全局 WebSocket 仅为客户端实现,
 *     浏览器侧服务端帧必须手写; 协议面最小化: 文本帧 + ping/pong + close, 不支持分片/压缩。
 *   - 中继目标只来自服务端常量/环境变量（GW_ORIGIN）, 非请求输入, 无 SSRF 面;
 *     scheme 白名单仅 http/https（派生 ws/wss）。
 */

import { createHash } from "node:crypto";

/** 中继端点路径（浏览器侧） */
export const WS_MONITOR_PATH = "/console/ws/monitor";

/** RFC 6455 握手魔串 */
const WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

/**
 * 派生网关 /ws/monitor 目标 URL。
 * @param {string} gwOrigin 服务端常量来源（http/https），如 "http://127.0.0.1:8800"
 * @param {string} adminKey 服务端环境变量注入的管理密钥（仅存在于本进程）
 * @returns {{ ok: true, url: string } | { ok: false, error: string }}
 */
export function deriveGatewayWsUrl(gwOrigin, adminKey) {
  if (!adminKey) return { ok: false, error: "GW_ADMIN_KEY 未配置（服务端环境变量）" };
  let parsed;
  try {
    parsed = new URL(gwOrigin);
  } catch {
    return { ok: false, error: `GW_ORIGIN 非法: ${gwOrigin}` };
  }
  // scheme 白名单: 仅 http/https（派生 ws/wss）, 其余协议拒绝
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { ok: false, error: `GW_ORIGIN scheme 必须为 http/https: ${parsed.protocol}` };
  }
  const wsScheme = parsed.protocol === "https:" ? "wss" : "ws";
  const url = new URL(`${wsScheme}://${parsed.host}/ws/monitor`);
  url.searchParams.set("token", adminKey);
  return { ok: true, url: url.toString() };
}

/**
 * RFC 6455 §1.3: Sec-WebSocket-Accept = base64(sha1(key + GUID))
 * @param {string} key 浏览器 Sec-WebSocket-Key 头
 * @returns {string}
 */
export function computeAcceptKey(key) {
  return createHash("sha1").update(key + WS_GUID).digest("base64");
}

/** 101 握手应答（原始 HTTP 文本）
 * @param {string} key Sec-WebSocket-Key
 */
export function handshakeResponse(key) {
  return (
    "HTTP/1.1 101 Switching Protocols\r\n" +
    "Upgrade: websocket\r\n" +
    "Connection: Upgrade\r\n" +
    `Sec-WebSocket-Accept: ${computeAcceptKey(key)}\r\n` +
    "\r\n"
  );
}

/** 非 WS 升级请求的原始 HTTP 拒绝应答
 * @param {number} code @param {string} reason
 */
export function rawRejectResponse(code, reason) {
  const body = JSON.stringify({ error: reason });
  return `HTTP/1.1 ${code} Rejected\r\nConnection: close\r\nContent-Type: application/json\r\nContent-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`;
}

/** 服务端→客户端文本帧（服务端帧不掩码, RFC 6455 §5.1）
 * @param {string | Buffer} data
 * @returns {Buffer}
 */
export function encodeTextFrame(data) {
  const payload = Buffer.isBuffer(data) ? data : Buffer.from(String(data), "utf8");
  return encodeFrame(0x1, payload);
}

/** ping/pong/close 帧编码 @param {number} opcode @param {Buffer} payload */
function encodeFrame(opcode, payload) {
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.from([0x80 | opcode, len]);
  } else if (len <= 0xffff) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  return Buffer.concat([header, payload]);
}

/** @param {Buffer} [payload] */
export function encodePongFrame(payload) {
  return encodeFrame(0xa, payload ?? Buffer.alloc(0));
}

/** @param {number} [code] */
export function encodeCloseFrame(code = 1000) {
  const payload = Buffer.alloc(2);
  payload.writeUInt16BE(code, 0);
  return encodeFrame(0x8, payload);
}

/**
 * 客户端→服务端帧解析（客户端帧必掩码, RFC 6455 §5.3）。
 * 最小实现: 单帧完整解析; 分片/延续帧按协议忽略 payload 语义（本中继浏览器侧不发业务帧）。
 * @param {Buffer} buf 累积缓冲
 * @returns {{ frames: Array<{ opcode: number; payload: Buffer }>, rest: Buffer } | null} null=缓冲不完整, 等待更多字节
 */
export function parseClientFrames(buf) {
  const frames = [];
  let offset = 0;
  while (offset < buf.length) {
    const b0 = buf[offset];
    const b1 = buf[offset + 1];
    if (b1 === undefined) return null; // 头未齐
    const opcode = b0 & 0x0f;
    const masked = (b1 & 0x80) !== 0;
    let len = b1 & 0x7f;
    let cursor = offset + 2;
    if (len === 126) {
      if (buf.length < cursor + 2) return null;
      len = buf.readUInt16BE(cursor);
      cursor += 2;
    } else if (len === 127) {
      if (buf.length < cursor + 8) return null;
      const big = buf.readBigUInt64BE(cursor);
      if (big > BigInt(0xffff)) return { frames, rest: buf.subarray(offset) }; // 超大帧防御: 停止解析
      len = Number(big);
      cursor += 8;
    }
    let maskKey = null;
    if (masked) {
      if (buf.length < cursor + 4) return null;
      maskKey = buf.subarray(cursor, cursor + 4);
      cursor += 4;
    }
    if (buf.length < cursor + len) return null; // payload 未齐
    let payload = buf.subarray(cursor, cursor + len);
    if (maskKey) {
      const unmasked = Buffer.allocUnsafe(len);
      for (let i = 0; i < len; i++) unmasked[i] = payload[i] ^ maskKey[i & 3];
      payload = unmasked;
    }
    frames.push({ opcode, payload: Buffer.from(payload) });
    offset = cursor + len;
  }
  return { frames, rest: Buffer.alloc(0) };
}
