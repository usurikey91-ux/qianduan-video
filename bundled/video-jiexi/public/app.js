const elements = {
  form: document.querySelector('#parse-form'),
  url: document.querySelector('#url'),
  clear: document.querySelector('#clear-button'),
  parseButton: document.querySelector('#parse-button'),
  detectedPlatform: document.querySelector('#detected-platform'),
  cookieOptions: document.querySelector('#cookie-options'),
  cookieBrowser: document.querySelector('#cookie-browser'),
  message: document.querySelector('#form-message'),
  loading: document.querySelector('#loading-panel'),
  result: document.querySelector('#result'),
  downloadDir: document.querySelector('#download-dir'),
  diskFree: document.querySelector('#disk-free'),
  thumbnail: document.querySelector('#thumbnail'),
  duration: document.querySelector('#duration'),
  title: document.querySelector('#title'),
  uploader: document.querySelector('#uploader'),
  formatCount: document.querySelector('#format-count'),
  source: document.querySelector('#source-badge'),
  formatBlock: document.querySelector('#format-block'),
  format: document.querySelector('#format'),
  formatNote: document.querySelector('#format-note'),
  download: document.querySelector('#download-button'),
  downloadLabel: document.querySelector('#download-label'),
  audioButton: document.querySelector('#audio-button'),
  coverButton: document.querySelector('#cover-button'),
  nextButton: document.querySelector('#next-button'),
  taskPanel: document.querySelector('#task-panel'),
  taskState: document.querySelector('#task-state'),
  taskMetric: document.querySelector('#task-metric'),
  taskFile: document.querySelector('#task-file'),
  progress: document.querySelector('#progress-bar'),
  cancel: document.querySelector('#cancel-button'),
  openFolder: document.querySelector('#open-folder-button'),
  directoryFeedback: document.querySelector('#directory-feedback')
};

let currentInfo = null;
let currentTask = null;
let pollTimer = null;

function scrollElementIntoView(element, block = 'center') {
  const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
  element.scrollIntoView({ behavior, block });
}

function formatDuration(seconds) {
  if (!seconds) return '';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return [hours, minutes, secs]
    .filter((_, index) => hours > 0 || index > 0)
    .map((part) => String(part).padStart(2, '0'))
    .join(':');
}

