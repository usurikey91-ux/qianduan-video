const http = require('node:http');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { randomUUID } = require('node:crypto');

const APP_ID = 'video-jiexi-local-v1';
const HOST = process.env.HOST || '0.0.0.0';
const PORT = Number(process.env.PORT || 4200);
const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const DOWNLOAD_DIR = process.env.DOWNLOAD_DIR || path.join(ROOT_DIR, 'downloads');
const OUTPUT_DIRS = {
  video: path.join(DOWNLOAD_DIR, '视频'),
  gallery: path.join(DOWNLOAD_DIR, '图文'),
  cover: path.join(DOWNLOAD_DIR, '图文'),
  audio: path.join(DOWNLOAD_DIR, '音乐')
};
const WORK_DIR = path.join(ROOT_DIR, 'work');
const LOCAL_YTDLP = path.join(ROOT_DIR, 'tools', 'yt-dlp.exe');
const YTDLP = process.env.YTDLP_PATH || (fs.existsSync(LOCAL_YTDLP) ? LOCAL_YTDLP : 'yt-dlp');
const systemFfmpeg = spawnSync('where.exe', ['ffmpeg'], { encoding: 'utf8', windowsHide: true });
let bundledFfmpeg = '';
try { bundledFfmpeg = require('ffmpeg-static') || ''; } catch {}
const FFMPEG = process.env.FFMPEG_PATH || systemFfmpeg.stdout?.split(/\r?\n/).find(Boolean) || bundledFfmpeg || 'ffmpeg';
const tasks = new Map();
const inspections = new Map();
const INSPECTION_TTL = 30 * 60 * 1000;
const TASK_TTL = 30 * 60 * 1000;
const MAX_JSON_BODY_BYTES = 64 * 1024;
const MAX_DOUYIN_PAGE_BYTES = 2 * 1024 * 1024;
const MAX_DOUYIN_IMAGES = 50;
const MAX_DOUYIN_IMAGE_BYTES = 50 * 1024 * 1024;
const DOUYIN_RENDER_TIMEOUT_MS = 25_000;
const DOUYIN_MOBILE_UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';
const publicBrowserProcesses = new Set();

fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });
for (const outputDir of Object.values(OUTPUT_DIRS)) fs.mkdirSync(outputDir, { recursive: true });
fs.mkdirSync(WORK_DIR, { recursive: true });

function sendJson(response, status, value) {
  const body = JSON.stringify(value);
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store'
  });
  response.end(body);
}

function sendText(response, status, value) {
  response.writeHead(status, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end(value);
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    let raw = '';
    let receivedBytes = 0;
    let settled = false;
    request.on('data', (chunk) => {
      if (settled) return;
      receivedBytes += Buffer.isBuffer(chunk) ? chunk.length : Buffer.byteLength(chunk);
      if (receivedBytes > MAX_JSON_BODY_BYTES) {
        settled = true;
        raw = '';
        const error = new Error('请求内容过大。');
        error.statusCode = 413;
        reject(error);
        return;
      }
      raw += chunk;
    });
    request.on('end', () => {
      if (settled) return;
      settled = true;
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        reject(new Error('请求内容不是有效的 JSON。'));
      }
    });
    request.on('error', (error) => {
      if (settled) return;
      settled = true;
      reject(error);
    });
  });
}

function normalizeUrl(value) {
  if (typeof value !== 'string' || value.length > 16_384) throw new Error('请输入有效的视频链接或分享文案。');
  const match = value.match(/https?:\/\/[^\s<>"'，。；！？、）》】]+/i);
  if (!match) throw new Error('没有找到链接，请粘贴包含 http 或 https 的分享内容。');
  const extracted = match[0].replace(/[),.;!?，。；！？、》】）]+$/u, '');
  let parsed;
  try {
    parsed = new URL(extracted);
  } catch {
    throw new Error('链接格式不正确。');
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('仅支持 http 或 https 链接。');
  return parsed.toString();
}

function detectPlatform(url) {
  if (!url) return '未知平台';
  const host = new URL(url).hostname.toLowerCase().replace(/^www\./, '');
  const platforms = [
    [/douyin\.com$/, '抖音'],
    [/iesdouyin\.com$/, '抖音'],
    [/tiktok\.com$/, 'TikTok'],
    [/kuaishou\.com$/, '快手'],
    [/(xiaohongshu\.com|xhslink\.com)$/, '小红书'],
    [/(bilibili\.com|b23\.tv)$/, '哔哩哔哩'],
    [/(youtube\.com|youtu\.be)$/, 'YouTube'],
    [/(weibo\.com|weibo\.cn)$/, '微博'],
    [/(twitter\.com|x\.com)$/, 'X / Twitter'],
    [/instagram\.com$/, 'Instagram']
  ];
  return platforms.find(([pattern]) => pattern.test(host))?.[1] || host;
}

function normalizeCookieBrowser(value) {
  if (value === undefined || value === null || value === '') return '';
  const browser = String(value).toLowerCase();
  if (!['edge', 'chrome', 'firefox'].includes(browser)) throw new Error('不支持的浏览器凭据选项。');
  return browser;
}

function cookieArgs(browser) {
  return browser ? ['--cookies-from-browser', browser] : [];
}

function baseYtDlpArgs(browser) {
  return ['--js-runtimes', 'node', ...cookieArgs(browser)];
}

function isLocalRequest(request) {
  const configuredToken = String(process.env.API_TOKEN || process.env.VIDEO_JIEXI_API_TOKEN || '').trim();
  if (configuredToken) {
    const authorization = String(request.headers.authorization || '');
    if (authorization === `Bearer ${configuredToken}`) return true;
  }
  const host = String(request.headers.host || '').toLowerCase();
  let hostname;
  try {
    hostname = new URL(`http://${host}`).hostname;
  } catch {
    return false;
  }
  const isPrivateIpv4 = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(hostname);
  const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
  if (new URL(`http://${host}`).port !== String(PORT) || (!isLocalHost && !isPrivateIpv4)) return false;
  const site = String(request.headers['sec-fetch-site'] || '').toLowerCase();
  if (site === 'cross-site') return false;
  const origin = request.headers.origin;
  if (!origin) return true;
  try {
    return new URL(origin).host === host && new URL(origin).protocol === 'http:';
  } catch {
    return false;
  }
}

function diskFreeBytes() {
  const stats = fs.statfsSync(DOWNLOAD_DIR);
  return Number(stats.bavail) * Number(stats.bsize);
}

function ensureDiskSpace(expectedBytes = 0, workingMultiplier = 1.5) {
  const reserve = 256 * 1024 * 1024;
  const required = Math.max(reserve, Math.ceil(Number(expectedBytes || 0) * workingMultiplier) + reserve);
  const free = diskFreeBytes();
  if (free < required) {
    const freeGb = (free / 1024 ** 3).toFixed(1);
    const requiredGb = (required / 1024 ** 3).toFixed(1);
    throw new Error(`磁盘空间不足：当前可用 ${freeGb} GB，建议至少保留 ${requiredGb} GB。`);
  }
}

function terminateProcessTree(child) {
  if (!child?.pid) return;
  const result = spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
  if (result.status !== 0 && child.exitCode === null) child.kill();
}

function cleanupTaskDir(taskDir) {
  const resolved = path.resolve(taskDir);
  if (resolved.startsWith(`${path.resolve(WORK_DIR)}${path.sep}`)) {
    fs.rmSync(resolved, { recursive: true, force: true });
  }
}

function moveUnique(source, destinationDir, desiredName = path.basename(source)) {
  const extension = path.extname(desiredName);
  const stem = path.basename(desiredName, extension);
  let destination = path.join(destinationDir, `${stem}${extension}`);
  let counter = 2;
  while (fs.existsSync(destination)) {
    destination = path.join(destinationDir, `${stem} (${counter})${extension}`);
    counter += 1;
  }
  fs.renameSync(source, destination);
  return destination;
}

function moveDirectoryUnique(source, destinationDir, desiredName) {
  const stem = safeFileStem(desiredName, '图文作品').slice(0, 120);
  let destination = path.join(destinationDir, stem);
  let counter = 2;
  while (fs.existsSync(destination)) {
    destination = path.join(destinationDir, `${stem} (${counter})`);
    counter += 1;
  }
  fs.renameSync(source, destination);
  return destination;
}

function outputDirectory(kind) {
  return OUTPUT_DIRS[kind] || DOWNLOAD_DIR;
}

function taskOutputPath(task) {
  if (!task || task.state !== 'completed' || !task.filename) return null;
  if (!['video', 'audio', 'cover'].includes(task.kind)) return null;
  const directory = path.resolve(outputDirectory(task.kind));
  const candidate = path.resolve(directory, task.filename);
  if (!candidate.startsWith(`${directory}${path.sep}`) || !fs.existsSync(candidate)) return null;
  return candidate;
}

function safeFileStem(value, fallback = 'video') {
  const stem = String(value || fallback)
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 180);
  return stem || fallback;
}

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: ROOT_DIR,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      ...options
    });
    let stdout = '';
    let stderr = '';
    const timeout = setTimeout(() => {
      terminateProcessTree(child);
      reject(new Error('解析超时，请稍后重试或检查链接是否需要登录。'));
    }, options.timeoutMs || 120_000);

    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.on('close', (code) => {
      clearTimeout(timeout);
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(cleanError(stderr || stdout) || `yt-dlp exited with code ${code}.`));
    });
  });
}

