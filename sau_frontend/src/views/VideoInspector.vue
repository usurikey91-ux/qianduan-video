<template>
  <div class="video-inspector">
    <div class="page-header">
      <div>
        <h1>视频解析</h1>
        <p>调用已配置的视频解析服务处理公开分享链接，下载后直接进入太阳鸟素材库。</p>
      </div>
      <el-tag :type="serviceAvailable ? 'success' : 'warning'" effect="plain">
        {{ serviceAvailable ? '解析服务在线' : '解析服务未连接' }}
      </el-tag>
    </div>

    <el-card shadow="never" class="inspect-card">
      <div class="inspect-row">
        <el-input v-model="url" clearable placeholder="粘贴抖音或其他平台分享链接" @keyup.enter="inspect" />
        <el-button type="primary" :loading="inspecting" @click="inspect">解析链接</el-button>
      </div>
      <div class="service-note">服务地址：{{ serviceBaseUrl || '未配置（请通过 VIDEO_JIEXI_BASE_URL 或运行时设置配置）' }}</div>
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
        <el-button type="primary" :loading="downloading" @click="download">下载视频并导入素材库</el-button>
      </div>
      <el-empty v-else description="当前版本先处理单条视频；图文或混合轮播取决于已配置的解析服务" :image-size="60" />
    </el-card>

    <el-card v-if="task" shadow="never" class="task-card">
      <template #header><div class="card-header"><span>下载任务</span><el-tag :type="task.state === 'completed' ? 'success' : task.state === 'error' ? 'danger' : 'warning'">{{ taskStateText }}</el-tag></div></template>
      <el-progress :percentage="Math.round(Number(task.progress) || 0)" :status="task.state === 'error' ? 'exception' : task.state === 'completed' ? 'success' : undefined" />
      <div class="task-message">{{ task.error || task.filename || '正在下载…' }}</div>
      <el-button v-if="task.state === 'completed' && !imported" type="success" @click="importMaterial">导入太阳鸟素材库</el-button>
      <el-tag v-if="imported" type="success">已导入素材库</el-tag>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { videoJiexiApi } from '@/api/videoJiexi'

const url = ref('')
const info = ref(null)
const formatId = ref('')
const task = ref(null)
const taskId = ref('')
const inspecting = ref(false)
const downloading = ref(false)
const imported = ref(false)
const route = useRoute()
const serviceAvailable = ref(false)
const serviceBaseUrl = ref('')
let pollTimer

const taskStateText = computed(() => ({ queued: '排队中', downloading: '下载中', processing: '处理中', completed: '已完成', error: '失败', cancelled: '已取消' }[task.value?.state] || task.value?.state || '未知'))

async function checkStatus() {
  const response = await videoJiexiApi.status()
  serviceAvailable.value = Boolean(response.data?.health?.ok)
  serviceBaseUrl.value = response.data?.base_url || ''
}

async function inspect() {
  if (!url.value.trim()) return ElMessage.warning('请先粘贴视频链接')
  inspecting.value = true
  try {
    const response = await videoJiexiApi.inspect(url.value.trim())
    info.value = response.data
    formatId.value = response.data?.formats?.[0]?.id ? String(response.data.formats[0].id) : ''
    task.value = null
    imported.value = false
    ElMessage.success('解析完成')
  } finally { inspecting.value = false }
}

async function download() {
  if (!info.value?.inspectionId) return ElMessage.warning('请先解析链接')
  downloading.value = true
  try {
    const response = await videoJiexiApi.download(info.value.inspectionId, formatId.value)
    task.value = response.data
    taskId.value = response.data?.id || ''
    imported.value = false
    startPolling()
  } finally { downloading.value = false }
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
    } catch { clearInterval(pollTimer) }
  }, 2000)
}

async function importMaterial() {
  const response = await videoJiexiApi.importMaterial(taskId.value)
  imported.value = true
  ElMessage.success(response.msg || '已导入素材库')
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
.video-inspector { display: grid; gap: 18px; }
.page-header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.page-header h1 { margin:0; color:#111827; font-size:28px; }
.page-header p { margin:8px 0 0; color:#6b7280; }
.inspect-row { display:flex; gap:12px; }
.inspect-row .el-input { flex:1; }
.service-note { margin-top:10px; color:#9ca3af; font-size:12px; }
.card-header { display:flex; align-items:center; justify-content:space-between; }
.result-grid { display:grid; grid-template-columns:1fr 180px; gap:20px; }
.result-title { font-size:18px; font-weight:700; color:#111827; }
.result-meta,.result-description { margin-top:10px; color:#6b7280; line-height:1.6; }
.cover { width:180px; height:120px; border-radius:10px; object-fit:cover; background:#f3f4f6; }
.format-row { display:flex; gap:12px; align-items:center; margin-top:20px; }
.task-message { margin:12px 0; color:#6b7280; }
@media (max-width: 700px) { .inspect-row,.format-row { flex-direction:column; align-items:stretch; } .result-grid { grid-template-columns:1fr; } }
</style>
