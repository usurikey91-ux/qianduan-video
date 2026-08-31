<template>
  <div class="own-content-review">
    <div class="page-header">
      <div>
        <h1>作品复盘</h1>
        <p>只读取官方或平台连接器实际返回的数据；表现不好的作品直接忽略。</p>
      </div>
        <div class="page-actions">
          <el-button type="primary" :loading="syncing" @click="syncWorks">同步平台数据</el-button>
          <el-button :loading="loadingWorks" @click="fetchWorks">刷新数据</el-button>
        </div>
    </div>

    <el-card shadow="never" class="platform-card">
      <el-tabs v-model="activePlatform" @tab-change="handlePlatformChange">
        <el-tab-pane label="抖音作品复盘" name="douyin" />
        <el-tab-pane label="小红书作品复盘" name="xiaohongshu" />
      </el-tabs>

      <div class="source-status" v-if="currentSource">
        <div>
          <strong>{{ currentSource.label }}</strong>
          <span class="source-connector">数据源：{{ currentSource.connector }}</span>
        </div>
        <el-tag :type="currentSource.status === 'connected' ? 'success' : 'info'" effect="plain">
          {{ currentSource.status === 'connected' ? '已连接' : currentSource.status === 'sync_available' ? '可直接同步' : '文件导入模式' }}
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
          <div class="card-header-actions">
            <span class="muted">共 {{ works.length }} 条 · 仅展示实际返回字段</span>
            <el-button v-if="activePlatform === 'douyin'" size="small" type="primary" plain :disabled="selectedWorks.length < 2" @click="compareSelected">对比所选作品</el-button>
          </div>
        </div>
      </template>

      <el-table :data="works" v-loading="loadingWorks" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column v-if="activePlatform === 'douyin'" type="selection" width="48" />
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
        <el-table-column v-if="activePlatform === 'douyin'" label="操作" width="90" fixed="right"><template #default="scope"><el-button size="small" link type="primary" @click="openDetails(scope.row)">查看详情</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!loadingWorks && works.length === 0" :description="`暂无${activePlatform === 'douyin' ? '抖音' : '小红书'}作品数据`" />
    </el-card>

    <el-dialog v-model="detailVisible" title="抖音作品详情" width="760px">
      <template v-if="detailWork">
        <div class="detail-title">{{ detailWork.title || '未命名作品' }}</div>
        <div class="detail-meta">发布时间：{{ detailWork.published_at || '-' }} · 数据时间：{{ detailWork.updated_at || detailWork.created_at || '-' }}</div>
        <el-link v-if="detailWork.video_url" :href="detailWork.video_url" target="_blank" type="primary">打开作品链接</el-link>
        <div class="metric-grid">
          <div v-for="metric in detailMetrics" :key="metric.key" class="metric-item">
            <span>{{ metric.label }}</span>
            <strong>{{ formatMetric(detailWork[metric.key], metric.kind) }}</strong>
          </div>
        </div>
        <el-alert v-if="detailWork.notes" title="采集备注" :description="detailWork.notes" type="info" :closable="false" />
      </template>
    </el-dialog>

    <el-dialog v-model="compareVisible" title="抖音作品对比" width="980px">
      <div class="compare-note">仅比较连接器实际返回的字段；空值表示平台没有返回该指标。</div>
      <el-table :data="compareRows" size="small" border>
        <el-table-column prop="label" label="指标" width="150" fixed="left" />
        <el-table-column v-for="work in selectedWorks" :key="work.id" :label="shortTitle(work.title)" min-width="180">
          <template #default="scope">{{ formatMetric(work[scope.row.key], scope.row.kind) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
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
const syncing = ref(false)
const loadingWorks = ref(false)
const works = ref([])
const selectedWorks = ref([])
const detailVisible = ref(false)
const detailWork = ref(null)
const compareVisible = ref(false)
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

const handlePlatformChange = async () => {
  selectedFile.value = null
  previewData.value = null
  importResult.value = null
  selectedWorks.value = []
  accountName.value = activePlatform.value === 'douyin' ? '抖音创作者中心' : '我的小红书账号'
  await fetchWorks()
}

const syncWorks = async () => {
  syncing.value = true
  try {
    const isDouyin = activePlatform.value === 'douyin'
    const defaultName = isDouyin ? '抖音创作者中心' : '我的小红书账号'
    const api = isDouyin ? ownContentApi.syncDouyin : ownContentApi.syncXiaohongshu
    const response = await api(accountName.value.trim() || defaultName, 20)
    importResult.value = response.data
    ElMessage.success(`同步完成：新增 ${response.data?.inserted || 0} 条，更新 ${response.data?.updated || 0} 条`)
    await fetchWorks()
  } finally { syncing.value = false }
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
const detailMetrics = [
  { key: 'play_count', label: '播放', kind: 'number' },
  { key: 'like_count', label: '点赞', kind: 'number' },
  { key: 'collect_count', label: '收藏', kind: 'number' },
  { key: 'comment_count', label: '评论', kind: 'number' },
  { key: 'share_count', label: '分享', kind: 'number' },
  { key: 'completion_rate', label: '完播率', kind: 'percent' },
  { key: 'five_sec_completion_rate', label: '5秒完播率', kind: 'percent' },
  { key: 'two_sec_bounce_rate', label: '2秒跳出率', kind: 'percent' },
  { key: 'avg_play_duration', label: '平均播放时长', kind: 'seconds' },
  { key: 'follower_delta', label: '涨粉', kind: 'number' },
]
const compareRows = detailMetrics
const formatMetric = (value, kind = 'number') => {
  if (value === null || value === undefined || value === '') return '-'
  if (kind === 'percent') return formatPercent(value)
  if (kind === 'seconds') return `${Number(value).toFixed(1)} 秒`
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value)
}
const shortTitle = (title) => {
  const text = String(title || '未命名作品')
  return text.length > 20 ? `${text.slice(0, 20)}…` : text
}
const handleSelectionChange = (rows) => { selectedWorks.value = rows }
const openDetails = (row) => { detailWork.value = row; detailVisible.value = true }
const compareSelected = () => {
  if (selectedWorks.value.length < 2) return ElMessage.warning('请至少选择 2 条抖音作品')
  if (selectedWorks.value.length > 20) return ElMessage.warning('最多比较 20 条作品')
  compareVisible.value = true
}

onMounted(async () => { await loadSources(); await fetchWorks() })
</script>

<style lang="scss" scoped>
.own-content-review {
  .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
  .page-actions { display: flex; gap: 10px; }
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
  .card-header-actions { display: flex; align-items: center; gap: 12px; }
  .detail-title { font-size: 18px; font-weight: 600; color: #1f2937; margin-bottom: 8px; }
  .detail-meta, .compare-note { color: #6b7280; font-size: 13px; margin-bottom: 12px; }
  .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)); gap: 10px; margin: 18px 0; }
  .metric-item { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; background: #f8fafc; }
  .metric-item span { display: block; color: #6b7280; font-size: 12px; margin-bottom: 6px; }
  .metric-item strong { color: #111827; font-size: 18px; }
  @media (max-width: 760px) { .card-header, .card-header-actions { align-items: flex-start; flex-direction: column; } .metric-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); } }
}
</style>