function cleanError(value) {
  const lines = String(value).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const useful = lines.filter((line) => /error|unsupported|login|cookies|private|not available/i.test(line));
  const message = (useful.at(-1) || lines.at(-1) || '').replace(/^ERROR:\s*/i, '');
  if (/fresh cookies/i.test(message)) {
    return '抖音需要新鲜 Cookie。请先在 Edge 或 Chrome 打开一次该链接，再在下方选择同一个浏览器重新解析。';
  }
  if (/could not copy.*cookie|database is locked/i.test(message)) {
    return '浏览器 Cookie 正在被占用。请完全退出所选浏览器后重试。';
  }
  if (/failed to decrypt with dpapi/i.test(message)) {
    return '当前 Edge/Chrome 启用了 App-Bound Cookie 加密，官方 yt-dlp 无法读取。请切换到已登录抖音的 Firefox，或选择不使用 Cookie 后重试。';
  }
  if (/could not find firefox cookies database/i.test(message)) {
    return 'Firefox 尚未建立可用 Cookie 配置。请先打开 Firefox 完成初始设置，登录抖音并访问一次该链接后重试。';
  }
  if (/failed to decrypt|decrypt.*cookie/i.test(message)) {
    return '无法读取所选浏览器的 Cookie，请尝试另一个已访问过抖音的浏览器。';
  }
  return message;
}

function qualityHeight(format) {
  const width = Number(format.width) || 0;
  const height = Number(format.height) || 0;
  if (!width || !height) return height;
  return Math.min(width, height);
}

const QUALITY_TIERS = [
  { height: 4320, label: '8K' },
  { height: 2160, label: '4K' },
  { height: 1440, label: '2K' },
  { height: 1080, label: '1080P' },
  { height: 720, label: '720P' }
];

function qualityTier(height) {
  const sourceHeight = Number(height) || 0;
  return QUALITY_TIERS.find((tier) => sourceHeight >= tier.height) || null;
}

function qualityLabel(height) {
  return qualityTier(height)?.label || `${Math.max(0, Math.round(Number(height) || 0))}P`;
}

function isH264(format) {
  return /^(avc1|h264)/i.test(format.vcodec || '');
}

function isAac(format) {
  return /^(mp4a|aac)/i.test(format.acodec || '');
}

function hasVideoTrack(format) {
  if (format.vcodec && format.vcodec !== 'none') return true;
  if (format.video_ext && format.video_ext !== 'none') return true;
  return Number(format.width) > 0 && Number(format.height) > 0;
}

function hasAudioTrack(format) {
  if (format.acodec && format.acodec !== 'none') return true;
  return Boolean(format.audio_ext && format.audio_ext !== 'none');
}

function hasKnownCodec(codec) {
  return Boolean(codec && codec !== 'none' && codec !== 'unknown' && codec !== 'NA');
}

function isMp4Container(format) {
  return String(format.ext || '').toLowerCase() === 'mp4';
}

function codecLabel(codec) {
  const value = String(codec || '').toLowerCase();
  if (/^(avc1|h264)/.test(value)) return 'H.264';
  if (/^(mp4a|aac)/.test(value)) return 'AAC';
  if (/^(hev1|hvc1|hevc)/.test(value)) return 'H.265 / HEVC';
  if (/^vp0?9/.test(value)) return 'VP9';
  if (/^av01|^av1/.test(value)) return 'AV1';
  return codec && codec !== 'none' ? String(codec).toUpperCase() : '';
}

function formatPreference(format) {
  const videoScore = isH264(format) ? 0 : /^(hev1|hvc1|hevc)/i.test(format.vcodec || '') ? 1 : 2;
  const audioScore = isAac(format) ? 0 : format.acodec && format.acodec !== 'none' ? 1 : 2;
  const containerScore = isMp4Container(format) ? 0 : 1;
  return videoScore * 100 + audioScore * 10 + containerScore;
}

function formatFilesize(format, duration) {
  const reported = Number(format.filesize || format.filesize_approx);
  if (reported > 0) return reported;
  const bitrateKbps = Number(format.tbr);
  const durationSeconds = Number(duration);
  if (bitrateKbps > 0 && durationSeconds > 0) {
    return Math.ceil(bitrateKbps * 1000 / 8 * durationSeconds);
  }
  return null;
}

