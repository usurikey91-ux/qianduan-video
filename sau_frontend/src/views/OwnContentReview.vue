<template>
  <div class="own-content-review">
    <div class="page-header">
      <div>
        <h1>作品复盘</h1>
        <p>只读取官方或平台连接器实际返回的数据，用中位数、最高值和作品对比做事实复盘。</p>
        <ProjectReferences context="review" />
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
        <div class="source-status-actions">
          <el-tag :type="currentSource.status === 'connected' ? 'success' : 'info'" effect="plain">
            {{ currentSource.status === 'connected' ? '已连接' : currentSource.status === 'sync_available' ? '可直接同步' : '文件导入模式' }}
          </el-tag>
          <el-button size="small" plain @click="router.push('/platform-connections')">管理账号连接</el-button>
        </div>
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

    <el-card v-if="activePlatform === 'douyin' && accountOverview" shadow="never" class="account-overview-card douyin-private-card">
      <template #header>
        <div class="card-header">
          <div>
            <strong>抖音自然视频流量</strong>
            <div class="muted">已登录创作者账号 · 近7天 · 不含 DOU+、同城、好友与站外流量 · 更新于 {{ accountOverview.captured_at || '-' }}</div>
          </div>
          <el-tag type="success" effect="plain">仅自己的账号可见</el-tag>
        </div>
      </template>
      <div class="private-data-layout">
        <section class="private-data-section">
          <div class="private-section-heading">
            <div>
              <strong>自然流量入口</strong>
              <small>平台当前实际返回的推荐、搜索、关注与主页数据</small>
            </div>
          </div>
          <div v-if="visibleTrafficSources.length" class="private-metric-grid">
            <div v-for="item in visibleTrafficSources" :key="item.key || item.label" class="private-metric">
              <span>{{ item.label }}</span>
              <strong>{{ formatMetric(item.value) }}</strong>
              <div v-if="metricTrendValues(item).length" class="trend-bars compact" :title="metricTrendValues(item).join(' → ')">
                <i v-for="(value, index) in metricTrendValues(item)" :key="index" :style="{ height: `${trendHeight(metricTrendValues(item), value)}%` }" />
              </div>
            </div>
          </div>
          <el-alert v-else title="本次同步未返回账号流量入口数据" type="info" :closable="false" show-icon />
        </section>

        <section class="private-data-section">
          <div class="private-section-heading">
            <div>
              <strong>账号与粉丝变化</strong>
              <small>用于辅助判断视频带来的访问、回访和涨粉</small>
            </div>
          </div>
          <div v-if="accountOverview.fan_metrics?.length" class="private-metric-grid">
            <div v-for="item in accountOverview.fan_metrics" :key="item.key || item.label" class="private-metric">
              <span>{{ item.label }}</span>
              <strong>{{ formatMetric(item.value) }}</strong>
              <div v-if="metricTrendValues(item).length" class="trend-bars compact" :title="metricTrendValues(item).join(' → ')">
                <i v-for="(value, index) in metricTrendValues(item)" :key="index" :style="{ height: `${trendHeight(metricTrendValues(item), value)}%` }" />
              </div>
            </div>
          </div>
        </section>

        <section class="private-data-section portrait-section">
          <div class="private-section-heading">
            <div>
              <strong>自然流量用户画像</strong>
              <small>性别、年龄、地域等仅在平台实际开放时展示</small>
            </div>
          </div>
          <div v-if="accountOverview.audience_profile?.length" class="private-metric-grid">
            <div v-for="item in accountOverview.audience_profile" :key="item.label" class="private-metric">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <el-alert v-else :title="accountOverview.audience_profile_note || '抖音本次未返回用户画像'" type="info" :closable="false" show-icon />
        </section>
      </div>
    </el-card>

    <el-card v-if="activePlatform === 'xiaohongshu' && accountOverview" shadow="never" class="account-overview-card">
      <template #header>
        <div class="card-header">
          <div>
            <strong>小红书账号官方概览</strong>
            <div v-if="accountOverview.account_name" class="current-account">当前账号：{{ accountOverview.account_name }}</div>
            <div class="muted">近30天创作者中心数据 · 更新于 {{ accountOverview.captured_at || '-' }}</div>
          </div>
        </div>
      </template>
      <div v-if="accountOverview.stats?.length" class="account-stats-grid">
        <div v-for="stat in accountOverview.stats" :key="stat.label" class="account-stat">
          <span>{{ stat.label }}</span>
          <strong>{{ formatMetric(stat.total) }}</strong>
          <div v-if="stat.trend?.length" class="trend-bars" :title="stat.trend.join(' → ')">
            <i v-for="(value, index) in stat.trend" :key="index" :style="{ height: `${trendHeight(stat.trend, value)}%` }" />
          </div>
          <small v-else>平台未返回趋势</small>
        </div>
      </div>
    </el-card>

    <el-card v-if="works.length" shadow="never" class="fact-review-card">
      <template #header>
        <div class="card-header">
          <div>
            <strong>事实复盘概览</strong>
            <div class="muted">按当前 {{ works.length }} 条作品即时计算，不调用 AI，不推测平台未返回的数据。</div>
          </div>
        </div>
      </template>
      <div class="fact-grid">
        <el-statistic title="作品数量" :value="works.length" />
        <template v-if="activePlatform === 'douyin'">
          <el-statistic title="中位曝光" :value="reviewOverview.exposureMedian ?? '-'" group-separator="," />
          <el-statistic title="中位播放" :value="reviewOverview.playMedian" group-separator="," />
          <el-statistic title="中位5秒完播率" :value="reviewOverview.fiveSecMedian === null ? '-' : reviewOverview.fiveSecMedian * 100" :precision="reviewOverview.fiveSecMedian === null ? 0 : 1" :suffix="reviewOverview.fiveSecMedian === null ? '' : '%'" />
        </template>
        <template v-else>
          <el-statistic :title="`中位${reviewOverview.primaryLabel}`" :value="reviewOverview.primaryMedian" group-separator="," />
          <el-statistic :title="`最高${reviewOverview.primaryLabel}`" :value="reviewOverview.primaryMaximum" group-separator="," />
          <el-statistic title="中位互动数" :value="reviewOverview.interactionMedian" group-separator="," />
        </template>
      </div>
    </el-card>

    <el-card shadow="never" class="works-card">
      <template #header>
        <div class="card-header">
          <div>
            <span>{{ activePlatform === 'douyin' ? '抖音作品数据' : '小红书作品数据' }}</span>
            <div v-if="activePlatform === 'xiaohongshu' && accountOverview?.account_name" class="muted">当前账号：{{ accountOverview.account_name }}</div>
          </div>
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
        <el-table-column v-if="activePlatform === 'douyin' && showMetric('exposure_count')" prop="exposure_count" label="曝光" width="95" sortable />
        <el-table-column v-if="showMetric('play_count')" prop="play_count" label="播放" width="95" sortable />
        <el-table-column v-if="activePlatform === 'douyin' && showMetric('cover_click_rate')" label="封面点击" width="110" sortable prop="cover_click_rate"><template #default="scope">{{ formatPercent(scope.row.cover_click_rate) }}</template></el-table-column>
        <el-table-column v-if="activePlatform === 'douyin' && showMetric('two_sec_bounce_rate')" label="2秒跳出" width="105" sortable prop="two_sec_bounce_rate"><template #default="scope">{{ formatPercent(scope.row.two_sec_bounce_rate) }}</template></el-table-column>
        <el-table-column v-if="activePlatform === 'douyin' && showMetric('five_sec_completion_rate')" label="5秒完播" width="105" sortable prop="five_sec_completion_rate"><template #default="scope">{{ formatPercent(scope.row.five_sec_completion_rate) }}</template></el-table-column>
        <el-table-column v-if="activePlatform === 'douyin' && showMetric('completion_rate')" label="完播率" width="105" sortable prop="completion_rate"><template #default="scope">{{ formatPercent(scope.row.completion_rate) }}</template></el-table-column>
        <el-table-column v-if="activePlatform === 'douyin' && showMetric('avg_play_duration')" label="平均播放" width="110" sortable prop="avg_play_duration"><template #default="scope">{{ formatMetric(scope.row.avg_play_duration, 'seconds') }}</template></el-table-column>
        <el-table-column v-if="showMetric('follower_delta')" label="涨粉" width="90" sortable prop="follower_delta" />
        <el-table-column v-if="showMetric('like_count')" prop="like_count" label="点赞" width="90" sortable />
        <el-table-column v-if="showMetric('collect_count')" prop="collect_count" label="收藏" width="90" sortable />
        <el-table-column v-if="showMetric('comment_count')" prop="comment_count" label="评论" width="90" sortable />
        <el-table-column v-if="showMetric('share_count')" prop="share_count" label="分享" width="90" sortable />
        <el-table-column label="数据时间" width="170"><template #default="scope">{{ scope.row.updated_at || scope.row.created_at || '-' }}</template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="scope"><el-button size="small" link type="primary" @click="openDetails(scope.row)">查看详情</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!loadingWorks && works.length === 0" :description="`暂无${activePlatform === 'douyin' ? '抖音' : '小红书'}作品数据`" />
    </el-card>

    <el-dialog v-model="detailVisible" :title="activePlatform === 'douyin' ? '抖音作品详情' : '小红书笔记详情'" width="760px">
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
        <div v-if="visibleOfficialSections.length" class="official-sections">
          <div class="official-heading">
            <strong>{{ activePlatform === 'douyin' ? '抖音后台专属数据' : '平台官方扩展数据' }}</strong>
            <span>仅展示本次同步实际返回的字段</span>
          </div>
          <section v-for="section in visibleOfficialSections" :key="section.label" class="official-section">
            <h4>{{ section.label }}</h4>
            <div class="official-grid">
              <div v-for="item in section.items" :key="item.label" class="official-item">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </section>
        </div>
        <el-alert v-else :title="activePlatform === 'douyin' ? '本条作品暂未返回流量来源或观众构成等扩展指标' : '本条笔记的观看来源或观众画像仍在平台统计中'" type="info" :closable="false" show-icon />
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
import { useRoute, useRouter } from 'vue-router'
import { ownContentApi } from '@/api/ownContent'
import ProjectReferences from '@/components/ProjectReferences.vue'

