// file: dashboard.spec.ts
// description: vk 管理看板 e2e - 真实 uvicorn + Playwright chromium 断言（五化-可视化&自动化）
// author: YanYuCloudCube Team
// created: 2026-09-20
// status: active
// tags: [e2e],[playwright],[dashboard],[rbac]

/**
 * vk 管理看板 e2e（真浏览器闭环）：
 * 前置：真实 uvicorn 子进程（密闭环境变量），本地复刻 Docker 布局 core/api → <tmp>/app。
 * 凭证：context extraHTTPHeaders 注入 X-API-Key（顶层导航无法带自定义头，page.route 注入
 *       与 goto 生命周期存在时序耦合易 ERR_ABORTED）。
 * 断言链：dashboard HTML 200/标题 → 无凭证 401 → 业务 Key：壳 200 / 数据 API 403 →
 *         admin 全流程：创建 → 列表渲染 → 搜索 → 编辑 → 停用/启用 → 用量 → 删除。
 */
import { chromium, expect, test, type Browser } from '@playwright/test';
import { spawn, type ChildProcess } from 'child_process';
import { mkdtempSync, rmSync, symlinkSync } from 'fs';
import os from 'os';
import path from 'path';

const ROOT = process.env.E2E_PROJECT_ROOT ?? `${__dirname}/../../../..`;
const PY = process.env.E2E_PYTHON ?? `${ROOT}/.venv/bin/python`;
const PORT = process.env.E2E_PORT ?? '3999';
const BASE = `http://127.0.0.1:${PORT}`;
const ADMIN_KEY = 'e2e-admin-key-1';
const BIZ_KEY = 'e2e-biz-key-1';
const DASH = `${BASE}/v1/admin/dashboard`;

let proc: ChildProcess | null = null;
let browser: Browser;
let tmpDir: string | null = null;
let childLog = '';

async function waitGateway(timeoutMs = 20_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`${BASE}/health`);
      if (r.ok) return;
    } catch {
      /* not yet */
    }
    if (proc && proc.exitCode !== null) {
      throw new Error(`uvicorn 提前退出(${proc.exitCode}):\n${childLog.slice(-2000)}`);
    }
    await new Promise((res) => setTimeout(res, 300));
  }
  throw new Error(`uvicorn 20s 未就绪: ${BASE}/health\n子进程输出:\n${childLog.slice(-2000)}`);
}

test.beforeAll(async () => {
  test.setTimeout(120_000);
  // 本地复刻 Docker 布局：core/api → <tmp>/app（对齐容器 /app/app），PYTHONPATH 指向 tmp
  tmpDir = mkdtempSync(path.join(os.tmpdir(), 'yyc3-e2e-'));
  const tmpSqlitePath = path.join(tmpDir, 'e2e-vk.sqlite3');
  symlinkSync(`${ROOT}/core/api`, path.join(tmpDir, 'app'), 'dir');
  // 密闭环境：默认值均非 change_me（可过关键配置校验）；上游池指向不可达地址（看板不依赖推理成功）
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    JWT_SECRET_KEY: 'e2e-only-secret-not-default',
    POSTGRES_PASSWORD: 'e2e-only-pg',
    REDIS_PASSWORD: 'e2e-only-redis',
    API_KEYS: BIZ_KEY,
    ADMIN_API_KEYS: ADMIN_KEY,
    OPENAI_COMPATIBLE_UPSTREAMS: JSON.stringify([
      {
        name: 'e2e-upstream',
        base_url: 'http://e2e-unused.test:9999',
        models: ['*'],
        priority: 1,
        weight: 100,
      },
    ]),
    OLLAMA_HOST: '127.0.0.1',
    OLLAMA_PORT: '11434',
    PROBE_ENABLED: 'false',
    // 本地无 PG：sqlite 自管 vk 表（ensure_tables 启动自建），vk 全链路真实落库
    DATABASE_URL: `sqlite+aiosqlite:///${tmpSqlitePath}`,
  };
  childLog = '';
  proc = spawn(
    PY,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', PORT, '--log-level', 'info'],
    { cwd: tmpDir, env: { ...env, PYTHONPATH: tmpDir } },
  );
  proc.stdout?.on('data', (d) => {
    childLog += String(d);
  });
  proc.stderr?.on('data', (d) => {
    childLog += String(d);
  });
  proc.on('error', (e) => {
    childLog += `\n[spawn error] ${e.message}`;
  });
  await waitGateway();

  browser = await chromium.launch({
    channel: process.platform === 'darwin' ? 'chrome' : undefined,
  });
});

test.afterAll(async () => {
  await browser?.close();
  if (proc?.pid) {
    // uvicorn 4 worker 场景 SIGTERM 可能留下孤儿占端口，SIGKILL 保证清理
    proc.kill('SIGKILL');
  }
  if (tmpDir) {
    rmSync(tmpDir, { recursive: true, force: true });
  }
});