function projectInfo(info) {
  const formats = Array.isArray(info.formats) ? info.formats : [];
  const hasSeparateAudio = formats.some((format) => format.acodec && format.acodec !== 'none'
    && (!format.vcodec || format.vcodec === 'none'));
  const seen = new Set();
  const videoFormats = formats
    .map((format) => ({ format, sourceHeight: qualityHeight(format), tier: qualityTier(qualityHeight(format)) }))
    .filter(({ format, tier }) => hasVideoTrack(format) && tier)
    .sort((a, b) => b.tier.height - a.tier.height
      || formatPreference(a.format) - formatPreference(b.format)
      || b.sourceHeight - a.sourceHeight
      || Number(b.format.tbr || 0) - Number(a.format.tbr || 0))
    .filter(({ tier }) => {
      const key = tier.height;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map(({ format, sourceHeight, tier }) => {
      const hasAudio = hasAudioTrack(format);
      const needsVideoTranscode = hasKnownCodec(format.vcodec) && !isH264(format);
      const needsAudioTranscode = hasAudio
        ? hasKnownCodec(format.acodec) && !isAac(format)
        : hasSeparateAudio;
      const needsContainerRemux = !isMp4Container(format);
      return {
        id: format.format_id,
        label: tier.label,
        ext: 'mp4',
        sourceExt: format.ext || '',
        height: sourceHeight,
        qualityHeight: tier.height,
        width: format.width,
        fps: format.fps,
        hasAudio,
        hasSeparateAudio,
        codec: format.vcodec,
        codecLabel: codecLabel(format.vcodec),
        audioCodec: hasAudio ? codecLabel(format.acodec) : '',
        needsVideoTranscode,
        needsAudioTranscode,
        needsContainerRemux,
        requiresTranscode: needsVideoTranscode || needsAudioTranscode || needsContainerRemux,
        filesize: formatFilesize(format, info.duration)
      };
    });

  return {
    id: info.id,
    title: info.title || '未命名视频',
    description: info.description || '',
    uploader: info.uploader || info.channel || info.creator || '',
    duration: info.duration || null,
    thumbnail: info.thumbnail || '',
    webpageUrl: info.webpage_url || '',
    extractor: info.extractor_key || info.extractor || '',
    platform: detectPlatform(info.webpage_url || info.original_url || info.url),
    live: Boolean(info.is_live),
    formats: videoFormats
  };
}

function parseDouyinRouterItem(html) {
  const match = String(html).match(/window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*<\/script>/s);
  if (!match) return null;
  const routerData = JSON.parse(match[1]);
  const page = Object.values(routerData.loaderData || {})
    .find((value) => value?.videoInfoRes?.item_list?.[0]);
  return page?.videoInfoRes?.item_list?.[0] || null;
}

function preferredResourceUrl(resource) {
  const urls = Array.isArray(resource?.url_list) ? resource.url_list.filter(Boolean) : [];
  return urls.find((candidate) => /\.jpe?g(?:\?|$)/i.test(candidate)) || urls[0] || '';
}

function parseDouyinGalleryHtml(html, webpageUrl = '') {
  const item = parseDouyinRouterItem(html);
  if (!item || !Array.isArray(item.images) || !item.images.length) return null;

  const images = item.images.slice(0, MAX_DOUYIN_IMAGES).map((image) => {
    const url = preferredResourceUrl(image);
    return url ? { url, width: Number(image.width) || null, height: Number(image.height) || null } : null;
  }).filter(Boolean);
  if (!images.length) return null;

  return {
    id: String(item.aweme_id || item.group_id_str || ''),
    title: item.desc || '抖音图文',
    description: item.desc || '',
    uploader: item.author?.nickname || item.author?.unique_id || '',
    duration: null,
    thumbnail: images[0].url,
    webpageUrl,
    extractor: 'Douyin 图文',
    platform: '抖音',
    mediaType: 'gallery',
    imageCount: images.length,
    downloadImages: images,
    downloadReferer: webpageUrl,
    formats: []
  };
}

function parseDouyinVideoHtml(html, webpageUrl = '') {
  const item = parseDouyinRouterItem(html);
  const video = item?.video;
  const sourceUrl = preferredResourceUrl(video?.play_addr);
  if (!item || !video || !sourceUrl) return null;

  let downloadUrl;
  try {
    downloadUrl = new URL(sourceUrl);
  } catch {
    return null;
  }
  const hostname = downloadUrl.hostname.toLowerCase();
  if (downloadUrl.protocol !== 'https:' || !/(^|\.)(snssdk\.com|douyinvod\.com)$/.test(hostname)) return null;
  downloadUrl.pathname = downloadUrl.pathname.replace('/aweme/v1/playwm/', '/aweme/v1/play/');
  downloadUrl.searchParams.delete('logo_name');

  const width = Number(video.width) || null;
  const height = Number(video.height) || null;
  const quality = width && height ? Math.min(width, height) : 720;
  const durationMs = Number(video.duration || item.duration) || 0;
  return {
    id: String(item.aweme_id || item.group_id_str || ''),
    title: item.desc || '抖音视频',
    description: item.desc || '',
    uploader: item.author?.nickname || item.author?.unique_id || '',
    duration: durationMs ? durationMs / 1000 : null,
    thumbnail: preferredResourceUrl(video.cover || video.origin_cover || video.dynamic_cover),
    webpageUrl,
    extractor: 'Douyin 公开分享页',
    platform: '抖音',
    mediaType: 'video',
    downloadUrl: downloadUrl.toString(),
    downloadReferer: webpageUrl,
    formats: [{
      id: 'douyin-direct',
      label: qualityLabel(quality),
      ext: 'mp4',
      sourceExt: 'mp4',
      height,
      width,
      fps: null,
      hasAudio: true,
      codec: 'h264',
      codecLabel: 'H.264',
      audioCodec: 'AAC',
      needsVideoTranscode: false,
      needsAudioTranscode: false,
      needsContainerRemux: false,
      requiresTranscode: false,
      filesize: null
    }]
  };
}

function findDouyinRenderedDetail(value, depth = 0) {
  if (!value || typeof value !== 'object' || depth > 10) return null;
  if (value.aweme?.detail && typeof value.aweme.detail === 'object') return value.aweme.detail;
  for (const child of Object.values(value)) {
    const detail = findDouyinRenderedDetail(child, depth + 1);
    if (detail) return detail;
  }
  return null;
}

function parseDouyinRenderedHtml(html, webpageUrl = '') {
  const scripts = String(html).matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi);
  for (const match of scripts) {
    const script = match[1].trim();
    const prefix = 'self.__pace_f.push(';
    if (!script.startsWith(prefix) || !script.includes('\\"aweme\\"')) continue;
    const closingParenthesis = script.lastIndexOf(')');
    if (closingParenthesis <= prefix.length) continue;

    try {
      const frame = JSON.parse(script.slice(prefix.length, closingParenthesis));
      const payload = frame?.[1];
      if (typeof payload !== 'string') continue;
      const separator = payload.indexOf(':');
      if (separator < 0) continue;
      const detail = findDouyinRenderedDetail(JSON.parse(payload.slice(separator + 1)));
      if (!Array.isArray(detail?.images) || !detail.images.length) continue;

      const images = detail.images.slice(0, MAX_DOUYIN_IMAGES).map((image) => {
        const candidates = [
          ...(Array.isArray(image.urlList) ? image.urlList : []),
          ...(Array.isArray(image.downloadUrlList) ? image.downloadUrlList : [])
        ].map(trustedCollectionImageUrl).filter(Boolean);
        const url = candidates.find((candidate) => /\.jpe?g(?:\?|$)/i.test(candidate)) || candidates[0] || '';
        return url ? { url, width: Number(image.width) || null, height: Number(image.height) || null } : null;
      }).filter(Boolean);
      if (!images.length) continue;

      return {
        id: String(detail.awemeId || detail.groupId || ''),
        title: detail.desc || detail.itemTitle || '抖音图文',
        description: detail.desc || '',
        uploader: detail.authorInfo?.nickname || detail.author?.nickname || '',
        duration: null,
        thumbnail: images[0].url,
        webpageUrl,
        extractor: 'Douyin 公开作品页',
        platform: '抖音',
        mediaType: 'gallery',
        imageCount: images.length,
        downloadImages: images,
        downloadReferer: webpageUrl,
        formats: []
      };
    } catch {
      // Other React server-component frames can use different payload formats.
    }
  }
  return null;
}

function trustedDouyinVideoUrl(value) {
  try {
    const parsed = new URL(value);
    const hostname = parsed.hostname.toLowerCase();
    if (parsed.protocol !== 'https:') return '';
    return /(^|\.)(douyinvod\.com|snssdk\.com)$/.test(hostname) ? parsed.toString() : '';
  } catch {
    return '';
  }
}

function douyinResourceUrls(resource) {
  const values = [
    ...(Array.isArray(resource?.url_list) ? resource.url_list : []),
    ...(Array.isArray(resource?.urlList) ? resource.urlList : [])
  ];
  return values.filter((value) => typeof value === 'string' && value);
}

function projectDouyinWebDetail(detail, webpageUrl = '') {
  if (!detail || typeof detail !== 'object') return null;
  const id = String(detail.aweme_id || detail.awemeId || detail.group_id || detail.groupId || '');
  const title = detail.desc || detail.item_title || detail.itemTitle || '抖音作品';
  const uploader = detail.author?.nickname || detail.authorInfo?.nickname || '';
  const rawImages = Array.isArray(detail.images) ? detail.images : [];

  if (rawImages.length) {
    const images = rawImages.slice(0, MAX_DOUYIN_IMAGES).map((image) => {
      const candidates = [
        ...douyinResourceUrls(image),
        ...douyinResourceUrls(image.download_url_list),
        ...(Array.isArray(image.downloadUrlList) ? image.downloadUrlList : [])
      ].map(trustedCollectionImageUrl).filter(Boolean);
      const url = candidates.find((candidate) => /\.jpe?g(?:\?|$)/i.test(candidate)) || candidates[0] || '';
      return url ? { url, width: Number(image.width) || null, height: Number(image.height) || null } : null;
    }).filter(Boolean);
    if (images.length) {
      return {
        id,
        title,
        description: detail.desc || '',
        uploader,
        duration: null,
        thumbnail: images[0].url,
        webpageUrl,
        extractor: 'Douyin 公开作品页',
        platform: '抖音',
        mediaType: 'gallery',
        imageCount: images.length,
        downloadImages: images,
        downloadReferer: webpageUrl,
        formats: []
      };
    }
  }

  const video = detail.video;
  if (!video || typeof video !== 'object') return null;
  const rates = Array.isArray(video.bit_rate) ? video.bit_rate : Array.isArray(video.bitRate) ? video.bitRate : [];
  const candidates = rates.map((entry) => {
    const resource = entry.play_addr || entry.playAddr;
    const url = douyinResourceUrls(resource).map(trustedDouyinVideoUrl).find(Boolean) || '';
    if (!url || Number(entry.is_h265 ?? entry.isH265) === 1) return null;
    return {
      url,
      width: Number(resource?.width) || null,
      height: Number(resource?.height) || null,
      bitrate: Number(entry.bit_rate ?? entry.bitRate) || 0,
      filesize: Number(resource?.data_size ?? resource?.dataSize) || null
    };
  }).filter(Boolean).sort((a, b) => Math.min(b.width || 0, b.height || 0) - Math.min(a.width || 0, a.height || 0)
    || b.bitrate - a.bitrate);

  const fallbackResource = video.play_addr || video.playAddr;
  const fallbackUrl = douyinResourceUrls(fallbackResource).map(trustedDouyinVideoUrl).find(Boolean) || '';
  const selected = candidates[0] || (fallbackUrl ? {
    url: fallbackUrl,
    width: Number(fallbackResource?.width) || null,
    height: Number(fallbackResource?.height) || null,
    bitrate: 0,
    filesize: Number(fallbackResource?.data_size ?? fallbackResource?.dataSize) || null
  } : null);
  if (!selected) return null;

  const quality = selected.width && selected.height ? Math.min(selected.width, selected.height) : 720;
  const durationMs = Number(video.duration || detail.duration) || 0;
  return {
    id,
    title,
    description: detail.desc || '',
    uploader,
    duration: durationMs ? durationMs / 1000 : null,
    thumbnail: douyinResourceUrls(video.cover || video.origin_cover || video.dynamic_cover).map(trustedCollectionImageUrl).find(Boolean) || '',
    webpageUrl,
    extractor: 'Douyin 公开作品页',
    platform: '抖音',
    mediaType: 'video',
    downloadUrl: selected.url,
    downloadReferer: webpageUrl,
    formats: [{
      id: 'douyin-browser-direct',
      label: qualityLabel(quality),
      ext: 'mp4',
      sourceExt: 'mp4',
      height: selected.height,
      width: selected.width,
      fps: null,
      hasAudio: true,
      hasSeparateAudio: false,
      codec: 'h264',
      codecLabel: 'H.264',
      audioCodec: 'AAC',
      needsVideoTranscode: false,
      needsAudioTranscode: false,
      needsContainerRemux: false,
      requiresTranscode: false,
      filesize: selected.filesize
    }]
  };
}

function findPublicBrowserExecutable() {
  const candidates = [
    process.env.PUBLIC_BROWSER_PATH,
    process.env.CHROME_PATH,
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
  ].filter(Boolean);
  return candidates.find((candidate) => fs.existsSync(candidate)) || '';
}

function reserveLoopbackPort() {
  return new Promise((resolve, reject) => {
    const socket = net.createServer();
    socket.unref();
    socket.once('error', reject);
    socket.listen(0, '127.0.0.1', () => {
      const address = socket.address();
      socket.close((error) => error ? reject(error) : resolve(address.port));
    });
  });
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitForPublicBrowserTarget(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) {
        const targets = await response.json();
        const target = targets.find((candidate) => candidate.type === 'page' && candidate.webSocketDebuggerUrl);
        if (target) return target.webSocketDebuggerUrl;
      }
    } catch {
      // Chrome may need a moment to create its first page target.
    }
    await wait(200);
  }
  throw new Error('公开页面渲染器启动超时。');
}