const route = useRoute()
const router = useRouter()
const requestedPlatform = ['douyin', 'xiaohongshu'].includes(String(route.query.platform))
  ? String(route.query.platform)
  : 'douyin'
const activePlatform = ref(requestedPlatform)
const accountName = ref(requestedPlatform === 'douyin' ? '抖音创作者中心' : '我的小红书账号')
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
const accountOverview = ref(null)
const currentSource = computed(() => sources.value[activePlatform.value])
const canImport = computed(() => Boolean(selectedFile.value && previewData.value?.valid_count > 0))
const ignoredTrafficLabels = ['DOU+', '抖加', '同城', '好友', '站外']
const visibleTrafficSources = computed(() => (accountOverview.value?.traffic_sources || []).filter((item) => {
  const label = String(item.label || '')
  return label !== '作品分享' && !ignoredTrafficLabels.some((ignored) => label.toLowerCase().includes(ignored.toLowerCase()))
}))
const visibleOfficialSections = computed(() => {
  const sections = detailWork.value?.official_metric_sections || []
  if (activePlatform.value !== 'douyin') return sections
  return sections.map((section) => ({
    ...section,
    items: (section.items || []).filter((item) => !ignoredTrafficLabels.some((label) => String(item.label || '').toLowerCase().includes(label.toLowerCase())))
  })).filter((section) => section.items.length)
})

