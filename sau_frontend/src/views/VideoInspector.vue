<template>
  <div class="video-inspector">
    <header class="sau-page-head">
      <span class="sau-page-icon"><el-icon><VideoPlay /></el-icon></span>
      <div class="sau-page-title">
        <h1>视频解析</h1>
        <p>调用已配置的视频解析服务处理公开分享链接，并将结果保存到本地素材目录</p>
      </div>
      <div class="sau-page-counts">
        <span class="sau-badge" :class="serviceAvailable ? 'is-success' : 'is-warning'">
          {{ serviceAvailable ? '解析服务在线' : '解析服务未连接' }}
        </span>
      </div>
      <div class="sau-page-actions">
        <el-button :icon="FolderOpened" :disabled="!downloadDir" @click="openFolder">打开下载文件夹</el-button>
      </div>
    </header>

    <div class="sau-page-filters">
      <div class="sau-chips">
        <span class="sau-chip is-label"><el-icon><Link /></el-icon>支持公开链接</span>
        <span v-for="platform in supportedPlatforms" :key="platform" class="sau-badge">{{ platform }}</span>
      </div>
    </div>

    <div class="sau-page-body">
    <el-card shadow="never" class="inspect-card">
      <div class="inspect-row">
        <el-input v-model="url" clearable placeholder="粘贴抖音或其他平台分享链接" @keyup.enter="inspect" />
        <el-select v-model="cookieBrowser" clearable placeholder="凭据" style="width: 130px">
          <el-option label="不读取 Cookie" value="" />
          <el-option label="Chrome Cookie" value="chrome" />
          <el-option label="Edge Cookie" value="edge" />
          <el-option label="Firefox Cookie" value="firefox" />
        </el-select>
        <el-button type="primary" :loading="inspecting" @click="inspect">解析链接</el-button>
      </div>
      <div class="service-note">下载目录 <code>{{ downloadDir || '未读取到目录' }}</code> · {{ embeddedService ? '解析引擎已内置于本工作台' : `服务地址：${serviceBaseUrl || '未配置'}` }}</div>
    </el-card>

    <el-card v-if="info" shadow="never" class="result-card">
      <template #header>
        <div class="card-header"><span>解析结果</span><el-tag effect="plain">{{ info.platform || '媒体' }}</el-tag></div>
      </template>
      <div class="result-grid">
        <div>
          <div class="result-title">{{ info.title || '未识别标题' }}</div>
          <div class="result-meta">{{ info.uploader || '未知作者' }} · {{ info.duration || '-' }}</div>
          <p class="result-description">{{ info.description || '没有返回描述' }}</p>
        </div>
        <img v-if="info.thumbnail" :src="info.thumbnail" class="cover" alt="封面" />
      </div>
      <div v-if="info.mediaType !== 'gallery' && info.mediaType !== 'collection'" class="format-row">
        <el-select v-if="info.formats?.length" v-model="formatId" placeholder="选择画质" style="min-width: 240px">
          <el-option v-for="format in info.formats" :key="format.id" :label="format.label || format.id" :value="String(format.id)" />
        </el-select>
        <el-button type="primary" :loading="downloading" @click="download">下载视频</el-button>
      </div>
      <el-empty v-else description="当前版本先处理单条视频；图文或混合轮播取决于已配置的解析服务" :image-size="60" />
    </el-card>

    <el-card v-if="task" shadow="never" class="task-card">
      <template #header><div class="card-header"><span>下载任务</span><el-tag :type="task.state === 'completed' ? 'success' : task.state === 'error' ? 'danger' : 'warning'">{{ taskStateText }}</el-tag></div></template>
      <el-progress :percentage="Math.round(Number(task.progress) || 0)" :status="task.state === 'error' ? 'exception' : task.state === 'completed' ? 'success' : undefined" />
      <div class="task-message">{{ task.error || task.filename || '正在下载…' }}</div>
      <div class="task-actions">
        <el-tag v-if="task.state === 'completed'" type="success">下载完成</el-tag>
        <el-button v-if="task.state === 'completed'" type="primary" size="small" :loading="importing" @click="importMaterial">导入素材库</el-button>
        <el-button v-if="['queued','downloading','processing'].includes(task.state)" size="small" @click="stopWaiting">停止等待</el-button>
      </div>
    </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { videoJiexiApi } from '@/api/videoJiexi'
import { FolderOpened, Link, VideoPlay } from '@element-plus/icons-vue'

const url = ref('')
const cookieBrowser = ref('')
const info = ref(null)
const formatId = ref('')
const task = ref(null)
const taskId = ref('')
const inspecting = ref(false)
const downloading = ref(false)
const importing = ref(false)
const route = useRoute()
const serviceAvailable = ref(false)
const serviceBaseUrl = ref('')
const downloadDir = ref('')
const embeddedService = ref(false)
const supportedPlatforms = ['抖音', 'TikTok', '哔哩哔哩', 'YouTube', '小红书', '快手', '微博', 'X', 'Instagram']
let pollTimer

