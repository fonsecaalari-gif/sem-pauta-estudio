// Captura a cena 3D frame a frame com Playwright (Chromium headless) e salva PNGs.
// uso: node render3d.mjs <modo> <pasta_saida>
import { chromium } from 'playwright';
import { createServer } from 'http';
import { readFile, mkdir, writeFile } from 'fs/promises';
import { extname, join, dirname } from 'path';
import { fileURLToPath } from 'url';
const here = dirname(fileURLToPath(import.meta.url));
const [mode = 'sting', out = join(here, 'out', mode)] = process.argv.slice(2);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json' };
const srv = createServer(async (req, res) => {
  try { const p = join(here, decodeURIComponent(new URL(req.url, 'http://x').pathname)); res.writeHead(200, { 'content-type': types[extname(p)] || 'application/octet-stream' }); res.end(await readFile(p)); }
  catch { res.writeHead(404); res.end(); }
}).listen(0);
const port = srv.address().port;
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage();
page.on('console', m => console.log('[page]', m.text())); page.on('pageerror', e => console.error('[erro]', e.message));
await page.goto(`http://localhost:${port}/cena.html?mode=${mode}`);
await page.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
const n = await page.evaluate(() => window.FRAMES);
await mkdir(out, { recursive: true });
for (let i = 0; i < n; i++) {
  const data = await page.evaluate(f => { window.renderFrame(f); return window.snapshot(); }, i);
  await writeFile(join(out, `f_${String(i).padStart(4, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
  if (i % 10 === 0) console.log(mode, i, '/', n);
}
await browser.close(); srv.close();
console.log('ok', out);