const numberValue = (value) => {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
}
const medianValue = (values) => {
  const sorted = values.filter((value) => value !== null).sort((a, b) => a - b)
  if (!sorted.length) return 0
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2)
}
const medianFor = (key) => {
  const values = works.value.map((item) => numberValue(item[key])).filter((value) => value !== null)
  return values.length ? medianValue(values) : null
}
const reviewOverview = computed(() => {
  const hasPlay = works.value.some((item) => numberValue(item.play_count) !== null)
  const primaryKey = hasPlay ? 'play_count' : 'like_count'
  const primaryLabel = hasPlay ? '播放' : '点赞'
  const primaryValues = works.value.map((item) => numberValue(item[primaryKey]))
  const interactions = works.value.map((item) => {
    const values = ['like_count', 'collect_count', 'comment_count', 'share_count']
      .map((key) => numberValue(item[key]))
      .filter((value) => value !== null)
    return values.length ? values.reduce((sum, value) => sum + value, 0) : null
  })
  return {
    primaryLabel,
    primaryMedian: medianValue(primaryValues),
    primaryMaximum: Math.max(0, ...primaryValues.filter((value) => value !== null)),
    interactionMedian: medianValue(interactions),
    exposureMedian: medianFor('exposure_count'),
    playMedian: medianFor('play_count') ?? 0,
    fiveSecMedian: medianFor('five_sec_completion_rate')
  }
})

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
    await fetchAccountOverview()
  } finally { loadingWorks.value = false }
}