function sendCdpCommand(socket, id, method, params = {}, timeoutMs = 5_000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      socket.removeEventListener('message', onMessage);
      reject(new Error(`浏览器命令超时：${method}`));
    }, timeoutMs);
    const onMessage = (event) => {
      let message;
      try {
        const raw = typeof event.data === 'string' ? event.data : Buffer.from(event.data).toString('utf8');
        message = JSON.parse(raw);
      } catch {
        return;
      }
      if (message.id !== id) return;
      clearTimeout(timeout);
      socket.removeEventListener('message', onMessage);
      if (message.error) reject(new Error(message.error.message || `浏览器命令失败：${method}`));
      else resolve(message.result);
    };
    socket.addEventListener('message', onMessage);
    socket.send(JSON.stringify({ id, method, params }));
  });
}

function cleanupPublicBrowserProfile(profileDir) {
  const resolved = path.resolve(profileDir);
  if (path.dirname(resolved) !== path.resolve(WORK_DIR) || !path.basename(resolved).startsWith('.douyin-public-')) return;
  try {
    fs.rmSync(resolved, { recursive: true, force: true, maxRetries: 4, retryDelay: 150 });
  } catch {
    // A Chromium helper can briefly retain a file handle after the main process exits.
  }
}

async function renderDouyinPublicPage(url) {
  if (typeof WebSocket !== 'function') return null;
  const executable = findPublicBrowserExecutable();
  if (!executable) return null;

  const port = await reserveLoopbackPort();
  const profileDir = path.join(WORK_DIR, `.douyin-public-${randomUUID()}`);
  fs.mkdirSync(profileDir, { recursive: true });
  const child = spawn(executable, [
    '--headless=new',
    '--disable-gpu',
    '--disable-extensions',
    '--disable-sync',
    '--no-first-run',
    '--disable-default-apps',
    '--remote-debugging-address=127.0.0.1',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--window-size=1280,900',
    '--lang=zh-CN',
    'about:blank'
  ], { cwd: ROOT_DIR, windowsHide: true, stdio: 'ignore' });
  publicBrowserProcesses.add(child);
  let socket;
  let commandId = 1;
  let detailRequestId = '';
  let detailResponseReady = false;
  let onNetworkMessage;

  try {
    const webSocketUrl = await waitForPublicBrowserTarget(port, 8_000);
    socket = new WebSocket(webSocketUrl);
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('无法连接公开页面渲染器。')), 5_000);
      socket.addEventListener('open', () => { clearTimeout(timeout); resolve(); }, { once: true });
      socket.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('无法连接公开页面渲染器。')); }, { once: true });
    });

    onNetworkMessage = (event) => {
      let message;
      try {
        const raw = typeof event.data === 'string' ? event.data : Buffer.from(event.data).toString('utf8');
        message = JSON.parse(raw);
      } catch {
        return;
      }
      if (message.method === 'Network.responseReceived'
        && /\/aweme\/v1\/web\/aweme\/detail\//.test(message.params?.response?.url || '')) {
        detailRequestId = message.params.requestId;
        detailResponseReady = false;
      }
      if (message.method === 'Network.loadingFinished' && message.params?.requestId === detailRequestId) {
        detailResponseReady = true;
      }
    };
    socket.addEventListener('message', onNetworkMessage);
    await sendCdpCommand(socket, commandId++, 'Network.enable', {
      maxTotalBufferSize: 20 * 1024 * 1024,
      maxResourceBufferSize: 5 * 1024 * 1024
    });
    await sendCdpCommand(socket, commandId++, 'Page.enable');
    await sendCdpCommand(socket, commandId++, 'Runtime.enable');
    await sendCdpCommand(socket, commandId++, 'Page.navigate', { url });
    const deadline = Date.now() + DOUYIN_RENDER_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (detailRequestId && detailResponseReady) {
        try {
          const response = await sendCdpCommand(socket, commandId++, 'Network.getResponseBody', { requestId: detailRequestId }, 10_000);
          const rawBody = response.base64Encoded ? Buffer.from(response.body, 'base64').toString('utf8') : response.body;
          const body = JSON.parse(rawBody);
          const detail = body.aweme_detail || body.awemeDetail || body.detail;
          if (detail) {
            const location = await sendCdpCommand(socket, commandId++, 'Runtime.evaluate', {
              expression: 'location.href',
              returnByValue: true
            });
            return { detail, url: location.result?.value || url };
          }
        } catch {
          detailResponseReady = false;
        }
      }
      const probe = await sendCdpCommand(socket, commandId++, 'Runtime.evaluate', {
        expression: `(() => ({ ready: document.readyState, hasDetail: Array.from(document.scripts).some((script) => { const text = script.textContent || ''; return text.includes('self.__pace_f.push') && text.includes('\\\\"detail\\\\":{'); }) }))()`,
        returnByValue: true
      });
      if (probe.result?.value?.hasDetail) {
        const snapshot = await sendCdpCommand(socket, commandId++, 'Runtime.evaluate', {
          expression: `({ html: document.documentElement.outerHTML, url: location.href })`,
          returnByValue: true
        }, 10_000);
        return snapshot.result?.value || null;
      }
      await wait(300);
    }
    throw new Error('抖音公开作品页加载超时。');
  } finally {
    if (socket && onNetworkMessage) socket.removeEventListener('message', onNetworkMessage);
    if (socket?.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ id: commandId++, method: 'Browser.close', params: {} }));
        await wait(500);
      } catch {}
    }
    try { socket?.close(); } catch {}
    terminateProcessTree(child);
    publicBrowserProcesses.delete(child);
    await wait(200);
    cleanupPublicBrowserProfile(profileDir);
  }
}

async function inspectDouyinRenderedMedia(url) {
  const parsed = new URL(url);
  if (!/(^|\.)douyin\.com$|(^|\.)iesdouyin\.com$/.test(parsed.hostname.toLowerCase())) return null;
  const page = await renderDouyinPublicPage(url);
  if (!page) return null;
  return page.detail ? projectDouyinWebDetail(page.detail, page.url) : parseDouyinRenderedHtml(page.html, page.url);
}

async function fetchDouyinPublicPage(url) {
  const response = await fetch(url, {
    redirect: 'follow',
    headers: {
      'User-Agent': DOUYIN_MOBILE_UA,
      Accept: 'text/html,application/xhtml+xml'
    },
    signal: AbortSignal.timeout(20_000)
  });
  if (!response.ok) return null;
  const declaredSize = Number(response.headers.get('content-length')) || 0;
  if (declaredSize > MAX_DOUYIN_PAGE_BYTES) throw new Error('抖音公开分享页面内容过大。');
  const html = await response.text();
  if (Buffer.byteLength(html) > MAX_DOUYIN_PAGE_BYTES) throw new Error('抖音公开分享页面内容过大。');
  return { html, url: response.url };
}

function douyinShareFallback(url) {
  const parsed = new URL(url);
  const match = parsed.pathname.match(/\/(video|note)\/(\d+)/);
  return match ? `https://www.iesdouyin.com/share/${match[1]}/${match[2]}` : '';
}

async function inspectDouyinPublicMedia(url) {
  const parsed = new URL(url);
  const hostname = parsed.hostname.toLowerCase();
  if (!/(^|\.)douyin\.com$|(^|\.)iesdouyin\.com$/.test(hostname)) return null;
  const candidates = [url];
  const initialFallback = douyinShareFallback(url);
  if (initialFallback) candidates.push(initialFallback);

  for (let index = 0; index < candidates.length; index += 1) {
    const page = await fetchDouyinPublicPage(candidates[index]);
    if (!page) continue;
    const media = parseDouyinGalleryHtml(page.html, page.url) || parseDouyinVideoHtml(page.html, page.url);
    if (media) return media;
    const redirectedFallback = douyinShareFallback(page.url);
    if (redirectedFallback && !candidates.includes(redirectedFallback)) candidates.push(redirectedFallback);
  }
  return null;
}

