import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const prefix = fs.mkdtempSync(path.join(os.tmpdir(), 'workbench-bilibili-fallback-'));
const packageRoot = path.join(prefix, 'node_modules', '@jackwener', 'opencli');
const cliDirectory = path.join(packageRoot, 'clis');
const bilibiliDirectory = path.join(cliDirectory, 'bilibili');
let registration;

const userVideosFixture = `import { cli, Strategy } from '@jackwener/opencli/registry';
import { apiGet, payloadData, resolveUid } from './utils.js';
cli({
    site: 'bilibili',
    name: 'user-videos',
    access: 'read',
    description: '查看指定用户的投稿视频',
    domain: 'www.bilibili.com',
    strategy: Strategy.COOKIE,
    args: [
        { name: 'uid', required: true, positional: true, help: 'User UID or username' },
        { name: 'limit', type: 'int', default: 20, help: 'Number of results' },
        { name: 'order', default: 'pubdate', help: 'Sort: pubdate, click, stow' },
        { name: 'page', type: 'int', default: 1, help: 'Page number' },
    ],
    columns: ['rank', 'title', 'plays', 'likes', 'date', 'url'],
    func: async (page, kwargs) => {
        const { uid: uidInput, limit = 20, order = 'pubdate', page: pageNum = 1 } = kwargs;
        const uid = await resolveUid(page, String(uidInput));
        const payload = await apiGet(page, '/x/space/wbi/arc/search', {
            params: {
                mid: uid,
                pn: pageNum,
                ps: Math.min(Number(limit), 50),
                order,
            },
            signed: true,
        });
        const vlist = payloadData(payload)?.list?.vlist ?? [];
        return vlist.slice(0, Number(limit)).map((item, i) => ({
            rank: i + 1,
            title: item.title ?? '',
            plays: item.play ?? 0,
            likes: item.like ?? 0,
            date: item.created ? new Date(item.created * 1000).toISOString().slice(0, 10) : '',
            url: item.bvid ? \`https://www.bilibili.com/video/\${item.bvid}\` : '',
        }));
    },
});`;

function makeVideo(mid, bvid, title, pubdate, play, like) {
  return { mid, bvid, title, pubdate, play, like };
}

function loadCommand(apiGet) {
  let source = fs.readFileSync(path.join(bilibiliDirectory, 'user-videos.js'), 'utf8');
  source = source.replace(/^import .*;\r?\n/gm, '');
  registration = undefined;
  vm.runInNewContext(source, {
    cli: value => { registration = value; },
    Strategy: { COOKIE: 'cookie' },
    apiGet,
    payloadData: payload => payload?.data ?? payload,
    resolveUid: async (_page, value) => value,
    stripHtml: value => String(value).replace(/<[^>]*>/g, ''),
  });
  assert.equal(typeof registration?.func, 'function');
  return registration.func;
}