const fetchAccountOverview = async () => {
  try {
    const api = activePlatform.value === 'douyin'
      ? ownContentApi.getDouyinOverview
      : ownContentApi.getXiaohongshuOverview
    const response = await api()
    accountOverview.value = response.data || null
  } catch (error) {
    accountOverview.value = null
    console.warn('读取小红书账号概览失败', error)
  }
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
    const warningCount = response.data?.warnings?.length || 0
    const message = `同步完成：新增 ${response.data?.inserted || 0} 条，更新 ${response.data?.updated || 0} 条`
    if (warningCount) ElMessage.warning(`${message}；${response.data.warnings.join('；')}`)
    else ElMessage.success(message)
    await fetchWorks()
  } finally { syncing.value = false }
}

const loadSources = async () => {
  try { const response = await ownContentApi.getReviewSources(); sources.value = response.data || {} } catch (error) { console.warn('读取复盘数据源状态失败', error) }
}
const sourceMetricLabels = {
  exposure_count: '曝光', play_count: '播放', cover_click_rate: '封面点击率',
  avg_play_duration: '平均播放时长', like_count: '点赞', collect_count: '收藏',
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
  { key: 'exposure_count', label: '曝光', kind: 'number' },
  { key: 'play_count', label: '播放', kind: 'number' },
  { key: 'cover_click_rate', label: '封面点击率', kind: 'percent' },
  { key: 'two_sec_bounce_rate', label: '2秒跳出率', kind: 'percent' },
  { key: 'five_sec_completion_rate', label: '5秒完播率', kind: 'percent' },
  { key: 'completion_rate', label: '完播率', kind: 'percent' },
  { key: 'avg_play_duration', label: '平均播放时长', kind: 'seconds' },
  { key: 'follower_delta', label: '涨粉', kind: 'number' },
  { key: 'like_count', label: '点赞（辅助）', kind: 'number' },
  { key: 'collect_count', label: '收藏（辅助）', kind: 'number' },
  { key: 'comment_count', label: '评论（辅助）', kind: 'number' },
  { key: 'share_count', label: '分享（辅助）', kind: 'number' },
]
const compareRows = detailMetrics
const formatMetric = (value, kind = 'number') => {
  if (value === null || value === undefined || value === '') return '-'
  if (kind === 'percent') return formatPercent(value)
  if (kind === 'seconds') return `${Number(value).toFixed(1)} 秒`
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value)
}
const trendHeight = (values, value) => {
  const maximum = Math.max(0, ...values.map((item) => Number(item) || 0))
  if (!maximum) return 4
  return Math.max(4, Math.round(((Number(value) || 0) / maximum) * 100))
}
const metricTrendValues = (item) => (item?.trend || [])
  .map((point) => numberValue(point?.value ?? point?.count))
  .filter((value) => value !== null)
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
  .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid var(--sau-line); }
  .page-actions { display: flex; gap: 10px; }
  .page-header h1 { margin: 0 0 6px; font-size: 28px; font-weight: 650; color: var(--sau-ink); letter-spacing: -0.02em; }
  .page-header p { margin: 0; color: var(--sau-ink-soft); font-size: 14px; }
  .platform-card, .account-overview-card, .fact-review-card, .works-card { margin-bottom: 18px; }
  .source-status { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--sau-paper-muted); border: 1px solid var(--sau-line); border-radius: 8px; }
  .source-status-actions { display: flex; align-items: center; gap: 10px; }
  .source-connector { margin-left: 12px; color: var(--sau-ink-soft); font-size: 12px; }
  .source-note { margin: 9px 0 14px; color: var(--sau-ink-soft); font-size: 13px; }
  .source-fields { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 0 0 14px; }
  .source-fields-label { margin-right: 4px; color: var(--sau-ink-soft); font-size: 13px; }
  .import-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
  .account-input { width: 180px; }
  .file-name, .muted { color: var(--sau-ink-soft); font-size: 13px; }
  .result-alert, .preview-block { margin-top: 16px; }
  .preview-summary { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }
  .fact-grid { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; }
  .card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .card-header-actions { display: flex; align-items: center; gap: 12px; }
  .detail-title { font-size: 20px; font-weight: 650; color: var(--sau-ink); margin-bottom: 8px; }
  .detail-meta, .compare-note { color: var(--sau-ink-soft); font-size: 13px; margin-bottom: 12px; }
  .metric-grid { display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)); gap: 10px; margin: 18px 0; }
  .metric-item { border: 1px solid var(--sau-line); border-radius: 8px; padding: 13px; background: var(--sau-paper-muted); }
  .metric-item span { display: block; color: var(--sau-ink-soft); font-size: 12px; margin-bottom: 6px; }
  .metric-item strong { color: var(--sau-ink); font-size: 18px; }
  .official-sections { margin: 4px 0 18px; padding-top: 16px; border-top: 1px solid var(--sau-line); }
  .official-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
  .official-heading span { color: var(--sau-muted); font-size: 12px; }
  .official-section h4 { margin: 16px 0 10px; color: var(--sau-ink); font-size: 14px; }
  .official-grid { display: grid; grid-template-columns: repeat(3, minmax(140px, 1fr)); gap: 10px; }
  .official-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid var(--sau-line); border-radius: 8px; background: var(--sau-paper); }
  .official-item span { color: var(--sau-ink-soft); font-size: 13px; }
  .official-item strong { color: var(--sau-ink); font-size: 15px; }
  .current-account { margin-top: 5px; color: var(--sau-ink); font-size: 14px; font-weight: 600; }
  .private-data-layout { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
  .private-data-section { min-width: 0; padding: 16px; border: 1px solid var(--sau-line); border-radius: 8px; background: var(--sau-paper); }
  .portrait-section { grid-column: 1 / -1; }
  .private-section-heading { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 13px; }
  .private-section-heading strong { display: block; color: var(--sau-ink); font-size: 15px; }
  .private-section-heading small { display: block; margin-top: 4px; color: var(--sau-ink-soft); font-size: 12px; }
  .private-metric-grid { display: grid; grid-template-columns: repeat(3, minmax(110px, 1fr)); gap: 9px; }
  .private-metric { min-width: 0; padding: 11px 12px; border-radius: 8px; background: var(--sau-paper-muted); }
  .private-metric span { display: block; overflow: hidden; color: var(--sau-ink-soft); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
  .private-metric strong { display: block; margin-top: 5px; color: var(--sau-ink); font-size: 19px; }
  .trend-bars.compact { height: 22px; margin-top: 8px; }
  .profile-fact { min-width: 120px; padding: 10px 12px; border: 1px solid var(--sau-line); border-radius: 8px; background: var(--sau-paper-muted); }
  .profile-fact span { display: block; margin-bottom: 5px; color: var(--sau-muted); font-size: 12px; }
  .profile-fact strong { color: var(--sau-ink); font-size: 14px; white-space: pre-line; }
  .account-stats-grid { display: grid; grid-template-columns: repeat(3, minmax(170px, 1fr)); gap: 12px; }
  .account-stat { padding: 13px 14px; border: 1px solid var(--sau-line); border-radius: 8px; background: var(--sau-paper); }
  .account-stat > span { display: block; color: var(--sau-ink-soft); font-size: 13px; }
  .account-stat > strong { display: block; margin: 5px 0 9px; color: var(--sau-ink); font-size: 21px; }
  .account-stat small { color: var(--sau-muted); }
  .trend-bars { display: flex; align-items: flex-end; gap: 2px; height: 34px; }
  .trend-bars i { flex: 1; min-width: 2px; border-radius: 2px 2px 0 0; background: var(--sau-cinnabar); opacity: .72; }
  @media (max-width: 760px) { .page-header, .card-header, .card-header-actions, .official-heading { align-items: flex-start; flex-direction: column; gap: 12px; } .fact-grid, .metric-grid, .official-grid, .account-stats-grid, .private-data-layout, .private-metric-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); } .private-data-section, .portrait-section { grid-column: 1 / -1; } }
}
</style>