function replaceBareUndefined(value) {
  let result = '';
  let quote = '';
  let escaped = false;
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    if (quote) {
      result += character;
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === quote) quote = '';
      continue;
    }
    if (character === '"') {
      quote = character;
      result += character;
      continue;
    }
    if (value.startsWith('undefined', index)) {
      const before = value[index - 1] || '';
      const after = value[index + 'undefined'.length] || '';
      if (!/[\w$]/.test(before) && !/[\w$]/.test(after)) {
        result += 'null';
        index += 'undefined'.length - 1;
        continue;
      }
    }
    result += character;
  }
  return result;
}

function parseXiaohongshuGalleryHtml(html, webpageUrl = '') {
  const match = String(html).match(/window\.__INITIAL_STATE__\s*=\s*(.*?)<\/script>/s);
  if (!match) return null;
  const initialState = JSON.parse(replaceBareUndefined(match[1].replace(/;\s*$/, '')));
  const note = initialState.noteData?.data?.noteData;
  if (!note || note.type === 'video' || !Array.isArray(note.imageList) || !note.imageList.length) return null;

  const images = note.imageList.slice(0, MAX_DOUYIN_IMAGES).map((image) => {
    const detailed = Array.isArray(image.infoList)
      ? image.infoList.find((item) => item?.imageScene === 'H5_DTL' && item.url)?.url
      : '';
    const candidate = detailed || image.url || '';
    if (!candidate) return null;
    let parsed;
    try {
      parsed = new URL(candidate);
    } catch {
      return null;
    }
    if (parsed.protocol === 'http:') parsed.protocol = 'https:';
    if (parsed.protocol !== 'https:' || !/(^|\.)xhscdn\.com$/.test(parsed.hostname.toLowerCase())) return null;
    return { url: parsed.toString(), width: Number(image.width) || null, height: Number(image.height) || null };
  }).filter(Boolean);
  if (!images.length) return null;

  return {
    id: String(note.noteId || ''),
    title: note.title || note.desc || '小红书图文',
    description: note.desc || '',
    uploader: note.user?.nickName || note.user?.nickname || '',
    duration: null,
    thumbnail: images[0].url,
    webpageUrl,
    extractor: 'Xiaohongshu 图文',
    platform: '小红书',
    mediaType: 'gallery',
    imageCount: images.length,
    downloadImages: images,
    downloadReferer: webpageUrl,
    formats: []
  };
}

async function inspectXiaohongshuPublicMedia(url) {
  const parsed = new URL(url);
  const hostname = parsed.hostname.toLowerCase();
  if (!/(^|\.)xiaohongshu\.com$|(^|\.)xhslink\.cn$/.test(hostname)) return null;
  const response = await fetch(url, {
    redirect: 'follow',
    headers: {
      'User-Agent': DOUYIN_MOBILE_UA,
      Accept: 'text/html,application/xhtml+xml'
    },
    signal: AbortSignal.timeout(20_000)
  });
  if (!response.ok) return null;
  const declaredSize = Number(response.headers.get('content-length')) || 0;
  if (declaredSize > MAX_DOUYIN_PAGE_BYTES) throw new Error('小红书公开页面内容过大。');
  const html = await response.text();
  if (Buffer.byteLength(html) > MAX_DOUYIN_PAGE_BYTES) throw new Error('小红书公开页面内容过大。');
  return parseXiaohongshuGalleryHtml(html, response.url);
}

function ytDlpCookieAttemptOrder(url, browser) {
  if (detectPlatform(url) !== '抖音') return [browser];
  return browser ? ['', browser] : [''];
}

function selectYtDlpInfo(rawInfo) {
  if (!Array.isArray(rawInfo.entries)) return { info: rawInfo, playlistIndex: null, playlistCount: null, playlistTitle: '' };
  const arrayIndex = rawInfo.entries.findIndex((entry) => Array.isArray(entry?.formats)
    && entry.formats.some((format) => format.vcodec && format.vcodec !== 'none'));
  if (arrayIndex < 0) return null;
  const info = rawInfo.entries[arrayIndex];
  return {
    info,
    playlistIndex: Number(info.playlist_index) || arrayIndex + 1,
    playlistCount: Number(rawInfo.playlist_count) || rawInfo.entries.length,
    playlistTitle: rawInfo.title || ''
  };
}

function trustedCollectionImageUrl(value) {
  try {
    const parsed = new URL(value);
    const hostname = parsed.hostname.toLowerCase();
    if (parsed.protocol !== 'https:') return '';
    return /(^|\.)(cdninstagram\.com|douyinpic\.com|byteimg\.com|xhscdn\.com|twimg\.com|sinaimg\.(cn|com)|weibocdn\.com|hdslb\.com|kwimgs\.com)$/.test(hostname)
      ? parsed.toString()
      : '';
  } catch {
    return '';
  }
}

function preferredCollectionImage(entry) {
  const candidates = [
    ...(Array.isArray(entry?.thumbnails) ? [...entry.thumbnails].sort((a, b) => Number(b.width || 0) * Number(b.height || 0)
      - Number(a.width || 0) * Number(a.height || 0)) : []),
    { url: entry?.thumbnail, width: entry?.width, height: entry?.height }
  ];
  for (const candidate of candidates) {
    const url = trustedCollectionImageUrl(candidate?.url);
    if (url) return { url, width: Number(candidate.width) || null, height: Number(candidate.height) || null };
  }
  return null;
}

function projectYtDlpCollection(rawInfo) {
  if (!Array.isArray(rawInfo.entries) || rawInfo.entries.length < 2) return null;
  const items = rawInfo.entries.map((entry, arrayIndex) => {
    if (!entry) return null;
    const projected = projectInfo(entry);
    if (projected.formats.length) {
      return {
        type: 'video',
        index: arrayIndex + 1,
        playlistIndex: Number(entry.playlist_index) || arrayIndex + 1,
        id: String(entry.id || ''),
        thumbnail: trustedCollectionImageUrl(entry.thumbnail),
        format: projected.formats[0]
      };
    }
    const image = preferredCollectionImage(entry);
    return image ? { type: 'image', index: arrayIndex + 1, id: String(entry.id || ''), ...image } : null;
  }).filter(Boolean);
  const imageCount = items.filter((item) => item.type === 'image').length;
  const videoCount = items.filter((item) => item.type === 'video').length;
  if (!imageCount || !videoCount) return null;

  const firstPreview = items.find((item) => item.type === 'image')?.url
    || items.find((item) => item.thumbnail)?.thumbnail || '';
  return {
    id: String(rawInfo.id || ''),
    title: rawInfo.title || '混合媒体作品',
    description: rawInfo.description || '',
    uploader: rawInfo.uploader || rawInfo.channel || rawInfo.creator || '',
    duration: null,
    thumbnail: firstPreview,
    webpageUrl: rawInfo.webpage_url || '',
    extractor: `${rawInfo.extractor_key || rawInfo.extractor || '媒体'} 轮播`,
    platform: detectPlatform(rawInfo.webpage_url || rawInfo.original_url || ''),
    mediaType: 'collection',
    itemCount: items.length,
    imageCount,
    videoCount,
    downloadItems: items,
    downloadReferer: rawInfo.webpage_url || '',
    formats: []
  };
}

async function inspectWithYtDlp(url, browser) {
  const { stdout } = await run(YTDLP, [
    '--dump-single-json',
    '--no-playlist',
    '--ignore-no-formats-error',
    '--no-warnings',
    '--skip-download',
    '--encoding', 'utf-8',
    ...baseYtDlpArgs(browser),
    url
  ]);
  const rawInfo = JSON.parse(stdout);
  const collection = projectYtDlpCollection(rawInfo);
  if (collection) return collection;
  const selected = selectYtDlpInfo(rawInfo);
  if (!selected) throw new Error('该链接中没有找到可下载的视频。');
  const projected = projectInfo(selected.info);
  if (selected.playlistIndex) {
    projected.playlistIndex = selected.playlistIndex;
    projected.playlistCount = selected.playlistCount;
    projected.title = `${selected.playlistTitle || projected.title} · 第 ${selected.playlistIndex}/${selected.playlistCount} 项视频`;
  }
  return projected;
}

async function inspectUrl(url, browser) {
  const douyinMedia = await inspectDouyinPublicMedia(url).catch(() => null);
  if (douyinMedia) return { info: douyinMedia, browser: '' };
  const xiaohongshuMedia = await inspectXiaohongshuPublicMedia(url).catch(() => null);
  if (xiaohongshuMedia) return { info: xiaohongshuMedia, browser: '' };

  let lastError;
  const attempts = ytDlpCookieAttemptOrder(url, browser);
  for (let index = 0; index < attempts.length; index += 1) {
    const candidateBrowser = attempts[index];
    try {
      return { info: await inspectWithYtDlp(url, candidateBrowser), browser: candidateBrowser };
    } catch (error) {
      lastError = error;
    }
    if (detectPlatform(url) === '抖音' && index === 0) {
      const renderedMedia = await inspectDouyinRenderedMedia(url).catch(() => null);
      if (renderedMedia) return { info: renderedMedia, browser: '' };
    }
  }
  throw lastError;
}

