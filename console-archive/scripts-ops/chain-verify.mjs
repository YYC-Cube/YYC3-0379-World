// S13 链路一致性取证: manifest 字段完整性 + 图标清单对齐 + 平台覆盖 (只读)
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const m = JSON.parse(readFileSync(join(ROOT, "dist/manifest.json"), "utf8"));
const required = ["name", "short_name", "icons", "start_url", "display", "theme_color"];
const missingFields = required.filter((k) => !(k in m) || m[k] === "" || m[k] == null);

// manifest icons ↔ dist 文件对齐 (public 原样拷贝)
const iconFiles = m.icons.map((i) => i.src.replace(/^\//, ""));
const missingIcons = iconFiles.filter((src) => !existsSync(join(ROOT, "dist", src)));

// 平台覆盖 (仓库实际 5 平台: Web App/Android/iOS/macOS/watchOS)
const dir = join(ROOT, "public/yyc3-icons");
const platforms = {};
for (const p of readdirSync(dir, { withFileTypes: true })) {
  if (p.isDirectory()) platforms[p.name] = readdirSync(join(dir, p.name)).filter((f) => f.endsWith(".png")).length;
}
const totalPngs = Object.values(platforms).reduce((s, n) => s + n, 0);

console.log(JSON.stringify({
  manifest: {
    ok: missingFields.length === 0 && missingIcons.length === 0,
    missingFields,
    iconsDeclared: m.icons.length,
    missingIcons,
    fields: { name: m.name, short_name: m.short_name, start_url: m.start_url, display: m.display, theme_color: m.theme_color, background_color: m.background_color },
  },
  icons: { platforms: Object.keys(platforms).length, platformDetail: platforms, totalPngs, ok: Object.keys(platforms).length === 5 && totalPngs > 0 },
}, null, 2));