test.describe('YYC³ vk 管理看板', () => {
  test('dashboard 可达且标题正确（admin 凭证）', async () => {
    const ctx = await browser.newContext({ extraHTTPHeaders: { 'X-API-Key': ADMIN_KEY } });
    const page = await ctx.newPage();
    const resp = await page.goto(DASH);
    expect(resp?.status()).toBe(200);
    await expect(page).toHaveTitle(/虚拟密钥看板/);
    await expect(page.locator('h1')).toHaveText(/YYC³ 虚拟密钥看板/);
    await ctx.close();
  });

  test('无凭证访问 dashboard → Auth 401（HTML 页也受保护）', async () => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    const resp = await page.goto(DASH);
    expect(resp?.status()).toBe(401);
    await ctx.close();
  });

  test('业务 Key：壳 200 → 数据 API 403 → prompt 补录 → 取消列表空（RBAC 分层）', async () => {
    const ctx = await browser.newContext({ extraHTTPHeaders: { 'X-API-Key': BIZ_KEY } });
    const page = await ctx.newPage();
    // 首个 load() 的 403 prompt 触发于导航期（Playwright 默认 dismiss，安全）；
    // goto 完成后再手动触发一次 load() 并注册监听，时序确定不依赖导航生命周期
    await page.goto(DASH);
    await expect(page.locator('h1')).toHaveText(/YYC³ 虚拟密钥看板/);
    let promptShown = false;
    page.on('dialog', (d) => {
      promptShown = true;
      void d.dismiss();
    });
    await page.evaluate('load()');
    await expect(page.locator('#cnt')).toHaveText(/共 0 条/, { timeout: 10_000 });
    expect(promptShown).toBe(true);
    await ctx.close();
  });

  test('admin 全流程：创建 → 列表渲染 → 搜索 → 编辑 → 停用/启用 → 用量 → 删除', async () => {
    test.setTimeout(60_000);
    const ctx = await browser.newContext({ extraHTTPHeaders: { 'X-API-Key': ADMIN_KEY } });
    const page = await ctx.newPage();
    // 预置 sessionStorage：页面自设头优先于 context 注入，预置后首次 fetch 即 200（无 prompt）
    await page.addInitScript(
      ({ k, v }) => sessionStorage.setItem(k, v),
      { k: 'yyc3-admin-key', v: ADMIN_KEY },
    );
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));
    page.on('requestfailed', (r) => pageErrors.push(`[reqfail] ${r.url()} ${r.failure()?.errorText}`));
    // 兜底：意外 JS dialog 一律接受，避免挂起
    page.on('dialog', (d) => void d.accept());
    await page.goto(DASH);

    // ① 创建（展开 details → 填表 → 提交 → 明文 Key 对话框）
    await page.locator('details summary').click();
    await page.fill('#f-name', 'e2e-vk');
    await page.fill('#f-budget', '10');
    await page.fill('#f-tpm', '500');
    await page.fill('#f-wl', 'glm-4*');
    await page.locator('details form button:not([type="button"])').click();
    try {
      await expect(page.locator('#dlg')).toBeVisible({ timeout: 10_000 });
    } catch (e) {
      const dlgT = await page.locator('#dlg-t').innerText().catch(() => '<n/a>');
      throw new Error(
        `创建对话框未弹出: ${e}\n#dlg-t=${dlgT}\npageErrors=${JSON.stringify(pageErrors)}`,
      );
    }
    await expect(page.locator('#dlg-t')).toContainText('创建成功');
    const plainKey = (await page.locator('#dlg-b').innerText()).trim();
    expect(plainKey.startsWith('vk-')).toBe(true);
    await page.locator('#dlg form button').click();

    // ② 列表渲染（行存在 + 状态 active + 预算 bar）
    const row = page.locator('#tbl tbody tr', { hasText: 'e2e-vk' });
    await expect(row).toHaveCount(1);
    await expect(row.locator('.tag.on')).toHaveText('active');
    await expect(row.locator('.bar .fill')).toBeVisible();

    // ③ 搜索过滤（无关词 0 行，命中词恢复）
    await page.fill('#q', '不存在的名字');
    await expect(page.locator('#cnt')).toHaveText(/共 0 条/);
    await page.fill('#q', 'e2e-vk');
    await expect(page.locator('#tbl tbody tr')).toHaveCount(1);

    // ④ 编辑（TPM 500 → 800）
    await row.locator('button', { hasText: '编辑' }).click();
    await expect(page.locator('#edlg')).toBeVisible();
    await expect(page.locator('#ed-name')).toHaveText('e2e-vk');
    await expect(page.locator('#e-budget')).toHaveValue('10');
    await expect(page.locator('#e-wl')).toHaveValue('glm-4*');
    await page.fill('#e-tpm', '800');
    // 「保存」按钮未显式写 type=submit（浏览器默认提交），:not([type=button]) 排除「取消」
    await page.locator('#edlg form button:not([type="button"])').click();
    await expect(page.locator('#edlg')).not.toBeVisible();
    await expect(page.locator('#tbl tbody tr', { hasText: '800' })).toHaveCount(1);

    // ⑤ 停用 → off 标签 → 启用恢复
    await page.locator('#tbl tbody tr button', { hasText: '停用' }).click();
    await expect(page.locator('#tbl tbody tr .tag.off')).toHaveText('disabled');
    await page.locator('#tbl tbody tr button', { hasText: '启用' }).click();
    await expect(page.locator('#tbl tbody tr .tag.on')).toHaveText('active');

    // ⑥ 用量弹窗（sqlite 空账本 → 暂无记录 + days=30 标题）
    await page.locator('#tbl tbody tr button', { hasText: '用量' }).click();
    await expect(page.locator('#dlg')).toBeVisible();
    await expect(page.locator('#dlg-t')).toContainText('近30天');
    await expect(page.locator('#dlg-b')).toContainText('暂无记录');
    await page.locator('#dlg form button').click();

    // ⑦ 删除（confirm 接受 → 行消失）
    page.once('dialog', (d) => void d.accept());
    await page.locator('#tbl tbody tr button', { hasText: '删除' }).click();
    await expect(page.locator('#tbl tbody tr', { hasText: 'e2e-vk' })).toHaveCount(0);
    await ctx.close();
  });
});
