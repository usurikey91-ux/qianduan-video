<template>
  <section class="connections-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">LOCAL ACCOUNT CONNECTIONS</span>
        <h1>账号连接</h1>
        <p>在这台电脑上打开平台官方登录页，由你本人扫码。密码、验证码和 Cookie 不会进入工作台接口。</p>
      </div>
      <el-button :icon="Refresh" :loading="refreshing" @click="refresh(true)">重新检测</el-button>
    </header>

    <el-alert
      title="每台电脑都是一套独立工作台"
      type="success"
      :closable="false"
      show-icon
    >
      <template #default>
        从 GitHub 安装后，每个人只连接自己的账号。登录态、作品数据和设置均保存在当前电脑，不经过项目作者的服务器。
      </template>
    </el-alert>

    <div class="steps" aria-label="首次使用步骤">
      <div><strong>1</strong><span>检测本机连接器</span></div>
      <div><strong>2</strong><span>打开官方页面扫码</span></div>
      <div><strong>3</strong><span>核对账号并首次同步</span></div>
    </div>

    <div class="platform-grid">
      <article v-for="platform in platforms" :key="platform.id" class="platform-card">
        <div class="platform-card__top">
          <div class="platform-mark" :class="`platform-mark--${platform.id}`">
            {{ platform.shortName }}
          </div>
          <div class="platform-title">
            <div class="title-row">
              <h2>{{ platform.name }}</h2>
              <el-tag :type="statusMeta(platform.id).type" effect="plain">
                {{ statusMeta(platform.id).label }}
              </el-tag>
            </div>
            <p>{{ platform.description }}</p>
          </div>
        </div>

        <div v-if="connection(platform.id)?.account" class="account-panel">
          <el-avatar :size="44">{{ accountInitial(platform.id) }}</el-avatar>
          <div>
            <span>当前本机账号</span>
            <strong>{{ connection(platform.id).account.displayName }}</strong>
            <small v-if="connection(platform.id).account.followers !== undefined">
              粉丝 {{ connection(platform.id).account.followers }}
            </small>
          </div>
        </div>
        <div v-else class="account-panel account-panel--empty">
          <el-icon><UserFilled /></el-icon>
          <div><strong>尚未确认账号</strong><span>扫码成功后会在这里显示账号身份</span></div>
        </div>

        <div class="status-panel" aria-live="polite">
          <el-icon :class="{ spinning: isActive(platform.id) }">
            <Loading v-if="isActive(platform.id)" />
            <CircleCheckFilled v-else-if="isConnected(platform.id)" />
            <WarningFilled v-else />
          </el-icon>
          <div>
            <strong>{{ statusMessage(platform.id) }}</strong>
            <span v-if="connection(platform.id)?.job?.message">
              {{ connection(platform.id).job.message }}
            </span>
            <span v-else-if="connection(platform.id)?.error">
              {{ connection(platform.id).error }}
            </span>
            <span v-else>官方页面中的验证码或安全验证必须由用户本人完成。</span>
          </div>
        </div>

        <div v-if="platform.id === 'douyin'" class="risk-box">
          <el-checkbox v-model="douyinRiskAcknowledged">
            我已了解这是非官方本地工具，自动化读取可能受到平台条款和风控限制
          </el-checkbox>
          <a
            v-if="connection('douyin')?.termsUrl"
            :href="connection('douyin').termsUrl"
            target="_blank"
            rel="noreferrer"
          >查看抖音平台条款</a>
        </div>

        <div class="card-actions">
          <el-button
            type="primary"
            :loading="isActive(platform.id)"
            :disabled="!canStart(platform.id)"
            @click="startLogin(platform.id)"
          >
            {{ loginButtonLabel(platform.id) }}
          </el-button>
          <el-button @click="goToReview(platform.id)">查看作品复盘</el-button>
        </div>
      </article>
    </div>

    <el-card shadow="never" class="safety-card">
      <template #header><strong>降低登录与采集风险的默认规则</strong></template>
      <div class="safety-grid">
        <div><el-icon><Monitor /></el-icon><span>只在本机可见浏览器中登录</span></div>
        <div><el-icon><Lock /></el-icon><span>不接收密码、验证码和 Cookie</span></div>
        <div><el-icon><Timer /></el-icon><span>串行同步并在失败后停止重试</span></div>
        <div><el-icon><View /></el-icon><span>默认只读创作者后台数据</span></div>
      </div>
      <p>任何浏览器自动化都不能承诺零风控。遇到验证码、异常登录或账号不一致时，工作台必须暂停并交还用户处理。</p>
    </el-card>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled,
  Loading,
  Lock,
  Monitor,
  Refresh,
  Timer,
  UserFilled,
  View,
  WarningFilled
} from '@element-plus/icons-vue'
import { platformConnectionsApi } from '@/api/platformConnections'

