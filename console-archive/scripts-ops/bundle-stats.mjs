// S12 取证: dist/assets 体积统计 (raw + gzip) → JSON (source-map-explorer 替代: 生产无 sourcemap 属策略)
import { readdirSync, statSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const dir = "dist/assets";
const files = readdirSync(dir).filter((f) => /\.(js|css)$/.test(f));
const entries = files.map((f) => {
  const buf = readFileSync(join(dir, f));
  return { file: f, rawKb: +(buf.length / 1024).toFixed(1), gzipKb: +(gzipSync(buf).length / 1024).toFixed(1) };
}).sort((a, b) => b.rawKb - a.rawKb);
const total = entries.reduce((s, e) => s + e.rawKb, 0);
const totalGzip = entries.reduce((s, e) => s + e.gzipKb, 0);
console.log(JSON.stringify({ generatedAt: new Date().toISOString(), chunks: entries.length, totalRawKb: +total.toFixed(1), totalGzipKb: +totalGzip.toFixed(1), largest: entries[0], top5: entries.slice(0, 5) }, null, 2));
void statSync;