const taskStateText = computed(() => ({ queued: '排队中', downloading: '下载中', processing: '处理中', completed: '已完成', error: '失败', cancelled: '已取消' }[task.value?.state] || task.value?.state || '未知'))

async function checkStatus() {
  const response = await videoJiexiApi.status()
  serviceAvailable.value = Boolean(response.data?.health?.ok)
  embeddedService.value = Boolean(response.data?.embedded)
  serviceBaseUrl.value = response.data?.base_url || ''
  downloadDir.value = response.data?.download_dir || response.data?.health?.downloadDir || ''
}

async function openFolder() {
  try {
    await videoJiexiApi.openFolder()
    ElMessage.success('已打开下载文件夹')
  } catch (error) {
    ElMessage.error(error?.message || '打开下载文件夹失败')
  }
}

async function inspect() {
  if (!url.value.trim()) return ElMessage.warning('请先粘贴视频链接')
  inspecting.value = true
  try {
    const response = await videoJiexiApi.inspect(url.value.trim(), cookieBrowser.value)
    info.value = response.data
    formatId.value = response.data?.formats?.[0]?.id ? String(response.data.formats[0].id) : ''
    task.value = null
    ElMessage.success('解析完成')
  } catch (error) {
    info.value = null
    const message = error?.response?.data?.msg || error?.response?.data?.error || error?.message || '解析链接失败'
    ElMessage.error(message)
  } finally { inspecting.value = false }
}

async function download() {
  if (!info.value?.inspectionId) return ElMessage.warning('请先解析链接')
  downloading.value = true
  try {
    const response = await videoJiexiApi.download(info.value.inspectionId, formatId.value)
    task.value = response.data
    taskId.value = response.data?.id || ''
    startPolling()
  } catch (error) {
    const message = error?.response?.data?.msg || error?.response?.data?.error || error?.message || '下载任务创建失败'
    ElMessage.error(message)
  } finally { downloading.value = false }
}

async function importMaterial() {
  if (!taskId.value) return
  importing.value = true
  try {
    await videoJiexiApi.importMaterial(taskId.value)
    ElMessage.success('已导入素材库')
  } catch (error) {
    const message = error?.response?.data?.msg || error?.response?.data?.error || error?.message || '导入素材失败'
    ElMessage.error(message)
  } finally { importing.value = false }
}

function stopWaiting() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
  const currentTaskId = taskId.value
  task.value = { ...task.value, state: 'cancelled', error: '正在取消任务…' }
  if (currentTaskId) {
    videoJiexiApi.cancel(currentTaskId)
      .then((response) => { task.value = response.data || { ...task.value, state: 'cancelled', error: '任务已取消' } })
      .catch((error) => { task.value = { ...task.value, state: 'error', error: error?.response?.data?.msg || '取消任务失败' } })
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    try {
      const response = await videoJiexiApi.task(taskId.value)
      task.value = response.data
      if (['completed', 'error', 'cancelled'].includes(task.value?.state)) {
        clearInterval(pollTimer)
        if (task.value.state === 'completed') ElMessage.success('下载完成，可以导入素材库')
      }
    } catch (error) {
      clearInterval(pollTimer)
      pollTimer = null
      task.value = { ...task.value, state: 'error', error: error?.response?.data?.msg || error?.message || '任务状态获取失败' }
      ElMessage.error(task.value.error)
    }
  }, 2000)
}


onMounted(() => {
  checkStatus().catch(() => { serviceAvailable.value = false })
  const incomingUrl = String(route.query.url || '').trim()
  if (incomingUrl) {
    url.value = incomingUrl
    window.setTimeout(() => { inspect().catch(() => {}) }, 120)
  }
})
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.video-inspector { min-width:0; }
.sau-page-body { display:grid; gap:14px; max-width:960px; }
.inspect-row { display:flex; gap:12px; }
.inspect-row .el-input { flex:1; }
.service-note { margin-top:10px; color:var(--sau-muted); font-size:12px; }
.card-header { display:flex; align-items:center; justify-content:space-between; }
.result-grid { display:grid; grid-template-columns:1fr 180px; gap:20px; }
.result-title { font-size:18px; font-weight:700; color:var(--sau-ink); }
.result-meta,.result-description { margin-top:10px; color:var(--sau-ink-soft); line-height:1.6; }
.cover { width:180px; height:120px; border-radius:8px; object-fit:cover; background:var(--sau-paper-muted); }
.format-row { display:flex; gap:12px; align-items:center; margin-top:20px; }
.task-message { margin:12px 0; color:var(--sau-ink-soft); }
.task-actions { display:flex; align-items:center; gap:10px; }
.service-note code { color:var(--sau-ink-soft); font-size:12px; overflow-wrap:anywhere; }
@media (max-width: 700px) { .inspect-row,.format-row { flex-direction:column; align-items:stretch; } .result-grid { grid-template-columns:1fr; } }
</style>
