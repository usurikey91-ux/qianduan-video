<template>
  <div class="benchmark-management">
    <header class="sau-page-head">
      <span class="sau-page-icon"><el-icon><Aim /></el-icon></span>
      <div class="sau-page-title">
        <h1>对标账号</h1>
        <p>按近 {{ WINDOW_DAYS }} 天入选作品数排序，只统计公开数据，不调用 AI</p>
      </div>
      <div class="sau-page-counts">
        <span class="sau-badge">账号 {{ monitorAccounts.length }}</span>
        <span class="sau-badge is-accent">近 {{ WINDOW_DAYS }} 天入选 {{ recentWorkCount }}</span>
        <span v-if="warningCount" class="sau-badge is-warning">需处理 {{ warningCount }}</span>
      </div>
      <div class="sau-page-actions">
        <el-button :icon="Setting" @click="openRulesDialog">默认规则</el-button>
        <el-button :icon="Refresh" :loading="monitorLoading" @click="refreshMonitor">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openBindDialog">添加对标账号</el-button>
      </div>
    </header>

    <div class="sau-page-filters">
      <div class="filter-line">
        <div class="sau-chips">
          <span class="sau-chip is-label"><el-icon><Filter /></el-icon>平台</span>
          <button
            v-for="item in platformFilterOptions"
            :key="item.value"
            type="button"
            class="sau-chip"
            :class="{ 'is-active': platformFilter === item.value }"
            @click="platformFilter = item.value"
          >{{ item.label }} · <em>{{ item.count }}</em></button>
        </div>
        <span class="rule-line">入选线 {{ ruleSummary(globalRules) }}</span>
      </div>
      <ProjectReferences context="benchmark" />
    </div>

    <div class="sau-page-body">
      <el-alert
        v-if="monitorError && !bindDialog && !rulesDialog"
        :title="monitorError"
        type="warning"
        show-icon
        :closable="false"
        class="monitor-alert"
      />

      <div v-loading="monitorLoading && !monitorAccounts.length" class="acc-grid">
        <TransitionGroup name="card" appear>
          <article
            v-for="(item, index) in visibleAccounts"
            :key="item.account.id"
            class="acc-card"
            :class="{ paused: !item.account.collection_enabled }"
            :style="{ '--i': index }"
          >
            <header class="c-head">
              <span class="c-rank">{{ String(item.rank).padStart(2, '0') }}</span>
              <span class="sau-badge" :class="badgeClass(item.account)">{{ monitorStatusText(item.account.collection_status) }}</span>
              <span class="c-plat">{{ platformLabel(item.account.platform) }}</span>
              <el-dropdown trigger="click" @command="(cmd) => onAccountCommand(cmd, item.account)">
                <button class="c-more" type="button" aria-label="更多操作"><el-icon><MoreFilled /></el-icon></button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">修改名称</el-dropdown-item>
                    <el-dropdown-item command="rules">单独设置规则</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">彻底删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </header>

            <div class="c-id">
              <div class="avatar" :style="avatarStyle(item.account)">{{ accountName(item.account).slice(0, 1) }}</div>
              <div class="c-id-text">
                <el-input
                  v-if="editingAccountId === item.account.id"
                  ref="accountNameInput"
                  v-model="editingAccountName"
                  size="small"
                  maxlength="255"
                  @keyup.enter="saveAccountName(item.account)"
                  @keyup.esc="cancelAccountNameEdit"
                  @blur="saveAccountName(item.account)"
                />
                <a v-else-if="item.account.profile_url" class="c-name" :href="item.account.profile_url" target="_blank" rel="noopener noreferrer" title="打开账号主页">{{ accountName(item.account) }}</a>
                <span v-else class="c-name">{{ accountName(item.account) }}</span>
                <span class="c-sub">{{ ruleSummary(item.account.monitoring_rules) }}</span>
              </div>
            </div>

            <div class="c-stats">
              <div>
                <b>{{ item.recent.length }}</b>
                <span>近 {{ WINDOW_DAYS }} 天入选</span>
              </div>
              <div>
                <b :class="{ hot: item.best >= 10 }">{{ item.best ? `${item.best.toFixed(1)}x` : '—' }}</b>
                <span>最高倍数</span>
              </div>
              <div>
                <b>{{ item.works.length }}</b>
                <span>累计入选</span>
              </div>
            </div>

            <div class="c-bars" :title="`最近 ${item.series.length} 条入选作品的相对倍数`" aria-hidden="true">
              <span
                v-for="bar in item.bars"
                :key="bar.key"
                :class="{ hot: bar.hot, empty: bar.empty }"
                :style="{ height: `${bar.height}%` }"
              />
            </div>

            <div class="c-best">
              <template v-if="item.bestWork">
                <span class="c-best-label">最高一条</span>
                <span class="c-best-title">{{ cleanTitle(item.bestWork.title) || '无标题' }}</span>
              </template>
              <span v-else class="c-best-empty">{{ monitorStatusHint(item.account) || `近 ${WINDOW_DAYS} 天没有作品超过入选线` }}</span>
            </div>

            <footer class="c-foot">
              <span class="c-updated">{{ item.account.last_success_at ? `${relativeTime(item.account.last_success_at)}更新` : '尚未采集' }}</span>
              <el-button size="small" :disabled="!item.account.collection_enabled" :loading="monitorCheckingId === item.account.id" @click="checkMonitorAccount(item.account)">立即检查</el-button>
              <el-switch
                v-model="item.account.collection_enabled"
                :loading="monitorTogglingId === item.account.id"
                size="small"
                title="自动监控"
                @change="toggleMonitorAccount(item.account)"
              />
            </footer>
          </article>
        </TransitionGroup>
      </div>

      <el-empty v-if="!monitorLoading && !monitorAccounts.length" description="还没有添加对标账号，系统也可以保持空状态运行" :image-size="80">
        <el-button type="primary" @click="openBindDialog">添加对标账号</el-button>
      </el-empty>
    </div>
    <el-dialog v-model="bindDialog" title="添加对标账号" width="560px">
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
      </div>
      <el-alert v-if="monitorError" :title="monitorError" type="warning" show-icon :closable="false" />
      <template #footer>
        <el-button @click="bindDialog = false">取消</el-button>
        <el-button type="primary" :loading="monitorBinding" @click="bindMonitorAccount">添加对标账号</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rulesDialog" title="默认监控规则" width="560px">
      <p class="dialog-note">新账号默认沿用；已有且未单独设置的账号也会同步更新。</p>
      <el-form label-position="top">
        <el-form-item label="参考作品数">
          <el-slider v-model="globalRules.reference_work_count" :min="5" :max="50" :step="1" show-input />
        </el-form-item>
        <el-form-item label="入选倍数">
          <el-slider v-model="globalRules.hot_multiple" :min="1.5" :max="10" :step="0.5" show-input />
        </el-form-item>
        <el-form-item label="巡检频率">
          <el-select v-model="globalRules.interval_hours" style="width: 100%">
            <el-option v-for="hour in intervalOptions" :key="hour" :label="hour === 24 ? '每天' : `每 ${hour} 小时`" :value="hour" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert v-if="monitorError" :title="monitorError" type="warning" show-icon :closable="false" />
      <template #footer>
        <el-button @click="cancelRulesDialog">取消</el-button>
        <el-button type="primary" :loading="savingGlobalRules" @click="saveGlobalRules">保存并重算</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="accountRulesVisible" title="账号监控规则" width="560px">
      <el-form label-position="top">
        <el-form-item>
          <el-switch
            v-model="accountRules.inherit_global"
            active-text="沿用默认规则"
            inactive-text="该账号单独设置"
            @change="syncAccountRulesFromGlobal"
          />
        </el-form-item>
        <el-form-item label="参考作品数">
          <el-slider v-model="accountRules.reference_work_count" :min="5" :max="50" :step="1" show-input :disabled="accountRules.inherit_global" />
        </el-form-item>
        <el-form-item label="入选倍数">
          <el-slider v-model="accountRules.hot_multiple" :min="1.5" :max="10" :step="0.5" show-input :disabled="accountRules.inherit_global" />
        </el-form-item>
        <el-form-item label="巡检频率">
          <el-select v-model="accountRules.interval_hours" :disabled="accountRules.inherit_global" style="width: 100%">
            <el-option v-for="hour in intervalOptions" :key="hour" :label="hour === 24 ? '每天' : `每 ${hour} 小时`" :value="hour" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert title="少于 5 条历史作品时不做入选判断；达到 5 条后按实际样本计算，并显示 X/目标条数。当前作品不会进入自己的中位数。" type="info" :closable="false" />
      <template #footer>
        <el-button @click="accountRulesVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingAccountRules" @click="saveAccountRules">保存并重算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Aim, Filter, MoreFilled, Plus, Refresh, Setting } from '@element-plus/icons-vue'