const router = useRouter()
const refreshing = ref(false)
const douyinRiskAcknowledged = ref(false)
const connections = reactive({ douyin: null, xiaohongshu: null })
let pollTimer = null

const platforms = [
  {
    id: 'douyin',
    shortName: '抖',
    name: '抖音创作者中心',
    description: '连接自己的创作者账号，读取作品表现、流量入口、粉丝占比与平台实际开放的画像数据。'
  },
  {
    id: 'xiaohongshu',
    shortName: '薯',
    name: '小红书创作服务平台',
    description: '连接自己的创作者账号，读取笔记表现、观看来源、观众画像与账号趋势。'
  }
]

const activePhases = new Set(['starting', 'waiting_for_scan', 'syncing'])
const connectedStates = new Set(['connected'])
const statusMap = {
  connected: { label: '已连接', type: 'success' },
  syncing: { label: '首次同步中', type: 'warning' },
  waiting_for_scan: { label: '等待扫码', type: 'warning' },
  starting: { label: '正在启动', type: 'warning' },
  login_check_required: { label: '需要验证', type: 'warning' },
  login_required: { label: '未登录', type: 'info' },
  local_data_available: { label: '已有本地数据', type: 'info' },
  connector_unavailable: { label: '连接器不可用', type: 'danger' },
  expired: { label: '登录超时', type: 'danger' },
  failed: { label: '连接失败', type: 'danger' },
  unknown: { label: '尚未检测', type: 'info' }
}

const connection = (platform) => connections[platform]
const currentState = (platform) => connection(platform)?.state || 'unknown'
const isActive = (platform) => activePhases.has(currentState(platform))
const isConnected = (platform) => connectedStates.has(currentState(platform))
const statusMeta = (platform) => statusMap[currentState(platform)] || statusMap.unknown

const accountInitial = (platform) => {
  const name = connection(platform)?.account?.displayName || ''
  return name.trim().slice(0, 1) || '账'
}

const statusMessage = (platform) => {
  const state = currentState(platform)
  if (state === 'connected') return '已确认本机登录状态'
  if (state === 'waiting_for_scan') return '请在官方窗口完成扫码'
  if (state === 'syncing') return '账号已登录，正在同步后台数据'
  if (state === 'login_check_required') return '本机已有历史数据，但当前登录态需要重新验证'
  if (state === 'connector_unavailable') return '未找到该平台连接器'
  if (state === 'expired') return '本次二维码或登录等待已超时'
  if (state === 'failed') return '本次连接没有完成'
  return '尚未连接当前平台账号'
}

const canStart = (platform) => {
  if (isActive(platform)) return false
  if (connection(platform)?.available === false) return false
  return platform !== 'douyin' || douyinRiskAcknowledged.value
}

const loginButtonLabel = (platform) => {
  if (isActive(platform)) return currentState(platform) === 'syncing' ? '正在同步' : '等待用户扫码'
  return isConnected(platform) ? '重新验证登录' : `扫码连接${platform === 'douyin' ? '抖音' : '小红书'}`
}

const shouldPoll = computed(() => platforms.some((item) => isActive(item.id)))