function normalizeDownloadKind(value) {
  const kind = value || 'video';
  if (!['video', 'audio', 'cover', 'gallery', 'collection'].includes(kind)) throw new Error('不支持的下载类型。');
  return kind;
}

function createInspection(url, browser, info) {
  const id = randomUUID();
  inspections.set(id, {
    id,
    url,
    browser,
    info,
    sourceUrl: info.downloadUrl || url,
    sourceReferer: info.downloadReferer || '',
    createdAt: Date.now()
  });
  return id;
}

function getInspection(value) {
  const inspection = inspections.get(String(value || ''));
  if (!inspection || Date.now() - inspection.createdAt > INSPECTION_TTL) {
    if (inspection) inspections.delete(inspection.id);
    throw new Error('解析结果已过期，请重新解析链接。');
  }
  return inspection;
}

function createDownload(inspection, formatId, requestedKind) {
  const kind = normalizeDownloadKind(requestedKind);
  if (inspection.info.mediaType === 'gallery') {
    if (kind !== 'gallery') throw new Error('图文作品仅支持下载全部图片。');
    return createGalleryDownload(inspection);
  }
  if (inspection.info.mediaType === 'collection') {
    if (kind !== 'collection') throw new Error('混合轮播仅支持按原顺序下载全部内容。');
    return createCollectionDownload(inspection);
  }
  const selected = kind === 'video'
    ? inspection.info.formats.find((format) => String(format.id) === String(formatId || ''))
    : null;
  if (kind === 'video' && !selected) throw new Error('所选画质不属于当前解析结果，请重新解析链接。');
  const directMedia = Boolean(inspection.sourceUrl && inspection.sourceUrl !== inspection.url);
  const directCover = directMedia && kind === 'cover' && Boolean(inspection.info.thumbnail);
  const directSource = directCover ? inspection.info.thumbnail : inspection.sourceUrl;
  const selectedFormat = directMedia ? 'best' : selected
    ? selected.hasAudio || !selected.hasSeparateAudio ? String(selected.id) : `${selected.id}+bestaudio`
    : null;
  ensureDiskSpace(selected?.filesize || 0, selected?.requiresTranscode ? 2.5 : 1.5);
  const id = randomUUID();
  const task = {
    id,
    kind,
    platform: detectPlatform(inspection.url),
    state: 'queued',
    progress: 0,
    speed: '',
    eta: '',
    filename: '',
    error: '',
    createdAt: Date.now(),
    process: null
  };
  tasks.set(id, task);

  const taskDir = path.join(WORK_DIR, id);
  fs.mkdirSync(taskDir, { recursive: true });
  const outputTemplate = directMedia
    ? path.join(taskDir, `${safeFileStem(inspection.info.title)} [${safeFileStem(inspection.info.id, 'video')}].%(ext)s`)
    : path.join(taskDir, '%(title).180B [%(id)s].%(ext)s');
  const sharedArgs = [
    '--newline',
    '--no-playlist',
    ...(inspection.info.playlistIndex ? ['--playlist-items', String(inspection.info.playlistIndex)] : []),
    '--windows-filenames',
    '--no-keep-video',
    '--ffmpeg-location', FFMPEG,
    '--output', outputTemplate,
    ...(directMedia ? ['--referer', inspection.sourceReferer] : baseYtDlpArgs(inspection.browser))
  ];
  const kindArgs = directCover
    ? ['--print', 'after_move:__FILE__:%(filepath)s']
    : kind === 'audio'
    ? ['--extract-audio', '--audio-format', 'mp3', '--audio-quality', '0', '--format', 'bestaudio/best', '--print', 'after_move:__FILE__:%(filepath)s']
    : kind === 'cover'
      ? ['--skip-download', '--write-thumbnail', '--convert-thumbnails', 'jpg']
      : ['--merge-output-format', 'mp4', '--format', selectedFormat, '--print', 'after_move:__FILE__:%(filepath)s'];
  const args = [
    ...sharedArgs,
    ...kindArgs,
    directSource
  ];

  const child = spawn(YTDLP, args, { cwd: ROOT_DIR, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  task.process = child;
  task.state = kind === 'cover' ? 'processing' : 'downloading';

  const consume = (chunk) => {
    const text = chunk.toString('utf8');
    for (const line of text.split(/\r?\n/)) {
      const progress = line.match(/\[download\]\s+([\d.]+)%/i);
      if (progress) {
        task.progress = Number(progress[1]);
        task.speed = line.match(/\bat\s+([^\s]+)/i)?.[1] || task.speed;
        task.eta = line.match(/\bETA\s+([^\s]+)/i)?.[1] || task.eta;
      }
      const file = line.match(/^__FILE__:(.+)$/);
      if (file) task.filename = path.basename(file[1].trim());
      if (/\[(Merger|ExtractAudio|VideoConvertor)\]/.test(line)) task.state = 'processing';
      if (/ERROR:/i.test(line)) task.error = cleanError(line);
    }
  };
  child.stdout.on('data', consume);
  child.stderr.on('data', consume);
  child.on('error', (error) => {
    task.state = 'error';
    task.error = error.code === 'ENOENT' ? '找不到 yt-dlp，请先运行 npm run setup。' : error.message;
    task.process = null;
    cleanupTaskDir(taskDir);
  });
  child.on('close', async (code) => {
    task.process = null;
    if (task.state === 'cancelled') {
      cleanupTaskDir(taskDir);
      return;
    }
    if (code === 0) {
      try {
        const extensionPattern = kind === 'cover'
          ? /\.(jpe?g|png|webp)$/i
          : kind === 'audio' ? /\.mp3$/i : /\.(mp4|mkv|webm|mov)$/i;
        const output = fs.readdirSync(taskDir).find((name) => extensionPattern.test(name) && !/\.part$/i.test(name));
        if (!output) {
          throw new Error(`没有找到生成的${kind === 'cover' ? '封面' : kind === 'audio' ? '音频' : '视频'}文件。`);
        }
        let finalOutput = path.join(taskDir, output);
        if (kind === 'video' && selected.requiresTranscode) {
          task.state = 'processing';
          const compatibleOutput = path.join(taskDir, `${safeFileStem(path.basename(output, path.extname(output)))} (compatible).mp4`);
          await transcodeForCompatibility(task, finalOutput, compatibleOutput, selected);
          if (task.state === 'cancelled') {
            cleanupTaskDir(taskDir);
            return;
          }
          fs.rmSync(finalOutput, { force: true });
          finalOutput = compatibleOutput;
        }
        const destination = moveUnique(finalOutput, outputDirectory(kind));
        task.filename = path.basename(destination);
        cleanupTaskDir(taskDir);
        task.state = 'completed';
        task.progress = 100;
      } catch (error) {
        if (task.state !== 'cancelled') {
          task.state = 'error';
          task.error = error.tool === 'ffmpeg' && error.code === 'ENOENT'
            ? '找不到 ffmpeg，无法转换为兼容的 MP4。请先运行 npm run setup。'
            : error.code === 'ENOENT'
              ? '下载生成的文件已被移动或删除，请重新下载。'
              : cleanError(error.message) || '视频转码失败。';
        }
        cleanupTaskDir(taskDir);
      }
    } else {
      task.state = 'error';
      task.error ||= `下载失败，yt-dlp 退出代码 ${code}。`;
      cleanupTaskDir(taskDir);
    }
  });

  return task;
}

function imageExtension(contentType, url) {
  const normalized = String(contentType || '').split(';')[0].trim().toLowerCase();
  if (normalized === 'image/png') return '.png';
  if (normalized === 'image/webp') return '.webp';
  if (normalized === 'image/gif') return '.gif';
  if (normalized === 'image/jpeg') return '.jpg';
  const extension = path.extname(new URL(url).pathname).toLowerCase();
  return ['.jpg', '.jpeg', '.png', '.webp', '.gif'].includes(extension) ? extension : '.jpg';
}

async function downloadGalleryImage(image, referer, signal) {
  const trustedUrl = trustedCollectionImageUrl(image.url);
  if (!trustedUrl) {
    throw new Error('图文作品返回了不受信任的图片地址。');
  }
  const response = await fetch(trustedUrl, {
    redirect: 'follow',
    headers: { 'User-Agent': DOUYIN_MOBILE_UA, Referer: referer || 'https://www.douyin.com/' },
    signal
  });
  if (!response.ok) throw new Error(`图片下载失败（HTTP ${response.status}）。`);
  const declaredSize = Number(response.headers.get('content-length')) || 0;
  if (declaredSize > MAX_DOUYIN_IMAGE_BYTES) throw new Error('单张图片超过 50 MB，已停止下载。');
  const buffer = Buffer.from(await response.arrayBuffer());
  if (buffer.length > MAX_DOUYIN_IMAGE_BYTES) throw new Error('单张图片超过 50 MB，已停止下载。');
  return { buffer, extension: imageExtension(response.headers.get('content-type'), response.url) };
}

function createGalleryDownload(inspection) {
  const images = inspection.info.downloadImages;
  if (!Array.isArray(images) || !images.length) throw new Error('该图文作品没有可下载的图片。');
  ensureDiskSpace();
  const id = randomUUID();
  const task = {
    id,
    kind: 'gallery',
    platform: inspection.info.platform || detectPlatform(inspection.url),
    state: 'downloading',
    progress: 0,
    speed: '',
    eta: '',
    filename: '',
    error: '',
    createdAt: Date.now(),
    process: null,
    abortController: new AbortController()
  };
  tasks.set(id, task);
  const taskDir = path.join(WORK_DIR, id);
  fs.mkdirSync(taskDir, { recursive: true });

  (async () => {
    try {
      for (let index = 0; index < images.length; index += 1) {
        const downloaded = await downloadGalleryImage(images[index], inspection.info.downloadReferer, task.abortController.signal);
        if (task.state === 'cancelled') return;
        const filename = `${String(index + 1).padStart(2, '0')}${downloaded.extension}`;
        fs.writeFileSync(path.join(taskDir, filename), downloaded.buffer);
        task.progress = Math.round(((index + 1) / images.length) * 100);
        task.speed = `${index + 1}/${images.length} 张`;
      }

      task.state = 'processing';
      if (task.state === 'cancelled') return;
      const folderName = `${safeFileStem(inspection.info.title, '图文作品').slice(0, 100)} [${safeFileStem(inspection.info.id, 'gallery')}]`;
      const destination = moveDirectoryUnique(taskDir, outputDirectory('gallery'), folderName);
      task.filename = path.basename(destination);
      task.state = 'completed';
      task.progress = 100;
      task.speed = `${images.length} 张图片`;
    } catch (error) {
      task.process = null;
      if (task.state !== 'cancelled') {
        task.state = 'error';
        task.error = error.name === 'AbortError' ? '图文下载已取消。' : cleanError(error.message) || '图文下载失败。';
      }
      cleanupTaskDir(taskDir);
    }
  })();

  return task;
}

function downloadCollectionVideo(inspection, item, itemOffset, taskDir, task, totalItems) {
  return new Promise((resolve, reject) => {
    const prefix = String(item.index).padStart(Math.max(2, String(totalItems).length), '0');
    const selected = item.format;
    const selectedFormat = selected.hasAudio || !selected.hasSeparateAudio
      ? String(selected.id)
      : `${selected.id}+bestaudio`;
    const outputTemplate = path.join(taskDir, `${prefix}.source.%(ext)s`);
    const args = [
      '--newline',
      '--no-warnings',
      '--no-playlist',
      '--playlist-items', String(item.playlistIndex),
      '--windows-filenames',
      '--no-keep-video',
      '--ffmpeg-location', FFMPEG,
      '--output', outputTemplate,
      ...baseYtDlpArgs(inspection.browser),
      '--format', selectedFormat,
      '--merge-output-format', 'mp4',
      '--print', 'after_move:__FILE__:%(filepath)s',
      inspection.url
    ];
    const child = spawn(YTDLP, args, { cwd: ROOT_DIR, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    task.process = child;
    task.state = 'downloading';
    let generatedPath = '';
    let stderr = '';

    const consume = (chunk, isError = false) => {
      const text = chunk.toString('utf8');
      if (isError) stderr = `${stderr}${text}`.slice(-64 * 1024);
      for (const line of text.split(/\r?\n/)) {
        const progress = line.match(/\[download\]\s+([\d.]+)%/i);
        if (progress) {
          const itemProgress = Number(progress[1]) / 100;
          task.progress = Math.round(((itemOffset + itemProgress) / totalItems) * 1000) / 10;
          task.speed = `${itemOffset + 1}/${totalItems} 项`;
        }
        const file = line.match(/^__FILE__:(.+)$/);
        if (file) generatedPath = file[1].trim();
      }
    };

    child.stdout.on('data', (chunk) => consume(chunk));
    child.stderr.on('data', (chunk) => consume(chunk, true));
    child.on('error', (error) => {
      if (task.process === child) task.process = null;
      reject(error);
    });
    child.on('close', (code) => {
      if (task.process === child) task.process = null;
      if (task.state === 'cancelled') return resolve('');
      if (code !== 0) return reject(new Error(cleanError(stderr) || `轮播第 ${item.index} 项视频下载失败。`));
      if (!generatedPath || !fs.existsSync(generatedPath)) {
        const output = fs.readdirSync(taskDir).find((name) => name.startsWith(`${prefix}.source.`) && !/\.part$/i.test(name));
        generatedPath = output ? path.join(taskDir, output) : '';
      }
      return generatedPath ? resolve(generatedPath) : reject(new Error(`没有找到轮播第 ${item.index} 项生成的视频文件。`));
    });
  });
}

function downloadCollectionImage(inspection, item, itemOffset, taskDir, task, totalItems) {
  return new Promise((resolve, reject) => {
    const prefix = String(item.index).padStart(Math.max(2, String(totalItems).length), '0');
    const args = [
      '--ignore-no-formats-error',
      '--no-warnings',
      '--no-playlist',
      '--playlist-items', String(item.index),
      '--skip-download',
      '--write-thumbnail',
      '--convert-thumbnails', 'jpg',
      '--output', path.join(taskDir, `${prefix}.%(ext)s`),
      ...baseYtDlpArgs(inspection.browser),
      inspection.url
    ];
    const child = spawn(YTDLP, args, { cwd: ROOT_DIR, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    task.process = child;
    task.state = 'downloading';
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr = `${stderr}${chunk}`.slice(-64 * 1024); });
    child.on('error', (error) => {
      if (task.process === child) task.process = null;
      reject(error);
    });
    child.on('close', (code) => {
      if (task.process === child) task.process = null;
      if (task.state === 'cancelled') return resolve('');
      if (code !== 0) return reject(new Error(cleanError(stderr) || `轮播第 ${item.index} 项图片下载失败。`));
      const output = fs.readdirSync(taskDir).find((name) => name === `${prefix}.jpg`);
      if (!output) return reject(new Error(`没有找到轮播第 ${item.index} 项生成的图片文件。`));
      task.progress = Math.round(((itemOffset + 1) / totalItems) * 1000) / 10;
      task.speed = `${itemOffset + 1}/${totalItems} 项`;
      return resolve(path.join(taskDir, output));
    });
  });
}

function createCollectionDownload(inspection) {
  const items = inspection.info.downloadItems;
  if (!Array.isArray(items) || !items.length) throw new Error('该混合轮播没有可下载的内容。');
  const expectedBytes = items.reduce((total, item) => total + Number(item.format?.filesize || 0), 0);
  ensureDiskSpace(expectedBytes, 2.5);
  const id = randomUUID();
  const task = {
    id,
    kind: 'collection',
    platform: inspection.info.platform || detectPlatform(inspection.url),
    state: 'downloading',
    progress: 0,
    speed: '',
    eta: '',
    filename: '',
    error: '',
    createdAt: Date.now(),
    process: null,
    abortController: new AbortController()
  };
  tasks.set(id, task);
  const taskDir = path.join(WORK_DIR, id);
  fs.mkdirSync(taskDir, { recursive: true });

  (async () => {
    try {
      for (let itemOffset = 0; itemOffset < items.length; itemOffset += 1) {
        const item = items[itemOffset];
        const prefix = String(item.index).padStart(Math.max(2, String(items.length).length), '0');
        if (item.type === 'image') {
          await downloadCollectionImage(inspection, item, itemOffset, taskDir, task, items.length);
          if (task.state === 'cancelled') {
            cleanupTaskDir(taskDir);
            return;
          }
        } else if (item.type === 'video') {
          let source = await downloadCollectionVideo(inspection, item, itemOffset, taskDir, task, items.length);
          if (task.state === 'cancelled') {
            cleanupTaskDir(taskDir);
            return;
          }
          const finalVideo = path.join(taskDir, `${prefix}.mp4`);
          if (item.format.requiresTranscode) {
            task.state = 'processing';
            await transcodeForCompatibility(task, source, finalVideo, item.format);
            if (task.state === 'cancelled') {
              cleanupTaskDir(taskDir);
              return;
            }
            fs.rmSync(source, { force: true });
          } else {
            fs.renameSync(source, finalVideo);
          }
        }
        task.progress = Math.round(((itemOffset + 1) / items.length) * 1000) / 10;
        task.speed = `${itemOffset + 1}/${items.length} 项`;
      }

      task.state = 'processing';
      const folderName = `${safeFileStem(inspection.info.title, '混合媒体作品').slice(0, 100)} [${safeFileStem(inspection.info.id, 'collection')}]`;
      const destination = moveDirectoryUnique(taskDir, outputDirectory('gallery'), folderName);
      task.filename = path.basename(destination);
      task.state = 'completed';
      task.progress = 100;
      task.speed = `${inspection.info.imageCount} 张图片 · ${inspection.info.videoCount} 个视频`;
    } catch (error) {
      if (task.state !== 'cancelled') {
        task.state = 'error';
        task.error = error.name === 'AbortError' ? '混合轮播下载已取消。' : cleanError(error.message) || '混合轮播下载失败。';
      }
      cleanupTaskDir(taskDir);
    }
  })();

  return task;
}

function transcodeForCompatibility(task, input, output, selected) {
  return new Promise((resolve, reject) => {
    const args = [
      '-y',
      '-i', input,
      '-map', '0:v:0',
      '-map', '0:a?',
      '-c:v', selected.needsVideoTranscode ? 'libx264' : 'copy',
      '-c:a', selected.needsAudioTranscode ? 'aac' : 'copy',
      ...(selected.needsAudioTranscode ? ['-b:a', '192k'] : []),
      '-movflags', '+faststart',
      output
    ];
    const child = spawn(FFMPEG, args, { cwd: ROOT_DIR, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    task.process = child;
    let stderr = '';
    child.stderr.on('data', (chunk) => {
      stderr = `${stderr}${chunk}`.slice(-64 * 1024);
    });
    child.on('error', (error) => {
      if (task.process === child) task.process = null;
      error.tool = 'ffmpeg';
      reject(error);
    });
    child.on('close', (code) => {
      if (task.process === child) task.process = null;
      if (task.state === 'cancelled') return resolve();
      if (code === 0) return resolve();
      reject(new Error(stderr || `ffmpeg exited with code ${code}.`));
    });
  });
}

function publicTask(task) {
  const { process: _process, abortController: _abortController, ...value } = task;
  return value;
}

function isTerminalTask(task) {
  return ['completed', 'cancelled', 'error'].includes(task.state);
}

function openExplorer(folderPath) {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(ROOT_DIR, 'scripts', 'open-folder.ps1');
    const args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath, '-FolderPath', folderPath];
    const child = spawn('powershell.exe', args, {
      windowsHide: true,
      stdio: ['ignore', 'ignore', 'pipe']
    });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.once('error', reject);
    child.once('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.trim() || '无法打开下载目录。'));
    });
  });
}

function serveFile(response, pathname) {
  const relative = pathname === '/' ? 'index.html' : pathname.slice(1);
  const fullPath = path.resolve(PUBLIC_DIR, relative);
  if (!fullPath.startsWith(`${PUBLIC_DIR}${path.sep}`)) return sendText(response, 403, 'Forbidden');
  fs.readFile(fullPath, (error, data) => {
    if (error) return sendText(response, 404, 'Not found');
    const contentTypes = {
      '.html': 'text/html; charset=utf-8',
      '.css': 'text/css; charset=utf-8',
      '.js': 'text/javascript; charset=utf-8',
      '.svg': 'image/svg+xml'
    };
    response.writeHead(200, {
      'Content-Type': contentTypes[path.extname(fullPath)] || 'application/octet-stream',
      'Cache-Control': 'no-store, max-age=0'
    });
    response.end(data);
  });
}

const server = http.createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url, `http://${request.headers.host || `${HOST}:${PORT}`}`);
    if (requestUrl.pathname.startsWith('/api/') && !isLocalRequest(request)) {
      return sendJson(response, 403, { error: '拒绝跨站访问本地接口。' });
    }
    if (request.method === 'GET' && requestUrl.pathname === '/api/health') {
      const ytVersion = spawnSync(YTDLP, ['--version'], { encoding: 'utf8', windowsHide: true });
      const ffmpegVersion = spawnSync(FFMPEG, ['-version'], { encoding: 'utf8', windowsHide: true });
      return sendJson(response, 200, {
        appId: APP_ID,
        ok: ytVersion.status === 0 && ffmpegVersion.status === 0,
        ytDlp: ytVersion.status === 0 ? ytVersion.stdout.trim() : null,
        ffmpeg: ffmpegVersion.status === 0 ? ffmpegVersion.stdout.split(/\r?\n/)[0] : null,
        downloadDir: DOWNLOAD_DIR,
        diskFree: diskFreeBytes()
      });
    }

    if (request.method === 'POST' && requestUrl.pathname === '/api/files/open') {
      await openExplorer(DOWNLOAD_DIR);
      return sendJson(response, 200, { ok: true, message: '下载目录已打开。' });
    }

    if (request.method === 'POST' && requestUrl.pathname === '/api/inspect') {
      const body = await readJson(request);
      const url = normalizeUrl(body.url);
      const browser = normalizeCookieBrowser(body.cookieBrowser);
      const inspection = await inspectUrl(url, browser);
      const { info } = inspection;
      const inspectionId = createInspection(url, inspection.browser, info);
      const { downloadUrl: _downloadUrl, downloadReferer: _downloadReferer, downloadImages: _downloadImages, downloadItems: _downloadItems, ...publicInfo } = info;
      return sendJson(response, 200, { ...publicInfo, inspectionId, inputUrl: url, platform: detectPlatform(url) });
    }

    if (request.method === 'POST' && requestUrl.pathname === '/api/downloads') {
      const body = await readJson(request);
      const inspection = getInspection(body.inspectionId);
      return sendJson(response, 202, publicTask(createDownload(inspection, body.formatId, body.kind)));
    }

    const taskMatch = requestUrl.pathname.match(/^\/api\/downloads\/([a-f0-9-]+)$/i);
    const taskFileMatch = requestUrl.pathname.match(/^\/api\/downloads\/([a-f0-9-]+)\/file$/i);
    if (taskFileMatch && request.method === 'GET') {
      const task = tasks.get(taskFileMatch[1]);
      const filePath = taskOutputPath(task);
      if (!task) return sendJson(response, 404, { error: '任务不存在。' });
      if (!filePath) return sendJson(response, 409, { error: '任务尚未完成或该任务类型暂不支持文件接口。' });
      const stat = fs.statSync(filePath);
      const extension = path.extname(filePath).toLowerCase();
      const contentType = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.mov': 'video/quicktime',
        '.mp3': 'audio/mpeg',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp'
      }[extension] || 'application/octet-stream';
      response.writeHead(200, {
        'Content-Type': contentType,
        'Content-Length': stat.size,
        'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(path.basename(filePath))}`,
        'Cache-Control': 'no-store'
      });
      return fs.createReadStream(filePath).pipe(response);
    }
    if (taskMatch && request.method === 'GET') {
      const task = tasks.get(taskMatch[1]);
      return task ? sendJson(response, 200, publicTask(task)) : sendJson(response, 404, { error: '任务不存在。' });
    }
    if (taskMatch && request.method === 'DELETE') {
      const task = tasks.get(taskMatch[1]);
      if (!task) return sendJson(response, 404, { error: '任务不存在。' });
      if (isTerminalTask(task)) return sendJson(response, 200, publicTask(task));
      if (task.process) terminateProcessTree(task.process);
      task.abortController?.abort();
      task.state = 'cancelled';
      return sendJson(response, 200, publicTask(task));
    }

    if (request.method === 'GET') return serveFile(response, requestUrl.pathname);
    return sendJson(response, 404, { error: '接口不存在。' });
  } catch (error) {
    const message = error.code === 'ENOENT'
      ? '找不到 yt-dlp，请先运行 npm run setup。'
      : error.message || '服务器发生错误。';
    sendJson(response, error.statusCode || 400, { error: message });
  }
});