import { benchmarkApi } from '@/api/benchmark'
import ProjectReferences from '@/components/ProjectReferences.vue'

const WINDOW_DAYS = 30
const BAR_COUNT = 16

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
const monitorTogglingId = ref(null)
const monitorError = ref('')
const editingAccountId = ref(null)
const editingAccountName = ref('')
const accountNameInput = ref(null)
const savingAccountName = ref(false)
const intervalOptions = [1, 2, 4, 8, 12, 24]
const globalRules = ref({ reference_work_count: 20, hot_multiple: 5, very_hot_multiple: 5.5, interval_hours: 4, inherit_global: true })
const savedGlobalRules = ref({ ...globalRules.value })
const savingGlobalRules = ref(false)
const accountRulesVisible = ref(false)
const accountRulesId = ref(null)
const accountRules = ref({ ...globalRules.value })
const savingAccountRules = ref(false)
const bindDialog = ref(false)
const rulesDialog = ref(false)
const platformFilter = ref('all')

const PLATFORM_LABELS = { douyin: '抖音', xiaohongshu: '小红书', bilibili: 'B站', kuaishou: '快手', weibo: '微博', youtube: 'YouTube', tiktok: 'TikTok' }
const platformLabel = (platform) => PLATFORM_LABELS[platform] || platform || '未知平台'
const accountName = (account) => account.display_name || account.handle || account.external_account_id || '未命名账号'