function formatSize(bytes) {
  if (!bytes) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit > 1 ? 1 : 0)} ${units[unit]}`;
}

function extractUrl(value) {
  const match = String(value).match(/https?:\/\/[^\s<>"'，。；！？、）》】]+/i);
  return match ? match[0].replace(/[),.;!?，。；！？、》】）]+$/u, '') : '';
}

function detectPlatform(value) {
  const url = extractUrl(value);
  if (!url) return '';
  try {
    const host = new URL(url).hostname.toLowerCase();
    const rules = [
      [/douyin\.com$/, '抖音'], [/tiktok\.com$/, 'TikTok'], [/kuaishou\.com$/, '快手'],
      [/(xiaohongshu\.com|xhslink\.com)$/, '小红书'], [/(bilibili\.com|b23\.tv)$/, '哔哩哔哩'],
      [/(youtube\.com|youtu\.be)$/, 'YouTube'], [/(weibo\.com|weibo\.cn)$/, '微博'],
      [/(twitter\.com|x\.com)$/, 'X'], [/instagram\.com$/, 'Instagram']
    ];
    return rules.find(([pattern]) => pattern.test(host))?.[1] || host.replace(/^www\./, '');
  } catch { return ''; }
}

function syncPlatformControls() {
  const platform = detectPlatform(elements.url.value);
  elements.detectedPlatform.textContent = platform ? `已识别 · ${platform}` : '';
  elements.detectedPlatform.classList.toggle('hidden', !platform);
  elements.cookieOptions.classList.toggle('hidden', platform !== '抖音');
  return platform;
}

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败。');
  return data;
}

function setParsing(active) {
  elements.loading.classList.toggle('hidden', !active);
  elements.parseButton.disabled = active;
  elements.parseButton.querySelector('span').textContent = active ? '解析中...' : '解析链接';
}

function renderInfo(info) {
  currentInfo = info;
  const isGallery = info.mediaType === 'gallery';
  const isCollection = info.mediaType === 'collection';
  const isBulkMedia = isGallery || isCollection;
  elements.url.value = info.inputUrl || elements.url.value;
  elements.thumbnail.src = info.thumbnail || '';
  elements.thumbnail.alt = isCollection ? '混合轮播预览' : isGallery ? '图文首图' : '视频封面';
  elements.thumbnail.style.visibility = info.thumbnail ? 'visible' : 'hidden';
  elements.duration.textContent = formatDuration(info.duration);
  elements.duration.classList.toggle('hidden', !info.duration);
  elements.title.textContent = info.title;
  elements.uploader.textContent = info.uploader || '未知发布者';
  elements.formatCount.textContent = isCollection
    ? `${info.imageCount} 张图片 · ${info.videoCount} 个视频`
    : isGallery ? `${info.imageCount} 张图片`
    : info.formats.length ? `${info.formats.length} 个可选画质` : '未找到可下载的视频流';
  elements.source.textContent = info.extractor || 'VIDEO';
  elements.formatBlock.classList.toggle('hidden', isBulkMedia);
  elements.audioButton.classList.toggle('hidden', isBulkMedia);
  elements.coverButton.classList.toggle('hidden', isBulkMedia);
  elements.download.dataset.kind = isCollection ? 'collection' : isGallery ? 'gallery' : 'video';
  elements.downloadLabel.textContent = isCollection ? '下载全部内容' : isGallery ? '下载全部图片' : '下载视频';

  elements.format.replaceChildren();
  for (const format of info.formats) {
    const details = [
      format.label,
      format.codecLabel || '视频',
      format.requiresTranscode ? '下载后转兼容 MP4' : '兼容 MP4',
      format.fps ? `${format.fps} FPS` : '',
      format.hasAudio ? '含音频' : format.hasSeparateAudio ? '自动合并音频' : '原素材无独立音轨',
      formatSize(format.filesize)
    ]
      .filter(Boolean).join(' · ');
    elements.format.add(new Option(details, format.id));
  }
  if (!info.formats.length) {
    elements.format.add(new Option('没有符合条件的画质', ''));
  }
  setDownloadButtons(false);
  elements.download.disabled = !isBulkMedia && !info.formats.length;
  elements.formatNote.textContent = info.formats.length
    ? '画质已归入常用档位；不兼容的编码或容器会在下载后自动转为 MP4。'
    : '该视频没有可下载的视频流。';
  elements.result.classList.remove('hidden');
  requestAnimationFrame(() => scrollElementIntoView(elements.download, 'center'));
}

async function inspect(event) {
  event.preventDefault();
  elements.message.textContent = '';
  elements.result.classList.add('hidden');
  setParsing(true);
  try {
    const platform = syncPlatformControls();
    const info = await api('/api/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: elements.url.value,
        cookieBrowser: platform === '抖音' ? elements.cookieBrowser.value : ''
      })
    });
    renderInfo(info);
  } catch (error) {
    elements.message.textContent = error.message;
  } finally {
    setParsing(false);
  }
}

function stateLabel(state) {
  return {
    queued: '等待下载',
    downloading: '正在下载',
    processing: '正在合并音视频',
    completed: '下载完成',
    cancelled: '已取消',
    error: '下载失败'
  }[state] || state;
}

function taskKindLabel(kind) {
  return { video: '视频', audio: 'MP3 音频', cover: '封面', gallery: '图文图片', collection: '混合轮播' }[kind] || '文件';
}

function renderTask(task) {
  currentTask = task;
  elements.taskPanel.classList.remove('hidden');
  const taskState = task.kind === 'gallery' && task.state === 'processing' ? '正在整理图片'
    : task.kind === 'collection' && task.state === 'processing' ? '正在整理内容'
      : stateLabel(task.state);
  elements.taskState.textContent = `${taskKindLabel(task.kind)} · ${taskState}`;
  elements.taskMetric.textContent = task.state === 'error'
    ? task.error
    : [task.progress ? `${task.progress.toFixed(1)}%` : '', task.speed, task.eta ? `剩余 ${task.eta}` : ''].filter(Boolean).join(' · ');
  elements.progress.style.width = `${task.progress || 0}%`;
  elements.taskFile.textContent = task.filename ? `已保存：${task.filename}` : '';
  elements.cancel.classList.toggle('hidden', ['completed', 'cancelled', 'error'].includes(task.state));
  const finished = ['completed', 'cancelled', 'error'].includes(task.state);
  setDownloadButtons(!finished);
}

async function pollTask() {
  if (!currentTask) return;
  try {
    const task = await api(`/api/downloads/${currentTask.id}`);
    renderTask(task);
    if (['completed', 'cancelled', 'error'].includes(task.state)) {
      clearTimeout(pollTimer);
      pollTimer = null;
      if (task.state === 'completed') {
        if (['video', 'cover', 'gallery', 'collection'].includes(task.kind)) await openFolder();
        scrollElementIntoView(elements.nextButton, 'center');
      }
      return;
    }
    pollTimer = setTimeout(pollTask, 700);
  } catch (error) {
    elements.taskMetric.textContent = error.message;
    elements.download.disabled = false;
  }
}

function setDownloadButtons(disabled) {
  document.querySelectorAll('[data-kind]').forEach((button) => { button.disabled = disabled; });
  elements.nextButton.disabled = disabled;
}

function resetForNext() {
  clearTimeout(pollTimer);
  pollTimer = null;
  currentInfo = null;
  currentTask = null;
  elements.url.value = '';
  elements.message.textContent = '';
  elements.result.classList.add('hidden');
  elements.taskPanel.classList.add('hidden');
  elements.detectedPlatform.classList.add('hidden');
  elements.cookieOptions.classList.add('hidden');
  elements.url.focus({ preventScroll: true });
  elements.url.scrollIntoView({ behavior: 'auto', block: 'center' });
}

async function startDownload(event) {
  if (!currentInfo) return;
  const kind = event.currentTarget.dataset.kind || 'video';
  if (kind === 'video' && !elements.format.value) {
    elements.message.textContent = '该视频没有可下载的视频流。';
    return;
  }
  setDownloadButtons(true);
  try {
    const task = await api('/api/downloads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        inspectionId: currentInfo.inspectionId,
        formatId: elements.format.value,
        kind
      })
    });
    renderTask(task);
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollTask, 300);
  } catch (error) {
    elements.message.textContent = error.message;
    setDownloadButtons(false);
  }
}

async function cancelDownload() {
  if (!currentTask) return;
  try {
    const task = await api(`/api/downloads/${currentTask.id}`, { method: 'DELETE' });
    renderTask(task);
    clearTimeout(pollTimer);
  } catch (error) {
    elements.taskMetric.textContent = error.message;
  }
}

async function openFolder() {
  elements.openFolder.disabled = true;
  elements.openFolder.querySelector('span').textContent = '正在打开...';
  elements.directoryFeedback.textContent = '';
  try {
    const result = await api('/api/files/open', { method: 'POST' });
    elements.directoryFeedback.textContent = result.message;
  } catch (error) {
    elements.directoryFeedback.textContent = `打开失败：${error.message}`;
  } finally {
    elements.openFolder.disabled = false;
    elements.openFolder.querySelector('span').textContent = '打开下载目录';
  }
}

async function checkHealth() {
  try {
    const health = await api('/api/health');
    elements.downloadDir.textContent = health.downloadDir;
    elements.diskFree.textContent = `可用空间 ${formatSize(health.diskFree)}`;
  } catch {
    elements.downloadDir.textContent = '无法读取下载目录';
    elements.diskFree.textContent = '';
  }
}

elements.form.addEventListener('submit', inspect);
elements.clear.addEventListener('click', () => {
  elements.url.value = '';
  elements.url.focus();
  elements.message.textContent = '';
  elements.result.classList.add('hidden');
  elements.detectedPlatform.classList.add('hidden');
  elements.cookieOptions.classList.add('hidden');
});
elements.nextButton.addEventListener('click', resetForNext);
document.querySelectorAll('[data-kind]').forEach((button) => button.addEventListener('click', startDownload));
elements.cancel.addEventListener('click', cancelDownload);
elements.openFolder.addEventListener('click', openFolder);
elements.url.addEventListener('input', syncPlatformControls);
elements.format.addEventListener('change', () => {
  const selected = currentInfo?.formats.find((format) => format.id === elements.format.value);
  elements.formatNote.textContent = selected?.hasAudio
    ? '该格式已包含音频，完成后统一输出为 MP4'
    : '将自动补充最佳音频并合并为 MP4';
});

checkHealth();