if (require.main === module) {
  server.listen(PORT, HOST, () => {
    console.log(`Video Jiexi is running at http://${HOST}:${PORT}`);
    console.log(`Downloads: ${DOWNLOAD_DIR}`);
  });
}

const cleanupTimer = setInterval(() => {
  const now = Date.now();
  for (const [id, inspection] of inspections) {
    if (now - inspection.createdAt > INSPECTION_TTL) inspections.delete(id);
  }
  for (const [id, task] of tasks) {
    if (!task.process && now - task.createdAt > TASK_TTL) tasks.delete(id);
  }
}, 5 * 60 * 1000);
cleanupTimer.unref();

function shutdown() {
  for (const task of tasks.values()) {
    if (task.process) terminateProcessTree(task.process);
  }
  for (const child of publicBrowserProcesses) terminateProcessTree(child);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 3_000).unref();
}

process.once('SIGINT', shutdown);
process.once('SIGTERM', shutdown);

module.exports = { APP_ID, cleanError, normalizeUrl, detectPlatform, projectInfo, projectYtDlpCollection, projectDouyinWebDetail, parseDouyinGalleryHtml, parseDouyinVideoHtml, parseDouyinRenderedHtml, parseXiaohongshuGalleryHtml, readJson, isLocalRequest, isTerminalTask, ytDlpCookieAttemptOrder, selectYtDlpInfo, server };
