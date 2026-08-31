<template>
  <div class="own-content-review">
    <div class="page-header">
      <div>
        <h1>作品复盘</h1>
        <p>只读取官方或平台连接器实际返回的数据；表现不好的作品直接忽略。</p>
      </div>
      <el-button :loading="loadingWorks" @click="fetchWorks">刷新数据</el-button>
    </div>

    <el-card shadow="never" class="platform-card">
      <el-tabs v-model="activePlatform" @tab-change="fetchWorks">
        <el-tab-pane label="抖音作品复盘" name="douyin" />
        <el-tab-pane label="小红书作品复盘" name="xiaohongshu" />
      </el-tabs>

      <div class="source-status" v-if="currentSource">
        <div>
          <strong>{{ currentSource.label }}</strong>
          <span class="source-connector">数据源：{{ currentSource.connector }}</span>
        </div>
        <el-tag :type="currentSource.status === 'connected' ? 'success' : 'info'" effect="plain">
          {{ currentSource.status === 'connected' ? '已连接' : '文件导入模式' }}
        </el-tag>
      </div>
      <p v-if="currentSource?.note" class="source-note">{{ currentSource.note }}</p>
      <div v-if="currentSource?.supports?.length" class="source-fields">
        <span class="source-fields-label">可识别字段</span>
        <el-tag v-for="field in currentSource.supports" :key="field" size="small" effect="plain">{{ field }}</el-tag>
      </div>

      <div class="import-row">
        <el-input v-model="accountName" class="account-input" :placeholder="activePlatform === 'douyin' ? '抖音账号名称' : '小红书账号名称'" />
        <el-upload action="#" :auto-upload="false" :show-file-list="false" accept=".xlsx,.csv" :on-change="handleFileChange">
          <el-button>选择官方数据文件</el-button>
        </el-upload>
        <div class="file-name">{{ selectedFile?.name || '未选择文件' }}</div>
        <el-button type="primary" :disabled="!selectedFile" :loading="previewLoading" @click="previewImport">预览</el-button>
        <el-button type="success" :disabled="!canImport" :loading="importing" @click="confirmImport">确认导入</el-button>
      </div>

      <el-alert v-if="importResult" :title="`导入完成：新增 ${importResult.inserted} 条，更新 ${importResult.updated} 条`" type="success" show-icon :closable="false" class="result-alert" />

      <div v-if="previewData" class="preview-block">
        <div class="preview-summary">
          <el-statistic title="原始行数" :value="previewData.raw_count" />
          <el-statistic title="有效作品" :value="previewData.valid_count" />
          <el-statistic title="识别字段" :value="Object.keys(previewData.field_map || {}).length" />
        </div>
        <el-table :data="previewData.preview_rows" size="small" style="width: 100%">
          <el-table-column prop="title" label="作品/笔记" min-width="280" show-overflow-tooltip />
          <el-table-column prop="published_at" label="发布时间" width="180" />
          <el-table-column prop="play_count" label="播放" width="90" />
          <el-table-column prop="like_count" label="点赞" width="90" />
          <el-table-column prop="collect_count" label="收藏" width="90" />
          <el-table-column prop="comment_count" label="评论" width="90" />
          <el-table-column prop="share_count" label="分享" width="90" />
        </el-table>
      </div>
    </el-card>

    <el-card shadow="never" class="works-card">
      <template #header>
        <div class="card-header">
          <span>{{ activePlatform === 'douyin' ? '抖音作品数据' : '小红书作品数据' }}</span>
          <span class="muted">共 {{ works.length }} 条 · 仅展示实际返回字段</span>
        </div>
      </template>

      <el-table :data="works" v-loading="loadingWorks" style="width: 100%">
        <el-table-column prop="title" label="作品/笔记" min-width="300" show-overflow-tooltip />
        <el-table-column prop="published_at" label="发布时间" width="180" />
        <el-table-column v-if="showMetric('play_count')" prop="play_count" label="播放" width="95" sortable />
        <el-table-column v-if="showMetric('like_count')" prop="like_count" label="点赞" width="90" sortable />
        <el-table-column v-if="showMetric('collect_count')" prop="collect_count" label="收藏" width="90" sortable />
        <el-table-column v-if="showMetric('comment_count')" prop="comment_count" label="评论" width="90" sortable />
        <el-table-column v-if="showMetric('share_count')" prop="share_count" label="分享" width="90" sortable />
        <el-table-column v-if="showMetric('completion_rate')" label="完播率" width="105" sortable prop="completion_rate"><template #default="scope">{{ formatPercent(scope.row.completion_rate) }}</template></el-table-column>
        <el-table-column v-if="showMetric('five_sec_completion_rate')" label="5秒完播" width="105" sortable prop="five_sec_completion_rate"><template #default="scope">{{ formatPercent(scope.row.five_sec_completion_rate) }}</template></el-table-column>
        <el-table-column v-if="showMetric('two_sec_bounce_rate')" label="2秒跳出" width="105" sortable prop="two_sec_bounce_rate"><template #default="scope">{{ formatPercent(scope.row.two_sec_bounce_rate) }}</template></el-table-column>
        <el-table-column v-if="showMetric('follower_delta')" label="涨粉" width="90" sortable prop="follower_delta" />
        <el-table-column label="数据时间" width="170"><template #default="scope">{{ scope.row.updated_at || scope.row.created_at || '-' }}</template></el-table-column>
      </el-table>
      <el-empty v-if="!loadingWorks && works.length === 0" :description="`暂无${activePlatform === 'douyin' ? '抖音' : '小红书'}作品数据`" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ownContentApi } from '@/api/ownContent'

