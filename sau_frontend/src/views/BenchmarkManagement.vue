<template>
  <div class="benchmark-management">
    <div class="page-header">
      <div>
        <h1>对标内容库</h1>
        <p>账号添加一次后自动巡检，只判断作品是否达到账号自身热度阈值。</p>
        <ProjectReferences context="benchmark" />
      </div>
      <el-button :loading="monitorLoading" @click="refreshMonitor">刷新</el-button>
    </div>

    <el-card shadow="never" class="rules-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">默认监控规则</div>
            <div class="card-subtitle">新账号默认沿用；已有且未单独设置的账号也会同步更新。只做公开数据统计，不调用 AI。</div>
          </div>
          <el-button type="primary" :loading="savingGlobalRules" @click="saveGlobalRules">保存并重算</el-button>
        </div>
      </template>
      <div class="rules-grid">
        <div class="rule-field">
          <span>参考作品数</span>
          <el-slider v-model="globalRules.reference_work_count" :min="5" :max="50" :step="1" show-input />
        </div>
        <div class="rule-field">
          <span>火</span>
          <el-slider v-model="globalRules.hot_multiple" :min="1.5" :max="10" :step="0.5" show-input />
        </div>
        <div class="rule-field">
          <span>特别火</span>
          <el-slider v-model="globalRules.very_hot_multiple" :min="2" :max="20" :step="0.5" show-input />
        </div>
        <label class="rule-field compact-rule">
          <span>巡检频率</span>
          <el-select v-model="globalRules.interval_hours">
            <el-option v-for="hour in intervalOptions" :key="hour" :label="hour === 24 ? '每天' : `每 ${hour} 小时`" :value="hour" />
          </el-select>
        </label>
      </div>
    </el-card>

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
            <el-input
              v-if="editingAccountId === scope.row.id"
              ref="accountNameInput"
              v-model="editingAccountName"
              size="small"
              maxlength="255"
              class="account-name-editor"
              @keyup.enter="saveAccountName(scope.row)"
              @keyup.esc="cancelAccountNameEdit"
              @blur="saveAccountName(scope.row)"
            />
            <div
              v-else
              class="monitor-account-name editable-account-name"
              title="双击修改昵称"
              @dblclick="startAccountNameEdit(scope.row)"
            >{{ scope.row.display_name || scope.row.handle || scope.row.external_account_id }}</div>
            <div class="monitor-account-id">{{ scope.row.platform }} · {{ scope.row.external_account_id }}</div>
            <div class="monitor-rule-summary">{{ ruleSummary(scope.row.monitoring_rules) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="采集状态" width="150">
          <template #default="scope">
            <el-tag :type="monitorStatusType(scope.row.collection_status)">{{ monitorStatusText(scope.row.collection_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="自动监控" width="110">
          <template #default="scope">
            <el-switch
              v-model="scope.row.collection_enabled"
              :loading="monitorTogglingId === scope.row.id"
              active-text="开"
              inactive-text="停"
              inline-prompt
              @change="toggleMonitorAccount(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="last_success_at" label="最近成功" width="210" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="scope">
            <el-button size="small" :disabled="!scope.row.collection_enabled" :loading="monitorCheckingId === scope.row.id" @click="checkMonitorAccount(scope.row)">立即检查</el-button>
            <el-button size="small" @click="openAccountRules(scope.row)">设置</el-button>
            <el-button size="small" type="danger" plain @click="deleteMonitorAccount(scope.row)">彻底删除</el-button>
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
          <template #default="scope">
            <div>{{ scope.row.relative_multiple ? `${scope.row.relative_multiple.toFixed(1)}x` : '-' }}</div>
            <div class="monitor-account-id">样本 {{ scope.row.evidence?.baseline_size || 0 }}/{{ scope.row.evidence?.configured_reference_work_count || 20 }}</div>
          </template>
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
        <el-form-item label="火倍数">
          <el-slider v-model="accountRules.hot_multiple" :min="1.5" :max="10" :step="0.5" show-input :disabled="accountRules.inherit_global" />
        </el-form-item>
        <el-form-item label="特别火倍数">
          <el-slider v-model="accountRules.very_hot_multiple" :min="2" :max="20" :step="0.5" show-input :disabled="accountRules.inherit_global" />
        </el-form-item>
        <el-form-item label="巡检频率">
          <el-select v-model="accountRules.interval_hours" :disabled="accountRules.inherit_global" style="width: 100%">
            <el-option v-for="hour in intervalOptions" :key="hour" :label="hour === 24 ? '每天' : `每 ${hour} 小时`" :value="hour" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert title="少于 5 条历史作品时不判火；达到 5 条后会按实际样本计算，并显示 X/目标条数。当前作品不会进入自己的中位数。" type="info" :closable="false" />
      <template #footer>
        <el-button @click="accountRulesVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingAccountRules" @click="saveAccountRules">保存并重算</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { benchmarkApi } from '@/api/benchmark'
import ProjectReferences from '@/components/ProjectReferences.vue'

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
const globalRules = ref({ reference_work_count: 20, hot_multiple: 3, very_hot_multiple: 5, interval_hours: 4, inherit_global: true })
const savingGlobalRules = ref(false)
const accountRulesVisible = ref(false)
const accountRulesId = ref(null)
const accountRules = ref({ ...globalRules.value })
const savingAccountRules = ref(false)

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

const ruleSummary = (rules = {}) => {
  const value = { ...globalRules.value, ...(rules || {}) }
  const interval = value.interval_hours === 24 ? '每天' : `每${value.interval_hours}小时`
  return `近${value.reference_work_count}条 · 火${value.hot_multiple}x · 特别火${value.very_hot_multiple}x · ${interval}${value.inherit_global === false ? ' · 单独设置' : ''}`
}

const validateRules = (rules) => {
  if (Number(rules.very_hot_multiple) <= Number(rules.hot_multiple)) {
    ElMessage.warning('“特别火”倍数必须大于“火”倍数')
    return false
  }
  return true
}

const loadGlobalRules = async () => {
  const response = await benchmarkApi.getOpencliMonitorRules()
  globalRules.value = { ...globalRules.value, ...(response.data || {}) }
}

const saveGlobalRules = async () => {
  if (!validateRules(globalRules.value)) return
  savingGlobalRules.value = true
  try {
    const response = await benchmarkApi.updateOpencliMonitorRules({ ...globalRules.value, inherit_global: true })
    const failures = response.data?.failures || []
    ElMessage.success(failures.length ? `默认规则已保存，${failures.length} 个账号等待下次同步` : '默认规则已保存，已有数据已重算')
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
.benchmark-management { display: grid; gap: 16px; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 22px; padding-bottom: 18px; border-bottom: 1px solid var(--sau-line); }
.page-header h1 { margin: 0; color: var(--sau-ink); font-size: 28px; font-weight: 650; letter-spacing: -0.02em; }
.page-header p, .card-subtitle { margin: 6px 0 0; color: var(--sau-ink-soft); font-size: 13px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-title, .card-header > span { font-weight: 600; }
.monitor-bind-row { display: flex; gap: 12px; margin-bottom: 14px; }
.platform-select { width: 140px; flex: 0 0 140px; }
.monitor-alert, .monitor-table { margin-bottom: 14px; }
.rules-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 36px; }
.rule-field { min-width: 0; }
.rule-field > span { display: block; margin-bottom: 8px; color: #606266; font-size: 13px; }
.compact-rule { max-width: 260px; }
.monitor-account-name { font-weight: 600; }
.editable-account-name { cursor: text; width: fit-content; border-bottom: 1px dashed transparent; }
.editable-account-name:hover { color: #409eff; border-bottom-color: #409eff; }
.account-name-editor { max-width: 260px; }
.monitor-account-id { margin-top: 4px; color: #909399; font-size: 12px; }
.monitor-rule-summary { margin-top: 5px; color: #606266; font-size: 12px; }
.muted { color: #909399; font-size: 12px; }
@media (max-width: 760px) {
  .page-header { flex-direction: column; }
  .monitor-bind-row { flex-direction: column; }
  .rules-grid { grid-template-columns: 1fr; }
  .platform-select { width: 100%; flex-basis: auto; }
}
</style>
