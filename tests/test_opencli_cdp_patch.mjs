import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const prefix = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-opencli-patch-'));
const packageRoot = path.join(prefix, 'node_modules', '@jackwener', 'opencli');
try {
  fs.mkdirSync(path.join(packageRoot, 'clis', 'douyin'), { recursive: true });
  fs.mkdirSync(path.join(packageRoot, 'clis', 'bilibili'), { recursive: true });
  fs.mkdirSync(path.join(packageRoot, 'dist', 'src'), { recursive: true });
  const douyin = path.join(packageRoot, 'clis', 'douyin', 'user-videos.js');
  fs.writeFileSync(douyin, "    columns: ['index', 'aweme_id', 'title', 'duration', 'digg_count', 'play_url', 'top_comments'],\nreturn {\n                index: index + 1,\n};");
  const bilibili = path.join(packageRoot, 'clis', 'bilibili', 'utils.js');
  fs.writeFileSync(bilibili, 'async function nav() { return await res.json(); }\nasync function fetchJson() { return await res.json(); }');
  const runtime = path.join(packageRoot, 'dist', 'src', 'runtime.js');
  fs.writeFileSync(runtime, 'function getBrowserFactory(site) { if (site && isElectronApp(site)) return CDPBridge; return BrowserBridge; }');
  for (let attempt = 0; attempt < 2; attempt++) {
    const result = spawnSync(process.execPath, [path.join(root, 'scripts', 'patch-opencli.js'), prefix], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
  }
  const source = fs.readFileSync(runtime, 'utf8');
  const douyinSource = fs.readFileSync(douyin, 'utf8');
  assert.equal((douyinSource.match(/author: \{ nickname:/g) || []).length, 1);
  assert.ok(douyinSource.includes("'top_comments', 'author'"));
  assert.equal((fs.readFileSync(bilibili, 'utf8').match(/Bilibili non-JSON response/g) || []).length, 2);
  const select = new Function('process', 'isElectronApp', 'CDPBridge', 'BrowserBridge', `${source}; return getBrowserFactory;`);
  const env = {};
  const factory = select({ env }, site => site === 'electron', 'cdp', 'bridge');
  assert.equal(factory('douyin'), 'bridge');
  assert.equal(factory('electron'), 'cdp');
  env.OPENCLI_CDP_ENDPOINT = 'http://127.0.0.1:9222';
  assert.equal(factory('douyin'), 'cdp');
  assert.equal(factory('bilibili'), 'cdp');
  env.OPENCLI_CDP_ENDPOINT = ' ';
  assert.equal(factory('douyin'), 'bridge');
  console.log('OpenCLI CDP patch routing and idempotency passed');
} finally {
  fs.rmSync(prefix, { recursive: true, force: true });
}
