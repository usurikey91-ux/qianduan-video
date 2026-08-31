<template>
  <div class="benchmark-management">
    <div class="page-header">
      <div>
        <h1>对标内容库</h1>
        <p>账号添加一次后自动巡检，只判断作品是否达到账号自身热度阈值。</p>
      </div>
      <el-button :loading="monitorLoading" @click="refreshMonitor">刷新</el-button>
    </div>

    <el-card shadow="never" class="monitor-card">
      <template #header>
        <div class="card-header">
          <span>对标账号</span>
          <el-tag effect="plain">平台按采集器状态显示</el-tag>
        </div>
      </template>

      <div class="monitor-bind-row">
        <el-select v-model="monitorPlatform" class="platform-select" placeholder="平台">
          <el-option label="自动识别" value="auto" />
          <el-option v-for="item in platformOptions" :key="item.id" :label="item.label || item.id" :value="item.id" />
        </el-select>
        <el-input
          v-model="monitorHomepageUrl"
          clearable
          placeholder="粘贴对标账号主页链接或稳定账号 ID"
          @keyup.enter="bindMonitorAccount"
        />
        <el-button type="primary" :loading="monitorBinding" @click="bindMonitorAccount">添加对标账号</el-button>
      </div>

      <el-alert
        v-if="monitorError"
        :title="monitorError"
        type="warning"
        show-icon
        :closable="false"
        class="monitor-alert"
      />

      <el-table v-if="monitorAccounts.length" :data="monitorAccounts" size="small" class="monitor-table">
        <el-table-column label="账号" min-width="260">
          <template #default="scope">
            <div class="monitor-account-name">{{ scope.row.display_name || scope.row.handle || scope.row.external_account_id }}</div>
            <div class="monitor-account-id">{{ scope.row.platform }} · {{ scope.row.external_account_id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="采集状态" width="150">
          <template #default="scope">
            <el-tag :type="monitorStatusType(scope.row.collection_status)">{{ monitorStatusText(scope.row.collection_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_success_at" label="最近成功" width="210" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button size="small" :loading="monitorCheckingId === scope.row.id" @click="checkMonitorAccount(scope.row)">立即检查</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!monitorLoading" description="还没有添加对标账号，系统也可以保持空状态运行" :image-size="70" />
    </el-card>

    <el-card shadow="never" class="queue-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">爆款作品</div>
            <div class="card-subtitle">只看公开数据是否相对账号自身基线显著更高；不自动进行内容拆解。</div>
          </div>
          <el-tag type="danger" effect="plain">特别火</el-tag>
        </div>
      </template>

      <el-table v-if="monitorWorks.length" :data="monitorWorks" size="small">
        <el-table-column label="作品" min-width="340">
          <template #default="scope">
            <el-link v-if="scope.row.url" :href="scope.row.url" target="_blank" type="primary">{{ scope.row.title || scope.row.external_work_id }}</el-link>
            <span v-else>{{ scope.row.title || scope.row.external_work_id }}</span>
            <div class="monitor-account-id">{{ scope.row.account?.display_name || scope.row.account?.external_account_id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="热度" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.priority ? 'danger' : 'warning'">{{ scope.row.priority ? '特别火' : '火' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="相对倍数" width="110">
          <template #default="scope">{{ scope.row.relative_multiple ? `${scope.row.relative_multiple.toFixed(1)}x` : '-' }}</template>
        </el-table-column>
        <el-table-column label="公开数据" min-width="220">
          <template #default="scope">{{ formatPublicMetrics(scope.row.latest_public_metrics) }}</template>
        </el-table-column>
        <el-table-column label="作品" width="100" fixed="right">
          <template #default="scope">
            <el-link v-if="scope.row.url" :href="scope.row.url" target="_blank" type="primary">打开作品</el-link>
            <span v-else class="muted">无链接</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!monitorLoading" description="暂无达到账号自身热度阈值的作品" :image-size="70" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { benchmarkApi } from '@/api/benchmark'

const monitorHomepageUrl = ref('')
const monitorPlatform = ref('auto')
const platformOptions = ref([
  { id: 'douyin', label: '抖音' },
  { id: 'xiaohongshu', label: '小红书' },
  { id: 'bilibili', label: '哔哩哔哩' },
  { id: 'kuaishou', label: '快手' },
  { id: 'weibo', label: '微博' },
  { id: 'youtube', label: 'YouTube' },
  { id: 'tiktok', label: 'TikTok' }
])
const monitorAccounts = ref([])
const monitorWorks = ref([])
const monitorLoading = ref(false)
const monitorBinding = ref(false)
const monitorCheckingId = ref(null)
const monitorError = ref('')

const detectPlatform = (value) => {
  const text = String(value || '').toLowerCase()
  if (text.includes('douyin.com')) return 'douyin'
  if (text.includes('xiaohongshu.com') || text.includes('xhslink.com') || text.includes('xhslink.cn')) return 'xiaohongshu'
  if (text.includes('bilibili.com')) return 'bilibili'
  if (text.includes('kuaishou.com')) return 'kuaishou'
  if (text.includes('weibo.com')) return 'weibo'
  if (text.includes('youtube.com') || text.includes('youtu.be')) return 'youtube'
  if (text.includes('tiktok.com')) return 'tiktok'
  return ''
}

const monitorStatusText = (status) => {
  const map = {
    unconfigured: '未配置', ready: '待检查', checking: '检查中', ok: '正常',
    account_invalid: '账号失效', login_required: '需要登录', login_expired: '登录失效',
    missing_metric: '缺少数据字段', collection_failed: '采集失败', published_at_missing: '缺少发布时间'
  }
  return map[status] || status || '未知'
}

const monitorStatusType = (status) => {
  if (status === 'ok') return 'success'
  if (['account_invalid', 'login_required', 'login_expired', 'missing_metric', 'collection_failed', 'published_at_missing'].includes(status)) return 'danger'
  if (status === 'checking') return 'warning'
  return 'info'
}

const formatPublicMetrics = (metrics) => {
  if (!metrics || typeof metrics !== 'object') return '-'
  const labels = { like_count: '赞', favorite_count: '藏', comment_count: '评', share_count: '转', view_count: '播' }
  return Object.entries(metrics).map(([key, value]) => `${labels[key] || key} ${value}`).join(' · ') || '-'
}

const refreshMonitor = async () => {
  monitorLoading.value = true
  monitorError.value = ''
  try {
    const [accountsResponse, worksResponse] = await Promise.all([
      benchmarkApi.getOpencliMonitorAccounts(),
      benchmarkApi.getOpencliMonitorWorks()
    ])
    monitorAccounts.value = accountsResponse.data || []
    monitorWorks.value = worksResponse.data || []
  } catch (error) {
    monitorError.value = error?.message || '采集服务未连接，请先配置并启动采集服务'
  } finally {
    monitorLoading.value = false
  }
}

const loadPlatforms = async () => {
  try {
    const response = await benchmarkApi.getPlatforms()
    const configured = response.data || []
    if (configured.length) platformOptions.value = configured
  } catch {
    // 平台列表为可选能力；未连接采集服务时保留通用平台选项。
  }
}

const bindMonitorAccount = async () => {
  if (!monitorHomepageUrl.value.trim()) return ElMessage.warning('请先粘贴对标账号主页链接或稳定账号 ID')
  monitorBinding.value = true
  monitorError.value = ''
  try {
    const selectedPlatform = monitorPlatform.value === 'auto'
      ? detectPlatform(monitorHomepageUrl.value)
      : monitorPlatform.value
    if (!selectedPlatform) {
      monitorError.value = '无法从链接识别平台，请手动选择平台'
      return
    }
    await benchmarkApi.bindOpencliMonitorAccount(monitorHomepageUrl.value.trim(), selectedPlatform)
    monitorHomepageUrl.value = ''
    monitorPlatform.value = 'auto'
    ElMessage.success('账号已加入自动监控')
    await refreshMonitor()
  } catch (error) {
    monitorError.value = error?.message || '绑定监控账号失败'
  } finally {
    monitorBinding.value = false
  }
}

const checkMonitorAccount = async (account) => {
  monitorCheckingId.value = account.id
  monitorError.value = ''
  try {
    await benchmarkApi.checkOpencliMonitorAccount(account.id)
    ElMessage.success('已提交检查任务')
    await refreshMonitor()
  } catch (error) {
    monitorError.value = error?.message || '提交检查任务失败'
  } finally {
    monitorCheckingId.value = null
  }
}

onMounted(() => Promise.all([refreshMonitor(), loadPlatforms()]))
</script>

<style lang="scss" scoped>
.benchmark-management { display: grid; gap: 16px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.page-header h1 { margin: 0; font-size: 24px; font-weight: 600; }
.page-header p, .card-subtitle { margin: 6px 0 0; color: #909399; font-size: 13px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-title, .card-header > span { font-weight: 600; }
.monitor-bind-row { display: flex; gap: 12px; margin-bottom: 14px; }
.platform-select { width: 140px; flex: 0 0 140px; }
.monitor-alert, .monitor-table { margin-bottom: 14px; }
.monitor-account-name { font-weight: 600; }
.monitor-account-id { margin-top: 4px; color: #909399; font-size: 12px; }
.muted { color: #909399; font-size: 12px; }
@media (max-width: 760px) {
  .page-header { flex-direction: column; }
  .monitor-bind-row { flex-direction: column; }
  .platform-select { width: 100%; flex-basis: auto; }
}
</style>