const activePlatform = ref('douyin')
const accountName = ref('我的账号')
const selectedFile = ref(null)
const previewData = ref(null)
const importResult = ref(null)
const previewLoading = ref(false)
const importing = ref(false)
const loadingWorks = ref(false)
const works = ref([])
const sources = ref({})
const currentSource = computed(() => sources.value[activePlatform.value])
const canImport = computed(() => Boolean(selectedFile.value && previewData.value?.valid_count > 0))

const handleFileChange = (uploadFile) => { selectedFile.value = uploadFile.raw; previewData.value = null; importResult.value = null }

const previewImport = async () => {
  if (!selectedFile.value) return
  previewLoading.value = true
  try {
    const api = activePlatform.value === 'douyin' ? ownContentApi.previewDouyinImport : ownContentApi.previewXiaohongshuImport
    const response = await api(selectedFile.value)
    previewData.value = response.data
    importResult.value = null
    ElMessage.success('预览完成')
  } finally { previewLoading.value = false }
}

const confirmImport = async () => {
  if (!canImport.value) return
  importing.value = true
  try {
    const api = activePlatform.value === 'douyin' ? ownContentApi.importDouyinWorks : ownContentApi.importXiaohongshuWorks
    const defaultName = activePlatform.value === 'douyin' ? '我的账号' : '我的小红书账号'
    const response = await api(selectedFile.value, accountName.value.trim() || defaultName)
    importResult.value = response.data
    ElMessage.success('导入完成')
    await fetchWorks()
  } finally { importing.value = false }
}

const fetchWorks = async () => {
  loadingWorks.value = true
  try {
    const api = activePlatform.value === 'douyin' ? ownContentApi.getDouyinWorks : ownContentApi.getXiaohongshuWorks
    const response = await api(200)
    works.value = response.data || []
  } finally { loadingWorks.value = false }
}

const loadSources = async () => {
  try { const response = await ownContentApi.getReviewSources(); sources.value = response.data || {} } catch (error) { console.warn('读取复盘数据源状态失败', error) }
}
const sourceMetricLabels = {
  play_count: '播放', like_count: '点赞', collect_count: '收藏',
  comment_count: '评论', share_count: '分享', completion_rate: '完播率',
  five_sec_completion_rate: '5秒完播率', two_sec_bounce_rate: '2秒跳出率',
  follower_delta: '涨粉',
}
const showMetric = (field) => {
  const supported = currentSource.value?.supports || []
  return works.value.some((row) => row[field] !== null && row[field] !== undefined && row[field] !== '')
    || supported.includes(sourceMetricLabels[field])
}
const formatPercent = (value) => (value === null || value === undefined || value === '' ? '-' : `${(Number(value) * 100).toFixed(1)}%`)

onMounted(async () => { await loadSources(); await fetchWorks() })
</script>

<style lang="scss" scoped>
.own-content-review {
  .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
  .page-header h1 { margin: 0 0 6px; font-size: 24px; font-weight: 700; color: #1f2937; }
  .page-header p { margin: 0; color: #6b7280; font-size: 14px; }
  .platform-card, .works-card { margin-bottom: 18px; }
  .source-status { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; }
  .source-connector { margin-left: 12px; color: #6b7280; font-size: 12px; }
  .source-note { margin: 9px 0 14px; color: #6b7280; font-size: 13px; }
  .source-fields { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; }
  .source-fields-label { margin-right: 4px; color: #6b7280; font-size: 13px; }
  .import-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
  .account-input { width: 180px; }
  .file-name, .muted { color: #6b7280; font-size: 13px; }
  .result-alert, .preview-block { margin-top: 16px; }
  .preview-summary { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }
  .card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
}
</style>