const updatePolling = () => {
  if (shouldPoll.value && !pollTimer) {
    pollTimer = window.setInterval(() => refresh(false), 2500)
  } else if (!shouldPoll.value && pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const refresh = async (probe = true) => {
  if (probe) refreshing.value = true
  try {
    const response = await platformConnectionsApi.getAll(probe)
    connections.douyin = response.data?.douyin || null
    connections.xiaohongshu = response.data?.xiaohongshu || null
    if (connections.douyin?.riskAcknowledged) douyinRiskAcknowledged.value = true
    updatePolling()
  } finally {
    refreshing.value = false
  }
}

const startLogin = async (platform) => {
  try {
    await platformConnectionsApi.startLogin(platform, {
      acknowledgedRisk: platform === 'douyin' ? douyinRiskAcknowledged.value : true,
      autoSync: true,
      limit: 20
    })
    ElMessage.success('官方登录窗口正在打开，请由账号本人扫码')
    await refresh(false)
  } catch (error) {
    // Global request handling already shows the server-provided reason.
  }
}

const goToReview = (platform) => {
  router.push({ path: '/own-content-review', query: { platform } })
}

onMounted(() => refresh(true))
onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<style lang="scss" scoped>
.connections-page { display: grid; gap: 20px; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.eyebrow { color: var(--sau-brass); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.page-heading h1 { margin: 6px 0 8px; color: var(--sau-ink); font-family: var(--sau-display-font); font-size: 34px; }
.page-heading p { max-width: 760px; margin: 0; color: var(--sau-muted); line-height: 1.7; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.steps div { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border: 1px solid var(--sau-line); border-radius: 12px; background: rgba(255, 253, 249, .74); }
.steps strong { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: var(--sau-ink); color: #fff; }
.steps span { color: var(--sau-ink); font-weight: 600; }
.platform-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.platform-card { padding: 22px; border: 1px solid var(--sau-line); border-radius: 16px; background: var(--sau-paper); box-shadow: 0 12px 30px rgba(29, 43, 58, .06); }
.platform-card__top { display: flex; align-items: flex-start; gap: 14px; }
.platform-mark { width: 48px; height: 48px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 14px; color: #fff; font-size: 20px; font-weight: 800; }
.platform-mark--douyin { background: #1d2b3a; }
.platform-mark--xiaohongshu { background: var(--sau-cinnabar); }
.platform-title { min-width: 0; flex: 1; }
.title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title-row h2 { margin: 0; color: var(--sau-ink); font-size: 19px; }
.platform-title p { margin: 7px 0 0; color: var(--sau-muted); font-size: 13px; line-height: 1.65; }
.account-panel { display: flex; align-items: center; gap: 12px; min-height: 72px; margin-top: 18px; padding: 12px 14px; border-radius: 12px; background: var(--sau-soft); }
.account-panel div { display: grid; gap: 2px; }
.account-panel span, .account-panel small { color: var(--sau-muted); font-size: 12px; }
.account-panel strong { color: var(--sau-ink); }
.account-panel--empty > .el-icon { width: 44px; height: 44px; border-radius: 50%; background: #fff; color: var(--sau-muted); font-size: 20px; }
.status-panel { display: flex; gap: 10px; margin-top: 14px; padding: 12px 14px; border: 1px solid var(--sau-line); border-radius: 12px; }
.status-panel > .el-icon { margin-top: 2px; color: var(--sau-cinnabar); font-size: 19px; }
.status-panel div { display: grid; gap: 3px; }
.status-panel strong { color: var(--sau-ink); font-size: 13px; }
.status-panel span { color: var(--sau-muted); font-size: 12px; line-height: 1.5; }
.risk-box { display: grid; gap: 6px; margin-top: 14px; padding: 12px 14px; border-radius: 12px; background: #fff7e8; }
.risk-box :deep(.el-checkbox) { height: auto; align-items: flex-start; white-space: normal; }
.risk-box :deep(.el-checkbox__label) { color: #6f531e; line-height: 1.5; white-space: normal; }
.risk-box a { width: fit-content; color: var(--sau-cinnabar); font-size: 12px; }
.card-actions { display: flex; gap: 10px; margin-top: 18px; }
.safety-card { border-radius: 14px; }
.safety-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.safety-grid div { display: flex; align-items: center; gap: 8px; color: var(--sau-ink); font-size: 13px; }
.safety-grid .el-icon { color: var(--sau-cinnabar); font-size: 18px; }
.safety-card p { margin: 14px 0 0; color: var(--sau-muted); font-size: 12px; line-height: 1.6; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 980px) {
  .platform-grid, .safety-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 720px) {
  .page-heading { display: grid; }
  .steps, .platform-grid, .safety-grid { grid-template-columns: 1fr; }
  .card-actions { flex-direction: column; }
}
</style>