try {
  fs.mkdirSync(path.join(cliDirectory, 'douyin'), { recursive: true });
  fs.mkdirSync(bilibiliDirectory, { recursive: true });
  fs.mkdirSync(path.join(packageRoot, 'dist', 'src'), { recursive: true });
  fs.writeFileSync(
    path.join(cliDirectory, 'douyin', 'user-videos.js'),
    "    columns: ['index', 'aweme_id', 'title', 'duration', 'digg_count', 'play_url', 'top_comments'],\nreturn {\n                index: index + 1,\n};"
  );
  fs.writeFileSync(
    path.join(bilibiliDirectory, 'utils.js'),
    'async function nav() { return await res.json(); }\nasync function fetchJson() { return await res.json(); }'
  );
  fs.writeFileSync(path.join(bilibiliDirectory, 'user-videos.js'), userVideosFixture);
  fs.writeFileSync(
    path.join(packageRoot, 'dist', 'src', 'runtime.js'),
    'function getBrowserFactory(site) { if (site && isElectronApp(site)) return CDPBridge; return BrowserBridge; }'
  );

  for (let attempt = 0; attempt < 2; attempt++) {
    const result = spawnSync(
      process.execPath,
      [path.join(root, 'scripts', 'patch-opencli.js'), prefix],
      { encoding: 'utf8' }
    );
    assert.equal(result.status, 0, result.stderr);
  }

  const patchedSource = fs.readFileSync(path.join(bilibiliDirectory, 'user-videos.js'), 'utf8');
  assert.equal(
    (patchedSource.match(/WORKBENCH_BILIBILI_PUBLIC_SEARCH_FALLBACK_ON_412/g) || []).length,
    1
  );

  const calls = [];
  const fallbackCommand = loadCommand(async (_page, endpoint, options) => {
    calls.push({ endpoint, options });
    if (endpoint === '/x/space/wbi/arc/search') {
      throw new Error('Bilibili non-JSON response: HTTP 412 at /x/space/wbi/arc/search');
    }
    if (endpoint === '/x/web-interface/card') {
      return { data: { card: { name: '省钱曼波' } } };
    }
    if (endpoint === '/x/web-interface/search/all/v2') {
      const page = Number(options.params.page);
      const videos = page === 1
        ? [
          makeVideo('387663956', 'BVnew', '<em class="keyword">最新</em>作品', 300, 120, 12),
          makeVideo('900', 'BVother', '其他账号作品', 400, 999, 999),
          makeVideo('387663956', 'BVold', '较早作品', 100, 40, 4),
        ]
        : [
          makeVideo('387663956', 'BVmid', '中间作品', 200, 80, 8),
          makeVideo('387663956', 'BVnew', '重复作品', 300, 120, 12),
        ];
      return { data: { result: [{ result_type: 'video', data: videos }] } };
    }
    throw new Error(`Unexpected endpoint: ${endpoint}`);
  });
  const fallbackItems = await fallbackCommand({}, { uid: '387663956', limit: 3, page: 1 });
  assert.deepEqual(JSON.parse(JSON.stringify(fallbackItems)), [
    {
      rank: 1,
      title: '最新作品',
      plays: 120,
      likes: 12,
      date: new Date(300 * 1000).toISOString().slice(0, 10),
      url: 'https://www.bilibili.com/video/BVnew',
    },
    {
      rank: 2,
      title: '中间作品',
      plays: 80,
      likes: 8,
      date: new Date(200 * 1000).toISOString().slice(0, 10),
      url: 'https://www.bilibili.com/video/BVmid',
    },
    {
      rank: 3,
      title: '较早作品',
      plays: 40,
      likes: 4,
      date: new Date(100 * 1000).toISOString().slice(0, 10),
      url: 'https://www.bilibili.com/video/BVold',
    },
  ]);
  assert.deepEqual(calls.map(call => call.endpoint), [
    '/x/space/wbi/arc/search',
    '/x/web-interface/card',
    '/x/web-interface/search/all/v2',
    '/x/web-interface/search/all/v2',
  ]);

  let fallbackRequested = false;
  const normalCommand = loadCommand(async (_page, endpoint) => {
    if (endpoint !== '/x/space/wbi/arc/search') {
      fallbackRequested = true;
      throw new Error(`Unexpected fallback endpoint: ${endpoint}`);
    }
    return {
      data: {
        list: {
          vlist: [makeVideo('387663956', 'BVdirect', '正常接口作品', 500, 10, 2)],
        },
      },
    };
  });
  const normalItems = await normalCommand({}, { uid: '387663956', limit: 1 });
  assert.equal(normalItems[0].url, 'https://www.bilibili.com/video/BVdirect');
  assert.equal(fallbackRequested, false);

  const errorCommand = loadCommand(async (_page, endpoint) => {
    if (endpoint === '/x/space/wbi/arc/search') throw new Error('socket hang up');
    fallbackRequested = true;
    throw new Error(`Unexpected fallback endpoint: ${endpoint}`);
  });
  await assert.rejects(
    errorCommand({}, { uid: '387663956', limit: 1 }),
    /socket hang up/
  );
  assert.equal(fallbackRequested, false);

  console.log('Bilibili 412 public-search fallback, UID filtering, deduplication, sorting, and idempotency passed');
} finally {
  fs.rmSync(prefix, { recursive: true, force: true });
}