// 后端不带时区的时间按 UTC 解析，与后端规则一致。
const parseTime = (value) => {
  if (!value) return null
  const text = String(value).trim().replace(' ', 'T')
  const date = new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(text) ? text : `${text}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

const relativeTime = (value) => {
  const date = parseTime(value)
  if (!date) return ''
  const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000))
  if (minutes < 60) return `${minutes || 1} 分钟前`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} 小时前`
  return `${Math.round(minutes / 60 / 24)} 天前`
}

const AVATAR_TINTS = ['#c9a27a, #8c6845', '#9aa58a, #5f6b4e', '#a3b2bb, #627580', '#c49a8a, #87594a', '#b2a2c4, #6e5f85', '#cdb489, #8e7547']
const avatarStyle = (account) => {
  const seed = [...String(account.id || '')].reduce((sum, ch) => sum + ch.charCodeAt(0), 0)
  return { background: `linear-gradient(135deg, ${AVATAR_TINTS[seed % AVATAR_TINTS.length]})` }
}

// 去掉标题里的话题标签；整条都是标签时用标签兜底。
const cleanTitle = (title) => {
  const text = String(title || '')
  const body = text.replace(/#[^#\s]+/g, ' ').replace(/\s+/g, ' ').trim()
  return body || [...text.matchAll(/#([^#\s]+)/g)].map((m) => m[1]).join(' · ')
}

// 最近 BAR_COUNT 条入选作品的倍数柱；倍数差距可达几十倍，柱高用对数刻度。不足的位置补空柱。
const buildBars = (series) => {
  const values = series.map((work) => work.relative_multiple)
  const max = Math.max(...values, 1)
  const logMax = Math.log(max + 1)
  const bars = values.map((v, i) => ({
    key: `${series[i].external_work_id || i}`,
    height: Math.max(10, (Math.log(v + 1) / logMax) * 100),
    hot: v === max,
    empty: false
  }))
  while (bars.length < BAR_COUNT) bars.unshift({ key: `empty-${bars.length}`, height: 8, hot: false, empty: true })
  return bars
}

const rankedAccounts = computed(() => {
  const cutoff = Date.now() - WINDOW_DAYS * 86400000
  const byAccount = new Map()
  for (const work of monitorWorks.value) {
    const id = work.account?.id
    if (!id || !Number.isFinite(Number(work.relative_multiple))) continue
    if (!byAccount.has(id)) byAccount.set(id, [])
    byAccount.get(id).push({ ...work, relative_multiple: Number(work.relative_multiple), _published: parseTime(work.published_at)?.getTime() || 0 })
  }
  return monitorAccounts.value
    .map((account) => {
      const works = (byAccount.get(account.id) || []).sort((a, b) => a._published - b._published)
      const recent = works.filter((work) => work._published >= cutoff)
      const bestWork = recent.reduce((top, work) => (!top || work.relative_multiple > top.relative_multiple ? work : top), null)
      const series = works.slice(-BAR_COUNT)
      return { account, works, recent, bestWork, best: bestWork?.relative_multiple || 0, series, bars: buildBars(series) }
    })
    .sort((a, b) => b.recent.length - a.recent.length || b.best - a.best || b.works.length - a.works.length)
    .map((item, index) => ({ ...item, rank: index + 1 }))
})

const visibleAccounts = computed(() => rankedAccounts.value.filter((item) =>
  platformFilter.value === 'all' || item.account.platform === platformFilter.value))

const recentWorkCount = computed(() => rankedAccounts.value.reduce((sum, item) => sum + item.recent.length, 0))

const platformFilterOptions = computed(() => {
  const counts = new Map()
  for (const account of monitorAccounts.value) counts.set(account.platform, (counts.get(account.platform) || 0) + 1)
  return [
    { label: '全部', value: 'all', count: monitorAccounts.value.length },
    ...[...counts].map(([value, count]) => ({ label: platformLabel(value), value, count }))
  ]
})

const badgeClass = (account) => ({
  success: 'is-success', warning: 'is-warning', danger: 'is-danger'
}[monitorStatusType(account.collection_status)] || '')

const warningCount = computed(() => monitorAccounts.value.filter((account) =>
  ['warning', 'danger'].includes(monitorStatusType(account.collection_status)) && account.collection_status !== 'checking').length)

const onAccountCommand = (command, account) => {
  if (command === 'rename') startAccountNameEdit(account)
  if (command === 'rules') openAccountRules(account)
  if (command === 'delete') deleteMonitorAccount(account)
}

const openBindDialog = () => {
  monitorError.value = ''
  bindDialog.value = true
}

const openRulesDialog = () => {
  monitorError.value = ''
  savedGlobalRules.value = { ...globalRules.value }
  rulesDialog.value = true
}

const cancelRulesDialog = () => {
  globalRules.value = { ...savedGlobalRules.value }
  rulesDialog.value = false
}

const detectPlatform = (value) => {
  const text = String(value || '').toLowerCase()
  if (text.includes('douyin.com')) return 'douyin'
  if (text.includes('xiaohongshu.com') || text.includes('xhslink.com') || text.includes('xhslink.cn')) return 'xiaohongshu'
  if (text.includes('bilibili.com') || text.includes('b23.tv')) return 'bilibili'
  if (text.includes('kuaishou.com')) return 'kuaishou'
  if (text.includes('weibo.com')) return 'weibo'
  if (text.includes('youtube.com') || text.includes('youtu.be')) return 'youtube'
  if (text.includes('tiktok.com')) return 'tiktok'
  return ''
}

const monitorStatusText = (status) => {
  const map = {
    unconfigured: '未配置', ready: '待检查', checking: '检查中', ok: '正常', paused: '已暂停',
    account_invalid: '账号失效', login_required: '需要登录', login_expired: '登录失效',
    missing_metric: '缺少数据字段', collection_failed: '采集失败', published_at_missing: '缺少发布时间',
    platform_restricted: '平台暂拒', empty_results: '空结果'
  }
  return map[status] || status || '未知'
}

const monitorStatusHint = (account) => {
  if (account.collection_status === 'platform_restricted') {
    const platformName = {
      bilibili: 'B站', douyin: '抖音', xiaohongshu: '小红书', kuaishou: '快手'
    }[account.platform] || account.platform || '平台'
    return account.last_error_message?.toLowerCase().includes('412')
      ? `${platformName}返回 HTTP 412，本次未更新作品`
      : `${platformName}暂时拒绝本次请求，作品未更新`
  }
  if (account.collection_status === 'empty_results') return '接口返回 0 条作品，本次不算成功'
  return ''
}

const monitorStatusType = (status) => {
  if (status === 'ok') return 'success'
  if (['account_invalid', 'login_required', 'login_expired', 'missing_metric', 'collection_failed', 'published_at_missing'].includes(status)) return 'danger'
  if (['platform_restricted', 'empty_results'].includes(status)) return 'warning'
  if (status === 'checking') return 'warning'
  return 'info'
}

const formatPublicMetrics = (metrics) => {
  if (!metrics || typeof metrics !== 'object') return '-'
  const labels = { like_count: '赞', favorite_count: '藏', comment_count: '评', share_count: '转', view_count: '播' }
  return Object.entries(metrics).map(([key, value]) => `${labels[key] || key} ${value}`).join(' · ') || '-'
}

const ruleSummary = (rules = {}) => {
  const value = { ...globalRules.value, ...(rules || {}) }
  const interval = value.interval_hours === 24 ? '每天' : `每${value.interval_hours}小时`
  return `近${value.reference_work_count}条 · 入选≥${value.hot_multiple}x · ${interval}${value.inherit_global === false ? ' · 单独设置' : ''}`
}

const validateRules = (rules) => {
  if (Number(rules.hot_multiple) < 1.5 || Number(rules.hot_multiple) > 10) {
    ElMessage.warning('入选倍数必须在 1.5 到 10 之间')
    return false
  }
  return true
}

const loadGlobalRules = async () => {
  const response = await benchmarkApi.getOpencliMonitorRules()
  globalRules.value = { ...globalRules.value, ...(response.data || {}) }
  savedGlobalRules.value = { ...globalRules.value }
}

const saveGlobalRules = async () => {
  if (!validateRules(globalRules.value)) return
  savingGlobalRules.value = true
  try {
    const response = await benchmarkApi.updateOpencliMonitorRules({ ...globalRules.value, inherit_global: true })
    const failures = response.data?.failures || []
    ElMessage.success(failures.length ? `默认规则已保存，${failures.length} 个账号等待下次同步` : '默认规则已保存，已有数据已重算')
    savedGlobalRules.value = { ...globalRules.value }
    rulesDialog.value = false
    await refreshMonitor()
  } catch (error) {
    monitorError.value = error?.message || '保存默认监控规则失败'
  } finally {
    savingGlobalRules.value = false
  }
}

const openAccountRules = (account) => {
  accountRulesId.value = account.id
  accountRules.value = { ...globalRules.value, ...(account.monitoring_rules || {}) }
  accountRulesVisible.value = true
}

const syncAccountRulesFromGlobal = (enabled) => {
  if (enabled) accountRules.value = { ...globalRules.value, inherit_global: true }
}

const saveAccountRules = async () => {
  if (!accountRulesId.value || !validateRules(accountRules.value)) return
  savingAccountRules.value = true
  try {
    const rules = accountRules.value.inherit_global
      ? { ...globalRules.value, inherit_global: true }
      : { ...accountRules.value, inherit_global: false }
    await benchmarkApi.updateOpencliMonitorAccountRules(accountRulesId.value, rules)
    ElMessage.success('账号规则已保存，已有数据已重算')
    accountRulesVisible.value = false
    await refreshMonitor()
  } catch (error) {
    monitorError.value = error?.message || '保存账号监控规则失败'
  } finally {
    savingAccountRules.value = false
  }
}

const refreshMonitor = async () => {
  monitorLoading.value = true
  monitorError.value = ''
  try {
    const [accountsResponse, worksResponse] = await Promise.all([
      benchmarkApi.getOpencliMonitorAccounts(),
      benchmarkApi.getOpencliMonitorWorks()
    ])
    // The monitor adapter may also return historical/system rows. The page
    // represents the user's active benchmark set, so hide disabled entries.
    const activeAccounts = (accountsResponse.data || []).filter((account) =>
      account.collection_enabled !== false || account.collection_status === 'paused'
    )
    const activeAccountIds = new Set(activeAccounts.map((account) => account.id))
    monitorAccounts.value = activeAccounts
    monitorWorks.value = (worksResponse.data || []).filter((work) =>
      activeAccountIds.has(work.account?.id)
    )
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
    bindDialog.value = false
    ElMessage.success('账号已加入自动监控')
    await refreshMonitor()
  } catch (error) {
    monitorError.value = error?.response?.data?.msg || error?.message || '绑定监控账号失败'
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

const toggleMonitorAccount = async (account) => {
  monitorTogglingId.value = account.id
  monitorError.value = ''
  try {
    const response = await benchmarkApi.setOpencliMonitorAccountEnabled(account.id, account.collection_enabled)
    Object.assign(account, response.data || {})
    ElMessage.success(account.collection_enabled ? '已恢复自动监控' : '已暂停自动监控，历史数据保留')
  } catch (error) {
    account.collection_enabled = !account.collection_enabled
    monitorError.value = error?.message || '切换自动监控状态失败'
  } finally {
    monitorTogglingId.value = null
  }
}

const startAccountNameEdit = async (account) => {
  editingAccountId.value = account.id
  editingAccountName.value = account.display_name || account.handle || ''
  await nextTick()
  const input = Array.isArray(accountNameInput.value) ? accountNameInput.value[0] : accountNameInput.value
  input?.focus?.()
  input?.select?.()
}

const cancelAccountNameEdit = () => {
  editingAccountId.value = null
  editingAccountName.value = ''
}

const saveAccountName = async (account) => {
  if (savingAccountName.value || editingAccountId.value !== account.id) return
  const displayName = editingAccountName.value.trim()
  if (!displayName) return ElMessage.warning('昵称不能为空')
  if (displayName === account.display_name) return cancelAccountNameEdit()
  savingAccountName.value = true
  try {
    const response = await benchmarkApi.updateOpencliMonitorAccount(account.id, displayName)
    account.display_name = response.data?.display_name || displayName
    ElMessage.success('昵称已保存')
    cancelAccountNameEdit()
  } catch (error) {
    monitorError.value = error?.message || '保存昵称失败'
  } finally {
    savingAccountName.value = false
  }
}

const deleteMonitorAccount = async (account) => {
  const name = account.display_name || account.handle || account.external_account_id
  try {
    await ElMessageBox.confirm(
      `将彻底删除“${name}”以及已采集作品、公开数据快照和爆款记录。删除后无法恢复。`,
      '确认彻底删除对标账号',
      { type: 'error', confirmButtonText: '彻底删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  monitorError.value = ''
  try {
    await benchmarkApi.removeOpencliMonitorAccount(account.id)
    ElMessage.success('对标账号及全部历史数据已彻底删除')
    await refreshMonitor()
  } catch (error) {
    monitorError.value = error?.message || '彻底删除账号失败'
  }
}

onMounted(async () => {
  try {
    await loadGlobalRules()
  } catch (error) {
    monitorError.value = error?.message || '读取默认监控规则失败'
  }
  await Promise.all([refreshMonitor(), loadPlatforms()])
})
</script>

<style lang="scss" scoped>
.benchmark-management { min-height: 100%; }

.filter-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rule-line { flex: none; color: var(--sau-muted); font-size: 11px; }

.monitor-alert { margin-bottom: 14px; }

.acc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  min-height: 200px;
}

// Beav cards: white, 1px warm border, 12px radius, no resting shadow; a soft shadow only on hover.
.acc-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--sau-line);
  border-radius: 12px;
  background: var(--sau-paper);
  transition: box-shadow 200ms ease, border-color 200ms ease, transform 200ms var(--sau-ease-out), opacity 200ms ease;

  &:hover {
    border-color: var(--sau-accent-border);
    box-shadow: var(--sau-shadow-sm);
    transform: translateY(-1px);
  }

  &.paused { opacity: 0.62; }
}

.card-enter-active {
  transition: opacity 260ms ease, transform 300ms var(--sau-ease-out);
  transition-delay: calc(min(var(--i), 12) * 30ms);
}
.card-enter-from { opacity: 0; transform: translateY(8px); }

.c-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px 0 14px;
}

.c-rank {
  color: var(--sau-muted);
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.c-plat { margin-left: auto; color: var(--sau-muted); font-size: 11px; }

.c-more {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--sau-muted);
  cursor: pointer;

  &:hover { background: var(--sau-paper-muted); color: var(--sau-ink); }
}

.c-id {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px 0;
}

.avatar {
  flex: none;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.c-id-text { display: grid; min-width: 0; gap: 2px; }

.c-name {
  overflow: hidden;
  color: var(--sau-ink);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}

a.c-name:hover { color: var(--sau-accent); }

.c-sub { overflow: hidden; color: var(--sau-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.c-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 14px 14px 0;
  padding: 10px 0;
  border-top: 1px solid var(--sau-divider);
  border-bottom: 1px solid var(--sau-divider);

  div { display: grid; gap: 2px; }
  div + div { padding-left: 12px; border-left: 1px solid var(--sau-divider); }

  b {
    color: var(--sau-ink);
    font-size: 18px;
    font-weight: 600;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;

    &.hot { color: var(--sau-accent); }
  }

  span { color: var(--sau-muted); font-size: 11px; }
}

.c-bars {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 36px;
  margin: 12px 14px 0;

  span {
    flex: 1;
    min-height: 3px;
    border-radius: 2px 2px 0 0;
    background: var(--sau-soft);
    transition: height 400ms var(--sau-ease-out);

    &.hot { background: var(--sau-accent); }
    &:not(.hot):not(.empty) { background: var(--sau-accent-border); }
  }
}

.c-best {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-height: 34px;
  padding: 8px 14px 0;
  font-size: 12px;
}

.c-best-label { flex: none; color: var(--sau-muted); font-size: 11px; }

.c-best-title,
.c-best-empty {
  min-width: 0;
  overflow: hidden;
  color: var(--sau-ink-soft);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.c-best-empty { color: var(--sau-muted); }

.c-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  padding: 10px 14px 12px;
}

.c-updated { flex: 1; min-width: 0; overflow: hidden; color: var(--sau-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.monitor-bind-row { display: flex; gap: 12px; margin-bottom: 14px; }
.platform-select { width: 140px; flex: 0 0 140px; }
.dialog-note { margin: 0 0 14px; color: var(--sau-ink-soft); font-size: 13px; }
:global(.danger-item) { color: var(--el-color-danger) !important; }

@media (max-width: 760px) {
  .sau-page-counts { display: none; }
  .filter-line { flex-direction: column; align-items: flex-start; }
  .monitor-bind-row { flex-direction: column; }
  .platform-select { width: 100%; flex-basis: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .acc-card, .card-enter-active { transition: none; }
}
</style>