<template>
  <div class="idea-radar">
    <header class="sau-page-head">
      <span class="sau-page-icon"><el-icon><Tickets /></el-icon></span>
      <div class="sau-page-title">
        <h1>入选作品</h1>
        <p>对标账号里超过入选线的作品，和你手动加进来的，都在这里</p>
      </div>
      <div class="sau-page-counts">
        <span class="sau-badge">总数 {{ videos.length }}</span>
        <span class="sau-badge is-accent">对标 {{ sourceCounts.benchmark }}</span>
        <span v-if="freshCount" class="sau-badge is-success">新增 {{ freshCount }}</span>
      </div>
      <div class="sau-page-actions">
        <el-button :icon="Refresh" :loading="loadingVideos" @click="fetchVideos">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="manualDialog = true">手动添加</el-button>
      </div>
    </header>

    <div class="sau-page-filters">
      <el-input v-model="keyword" placeholder="搜索标题、账号、话题" clearable :prefix-icon="Search" />
      <div class="filter-line">
        <div class="sau-chips">
          <span class="sau-chip is-label"><el-icon><Filter /></el-icon>来源</span>
          <button
            v-for="item in sourceFilterOptions"
            :key="item.value"
            type="button"
            class="sau-chip"
            :class="{ 'is-active': sourceFilter === item.value }"
            @click="sourceFilter = item.value"
          >{{ item.label }} · <em>{{ sourceCounts[item.value] }}</em></button>
          <span class="chip-divider" />
          <button
            v-for="item in dayOptions"
            :key="item.value"
            type="button"
            class="sau-chip"
            :class="{ 'is-active': selectedDays === item.value }"
            @click="selectedDays = item.value; fetchVideos()"
          >{{ item.short }}</button>
          <button type="button" class="sau-chip" :class="{ 'is-active': showDeleted }" @click="showDeleted = !showDeleted; fetchVideos()">显示已删除</button>
        </div>
        <span class="result-count">当前结果 {{ filteredVideos.length }}</span>
      </div>
    </div>

    <div v-loading="loadingVideos && !videos.length" class="sau-page-body day-list">
      <section v-for="group in dayGroups" :key="group.key" class="day">
        <header class="day-head">
          <span class="day-name">{{ group.label }}</span>
          <span class="day-date">{{ group.date }}</span>
          <span class="day-line" />
          <span class="day-count">{{ group.items.length }} 条</span>
        </header>
        <TransitionGroup name="row" tag="div" class="rows" appear>
          <article
            v-for="(video, index) in group.items"
            :key="video.id"
            class="row"
            :class="{ deleted: video.deleted_at, active: detailOpen && selectedVideo?.id === video.id }"
            :style="{ '--i': index }"
            role="button"
            tabindex="0"
            @click="openDetail(video)"
            @keydown.enter="openDetail(video)"
          >
            <div class="cover" :style="coverStyle(video)">
              <img v-if="video.cover_url" :src="video.cover_url" alt="" loading="lazy" referrerpolicy="no-referrer">
              <span v-else>{{ (video.account_name || '作')[0] }}</span>
            </div>
            <div class="row-main">
              <div class="row-top">
                <span v-if="video.source_type === 'manual'" class="sau-badge">手动添加</span>
                <span v-else class="sau-badge is-accent">对标 {{ video.relative_multiple ? `${Number(video.relative_multiple).toFixed(1)}x` : '' }}</span>
                <span v-if="isFresh(video)" class="sau-badge is-success">新</span>
                <span v-if="video.deleted_at" class="sau-badge is-danger">已删除</span>
                <span class="row-title">{{ splitTitle(video.title).text || '待抓取作品' }}</span>
              </div>
              <div class="row-meta">
                <span class="row-account">{{ video.account_name || (video.source_type === 'manual' ? '手动添加' : '对标账号') }}</span>
                <span v-if="publishedLabel(video)">发布 {{ publishedLabel(video) }}</span>
                <span v-if="Number(video.like_count)">赞 {{ formatNumber(video.like_count) }}</span>
                <span v-for="tag in splitTitle(video.title).tags.slice(0, 3)" :key="tag" class="row-tag">#{{ tag }}</span>
              </div>
            </div>
            <div class="row-side">
              <span class="row-time">{{ timeLabel(video) }}</span>
              <span class="row-actions" @click.stop>
                <el-button size="small" @click="openOriginal(video.video_url)">原作品</el-button>
                <el-button size="small" @click="openVideoInspector(video)">解析视频</el-button>
                <el-button v-if="video.deleted_at" size="small" @click="restoreVideo(video)">恢复</el-button>
                <el-button v-else size="small" type="danger" plain @click="deleteVideo(video)">移出</el-button>
              </span>
            </div>
          </article>
        </TransitionGroup>
      </section>
      <el-empty v-if="!loadingVideos && !dayGroups.length" :description="videos.length ? '没有符合条件的作品' : '暂无入选作品'" :image-size="90" />
    </div>
  </div>
  <el-drawer
    v-model="detailOpen"
    size="min(760px, 94vw)"
    :with-header="false"
    class="detail-drawer"
  >
    <section class="result-panel" v-loading="analyzing">
      <div v-if="selectedVideo" class="manual-facts">
        <div class="source-bar">
          <div>
            <span class="source-account">{{ selectedVideo.account_name || (selectedVideo.source_type === 'manual' ? '手动添加' : '对标账号') }}</span>
            <h2>{{ splitTitle(selectedVideo.title).text || '待抓取作品' }}</h2>
          </div>
          <div class="source-actions">
            <el-tag :type="selectedVideo.source_type === 'manual' ? 'info' : 'success'" effect="plain" round>{{ selectedVideo.source_type === 'manual' ? '手动添加' : '对标入选' }}</el-tag>
            <el-link :href="selectedVideo.video_url" @click.prevent="openOriginal(selectedVideo.video_url)" type="primary">打开原作品</el-link>
            <el-button size="small" type="primary" @click="openVideoInspector(selectedVideo)">解析视频</el-button>
          </div>
        </div>
        <div class="metric-strip">
          <div><span>点赞</span><strong>{{ formatNumber(selectedVideo.like_count) }}</strong></div>
          <div><span>评论</span><strong>{{ formatNumber(selectedVideo.comment_count) }}</strong></div>
          <div><span>收藏</span><strong>{{ formatNumber(selectedVideo.collect_count) }}</strong></div>
          <div><span>分享</span><strong>{{ formatNumber(selectedVideo.share_count) }}</strong></div>
          <div v-if="selectedVideo.source_type !== 'manual'"><span>相对倍数</span><strong>{{ selectedVideo.relative_multiple ? `${Number(selectedVideo.relative_multiple).toFixed(1)}x` : '未提供' }}</strong></div>
        </div>
        <div v-if="taskState?.cleaned_transcript" class="section-block">
          <div class="section-label">原视频本地转写</div>
          <div class="transcript-box">{{ taskState.cleaned_transcript }}</div>
        </div>
      </div>
      <template v-if="radar && !FACTS_ONLY_MODE">
        <div class="source-bar">
          <div>
            <span class="source-account">{{ radar.source.account_name }}</span>
            <h2>{{ radar.viral_theme }}</h2>
          </div>
          <div class="source-actions">
            <el-tag v-if="selectedVideo?.hot_status" type="success" effect="plain" round>已入选</el-tag>
            <el-link :href="radar.source.video_url" @click.prevent="openOriginal(radar.source.video_url)" type="primary">打开原作品</el-link>
            <el-button size="small" type="primary" @click="openVideoInspector(selectedVideo)">解析视频</el-button>
          </div>
        </div>

        <div class="metric-strip">
          <div><span>点赞</span><strong>{{ formatNumber(selectedVideo?.like_count || radar.source.like_count) }}</strong></div>
          <div><span>评论</span><strong>{{ formatNumber(selectedVideo?.comment_count) }}</strong></div>
          <div><span>收藏</span><strong>{{ formatNumber(selectedVideo?.collect_count) }}</strong></div>
          <div><span>分享</span><strong>{{ formatNumber(selectedVideo?.share_count) }}</strong></div>
          <div><span>相对倍数</span><strong>{{ selectedVideo?.relative_multiple ? `${Number(selectedVideo.relative_multiple).toFixed(1)}x` : '未提供' }}</strong></div>
        </div>

        <div class="formula">{{ radar.formula }}</div>

        <div class="analysis-basis">
          <el-tag type="success" effect="plain">根据视频完整文案分析</el-tag>
          <span v-if="taskState?.engine">{{ taskState.engine }} · {{ taskState.model }}</span>
          <el-tag v-if="radar.agent_model" type="primary" effect="plain">
            AI：{{ radar.agent_model.name }} · {{ radar.agent_model.model }}
          </el-tag>
        </div>
        <el-alert
          v-if="radar.ai_status === 'unavailable'"
          title="本次 AI 调用未成功，当前展示本地规则降级结果。"
          :description="`模型配置仍然存在；请检查中转站响应或点击重新解析。${radar.ai_error ? `\n${radar.ai_error}` : ''}`"
          type="warning"
          :closable="false"
          show-icon
        />

        <el-collapse v-if="taskState?.progress_log?.length" class="completion-log">
          <el-collapse-item
            :title="`本次处理日志 · 用时 ${formatDuration(taskState.elapsed_seconds)}`"
            name="task-log"
          >
            <div class="log-list">
              <div
                v-for="(entry, index) in taskState.progress_log"
                :key="`${entry.time}-${index}`"
                class="log-entry"
              >
                <span class="log-time">{{ entry.time }}</span>
                <span class="log-percent">{{ entry.percent }}%</span>
                <span class="log-message">{{ entry.message }}</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>

        <div v-if="taskState?.cleaned_transcript" class="section-block">
          <el-collapse>
            <el-collapse-item title="查看视频转写文案" name="transcript">
              <div class="transcript-box">{{ taskState.cleaned_transcript }}</div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <div v-if="radar.content_breakdown" class="section-block breakdown-card">
          <div class="section-label">正文拆解</div>
          <h3>{{ radar.content_breakdown.summary }}</h3>
          <p><strong>目标人群：</strong>{{ radar.content_breakdown.target_audience }}</p>
          <p><strong>开头钩子：</strong>{{ radar.content_breakdown.hook }}</p>
          <p><strong>核心观点：</strong>{{ radar.content_breakdown.core_viewpoint }}</p>
          <div class="breakdown-grid">
            <div>
              <strong>内容结构</strong>
              <ul><li v-for="item in radar.content_breakdown.structure" :key="item">{{ item }}</li></ul>
            </div>
            <div>
              <strong>机会链路</strong>
              <ul><li v-for="item in radar.content_breakdown.opportunity_chain" :key="item">{{ item }}</li></ul>
            </div>
          </div>
        </div>

        <div class="section-block">
          <div class="section-label">反常识观点</div>
          <div class="big-viewpoint">{{ radar.contrarian_viewpoint }}</div>
        </div>

        <div class="insight-grid">
          <div class="insight-box">
            <div class="section-label">人群焦虑</div>
            <ul>
              <li v-for="item in radar.audience_anxieties" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div class="insight-box">
            <div class="section-label">可迁移方向</div>
            <ul>
              <li v-for="item in radar.migration_angles" :key="item">{{ item }}</li>
            </ul>
          </div>
        </div>

        <div class="section-block">
          <div class="section-label">证据类型</div>
          <div class="tag-row">
            <el-tag v-for="item in radar.evidence_types" :key="item" effect="plain">
              {{ item }}
            </el-tag>
          </div>
        </div>

        <div class="section-block">
          <div class="section-label">三个参考性二创方案</div>
          <div v-if="radar.adaptation_variants?.length" class="adaptation-list">
            <article v-for="(variant, index) in radar.adaptation_variants" :key="`${variant.level}-${index}`" class="adaptation-card">
              <div class="adaptation-heading"><el-tag size="small">{{ variant.level }}</el-tag><strong>{{ variant.title }}</strong></div>
              <p><b>保留：</b>{{ variant.what_to_keep }}</p>
              <p><b>改变：</b>{{ variant.what_to_change }}</p>
              <p><b>大纲：</b>{{ variant.script_outline }}</p>
            </article>
          </div>
          <div v-else class="empty-note">当前分析结果没有返回三个改编方案，请重试。</div>
        </div>

        <div class="section-block">
          <div class="section-label">对应选题标题</div>
          <div class="title-list">
            <div v-for="(title, index) in radar.recommended_titles" :key="title" class="title-item">
              <span>{{ index + 1 }}</span>
              <strong>{{ title }}</strong>
            </div>
          </div>
        </div>

        <div class="section-block">
          <div class="section-label">口播开头</div>
          <pre class="script-box">{{ radar.opening_script }}</pre>
        </div>

        <div v-if="radar.complete_script || radar.personalized_script" class="section-block">
          <div class="section-label">完整可修改脚本</div>
          <pre class="script-box">{{ radar.complete_script || radar.personalized_script }}</pre>
        </div>
      </template>

      <div v-else-if="taskState && !['idle', 'success', 'complete'].includes(taskState.status)" class="task-state-card">
        <template v-if="taskState.status === 'failed'">
          <el-result icon="error" title="视频解析失败" :sub-title="taskState.error_message || '请重新解析'">
            <template #extra>
              <el-space>
                <el-button type="primary" @click="retrySelectedVideo">重新解析</el-button>
                <el-button
                  v-if="selectedVideo?.source_type === 'manual'"
                  @click="repairDialog = true"
                >更新链接</el-button>
              </el-space>
            </template>
          </el-result>
          <el-alert
            v-if="taskState.analysis_basis === 'title_only'"
            title="尚未获得视频正文，当前不会生成完整拆解。"
            type="warning"
            :closable="false"
          />
        </template>
        <template v-else>
          <div class="progress-header">
            <div>
              <div class="progress-stage">{{ stageLabel }}</div>
              <div class="progress-message">
                {{ taskState.progress_message || '任务正在后台处理' }}
              </div>
            </div>
            <strong>{{ taskProgress }}%</strong>
          </div>
          <el-progress
            :percentage="taskProgress"
            :stroke-width="12"
            :show-text="false"
            striped
            striped-flow
          />
          <div class="progress-meta">
            <span>已用时 {{ formatDuration(taskState.elapsed_seconds) }}</span>
            <span v-if="taskState.engine">{{ taskState.engine }} · {{ taskState.model }}</span>
          </div>
        </template>

        <div v-if="taskState.progress_log?.length" class="task-log">
          <div class="task-log-title">运行日志</div>
          <div class="log-list">
            <div
              v-for="(entry, index) in taskState.progress_log"
              :key="`${entry.time}-${index}`"
              class="log-entry"
            >
              <span class="log-time">{{ entry.time }}</span>
              <span class="log-percent">{{ entry.percent }}%</span>
              <span class="log-message">{{ entry.message }}</span>
            </div>
          </div>
        </div>
      </div>

      <el-empty
        v-else-if="!analyzing"
        description="选择一条对标作品查看公开事实"
        :image-size="110"
      />
    </section>
  </el-drawer>
  <el-dialog v-model="manualDialog" title="手动添加作品" width="520px">
    <el-form @submit.prevent="addManualVideo">
      <el-form-item label="作品链接"><el-input v-model="manualUrl" placeholder="粘贴任意 yt-dlp 支持的平台链接或完整分享文本" /></el-form-item>
      <p class="dialog-note">添加后会进入“手动添加”，不参与中位数和入选倍数判断；选择作品后可下载原视频并用本地 Whisper 转写。</p>
    </el-form>
    <template #footer><el-button @click="manualDialog=false">取消</el-button><el-button type="primary" :loading="addingManual" @click="addManualVideo">添加作品</el-button></template>
  </el-dialog>
  <el-dialog v-model="repairDialog" title="更新作品链接" width="520px">
    <el-form @submit.prevent="repairManualVideo">
      <el-form-item label="作品链接">
        <el-input v-model="repairUrl" placeholder="粘贴包含 http:// 或 https:// 的完整分享文本（支持 yt-dlp 平台）" />
      </el-form-item>
      <p class="dialog-note">更新后会清除本条作品的失败记录，并立即在本机重新下载和转写。</p>
    </el-form>
    <template #footer>
      <el-button @click="repairDialog = false">取消</el-button>
      <el-button type="primary" :loading="repairingManual" @click="repairManualVideo">更新并重试</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Filter, Plus, Refresh, Search, Tickets } from '@element-plus/icons-vue'
import { benchmarkApi } from '@/api/benchmark'
import { systemApi } from '@/api/videoJiexi'
import { useRouter } from 'vue-router'

const videos = ref([])
const selectedVideo = ref(null)
const radar = ref(null)
const taskState = ref(null)
const keyword = ref('')
const sourceFilter = ref(localStorage.getItem('ideaRadarSourceFilter') || 'all')
const showDeleted = ref(false)
const sourceFilterOptions = [
  { label: '全部', value: 'all' },
  { label: '对标入选', value: 'benchmark' },
  { label: '手动添加', value: 'manual' },
]
const manualDialog = ref(false)
const manualUrl = ref('')
const addingManual = ref(false)
const repairDialog = ref(false)
const repairUrl = ref('')
const repairingManual = ref(false)
const savedDays = Number(localStorage.getItem('ideaRadarDays') || 0)
const selectedDays = ref(Number.isFinite(savedDays) ? Math.min(90, Math.max(0, savedDays)) : 0)
const dayOptions = computed(() => {
  const values = [0, 7, 30, 90]
  if (!values.includes(selectedDays.value)) values.push(selectedDays.value)
  return values.sort((a, b) => a - b).map((value) => ({ value, label: value ? `近 ${value} 天发布` : '不限发布时间', short: value ? `近 ${value} 天` : '不限时间' }))
})
const detailOpen = ref(false)
// 上次离开本页的时间；此后入选的作品标记为新增。
const LAST_SEEN_KEY = 'ideaRadarLastSeenAt'
const lastSeenAt = Number(localStorage.getItem(LAST_SEEN_KEY) || 0)
const loadingVideos = ref(false)
const analyzing = ref(false)
const FACTS_ONLY_MODE = true
const router = useRouter()
let pollingTimer = null
let selectionToken = 0

const stageLabels = {
  pending: '等待解析',
  downloading: '正在下载视频',
  transcribing: '正在识别视频文案',
  analyzing: '正在拆解正文和分析机会',
  complete: '解析完成'
}

const stageLabel = computed(() => stageLabels[taskState.value?.stage] || '正在处理')
const taskProgress = computed(() => Math.max(0, Math.min(Number(taskState.value?.progress_percent || 0), 100)))

const filteredVideos = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return videos.value.filter((video) => {
    if (sourceFilter.value !== 'all' && (video.source_type || 'benchmark') !== sourceFilter.value) return false
    if (!q) return true
    return `${video.title || ''} ${video.account_name || ''}`.toLowerCase().includes(q)
  })
})

// 后端时间不带时区时按 UTC 存储（SQLite CURRENT_TIMESTAMP），与后端解析规则保持一致。
const parseTime = (value) => {
  if (!value) return null
  const text = String(value).trim().replace(' ', 'T')
  const date = new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(text) ? text : `${text}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

const rawData = (video) => {
  try { return JSON.parse(video.raw_data || '{}') || {} } catch { return {} }
}

const publishedAt = (video) => {
  const raw = rawData(video)
  return parseTime(raw.monitor_work?.published_at || raw.published_at)
}

const pad = (n) => String(n).padStart(2, '0')
const dayKey = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const WEEKDAYS = '日一二三四五六'

const dayGroups = computed(() => {
  const today = new Date()
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  const groups = new Map()
  const sorted = [...filteredVideos.value].sort((a, b) =>
    (parseTime(b.created_at)?.getTime() || 0) - (parseTime(a.created_at)?.getTime() || 0) || b.id - a.id)
  for (const video of sorted) {
    const entered = parseTime(video.created_at)
    const key = entered ? dayKey(entered) : 'unknown'
    if (!groups.has(key)) {
      let label = '入选时间未知'
      let date = ''
      if (entered) {
        const startOfDay = new Date(entered.getFullYear(), entered.getMonth(), entered.getDate()).getTime()
        const diff = Math.round((todayStart - startOfDay) / 86400000)
        label = diff === 0 ? '今天' : diff === 1 ? '昨天' : diff < 7 ? `${diff} 天前` : `${entered.getMonth() + 1}月${entered.getDate()}日`
        date = `${entered.getMonth() + 1}月${entered.getDate()}日 · 周${WEEKDAYS[entered.getDay()]}`
        if (entered.getFullYear() !== today.getFullYear()) date = `${entered.getFullYear()}年${date}`
      }
      groups.set(key, { key, label, date, items: [] })
    }
    groups.get(key).items.push(video)
  }
  return [...groups.values()]
})

const isFresh = (video) => Boolean(lastSeenAt) && (parseTime(video.created_at)?.getTime() || 0) > lastSeenAt
const freshCount = computed(() => videos.value.filter((video) => !video.deleted_at && isFresh(video)).length)

const timeLabel = (video) => {
  const entered = parseTime(video.created_at)
  return entered ? `${pad(entered.getHours())}:${pad(entered.getMinutes())}` : ''
}

const publishedLabel = (video) => {
  const date = publishedAt(video)
  if (!date) return ''
  const year = date.getFullYear() !== new Date().getFullYear() ? `${date.getFullYear()}年` : ''
  return `${year}${date.getMonth() + 1}月${date.getDate()}日`
}

// 抖音标题常带一串话题标签；正文和标签拆开显示，正文为空时用标签兜底。
const splitTitle = (title) => {
  const text = String(title || '')
  const tags = [...text.matchAll(/#([^#\s]+)/g)].map((m) => m[1])
  const body = text.replace(/#[^#\s]+/g, ' ').replace(/\s+/g, ' ').trim()
  return { text: body || tags.join(' · '), tags: body ? [...new Set(tags)] : [] }
}

const COVER_TINTS = ['#c9a27a, #8c6845', '#9aa58a, #5f6b4e', '#a3b2bb, #627580', '#c49a8a, #87594a', '#b2a2c4, #6e5f85', '#cdb489, #8e7547']
const coverStyle = (video) => {
  if (video.cover_url) return {}
  const seed = [...String(video.account_name || video.id)].reduce((sum, ch) => sum + ch.charCodeAt(0), 0)
  return { background: `linear-gradient(160deg, ${COVER_TINTS[seed % COVER_TINTS.length]})` }
}

const sourceCounts = computed(() => {
  const counts = { all: 0, benchmark: 0, manual: 0 }
  for (const video of videos.value) {
    counts.all += 1
    counts[video.source_type === 'manual' ? 'manual' : 'benchmark'] += 1
  }
  return counts
})

watch(selectedDays, (value) => {
  localStorage.setItem('ideaRadarDays', String(value))
})
watch(sourceFilter, (value) => localStorage.setItem('ideaRadarSourceFilter', value))

const formatNumber = (value) => {
  const n = Number(value || 0)
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString()
}

const formatDuration = (seconds) => {
  const value = Math.max(0, Number(seconds || 0))
  const minutes = Math.floor(value / 60)
  const remainingSeconds = Math.floor(value % 60)
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    return `${hours}小时${minutes % 60}分${remainingSeconds}秒`
  }
  return minutes ? `${minutes}分${remainingSeconds}秒` : `${remainingSeconds}秒`
}

const fetchVideos = async () => {
  loadingVideos.value = true
  try {
    const res = await benchmarkApi.getIdeaRadarVideos(100, selectedDays.value, showDeleted.value)
    videos.value = res.data || []
    if (selectedVideo.value && !videos.value.some((video) => video.id === selectedVideo.value.id)) {
      closeDetail()
    }
  } catch (error) {
    console.error('获取对标作品失败:', error)
    ElMessage.error('获取对标作品失败')
  } finally {
    loadingVideos.value = false
  }
}

const restoreVideo = async (video) => {
  try {
    await benchmarkApi.restoreIdeaRadarVideo(video.id)
    ElMessage.success('作品已恢复')
    await fetchVideos()
  } catch (error) { ElMessage.error(error?.message || '恢复作品失败') }
}

const addManualVideo = async () => {
  if (!manualUrl.value.trim()) return ElMessage.warning('请先粘贴作品链接')
  addingManual.value = true
  try {
    const res = await benchmarkApi.addManualIdeaRadarVideo(manualUrl.value.trim())
    const addedId = res.data?.id
    manualDialog.value = false
    manualUrl.value = ''
    await fetchVideos()
    const addedVideo = videos.value.find((video) => video.id === addedId)
    if (addedVideo) await selectVideo(addedVideo)
    ElMessage.success('已添加到手动添加')
  } catch (error) { ElMessage.error(error?.message || '添加作品失败') }
  finally { addingManual.value = false }
}

const deleteVideo = async (video) => {
  const wasSelected = selectedVideo.value?.id === video.id
  try {
    await benchmarkApi.deleteIdeaRadarVideo(video.id)
    videos.value = videos.value.filter((item) => item.id !== video.id)
    if (wasSelected) closeDetail()
    ElMessage.success('作品已移出')
  } catch (error) {
    ElMessage.error(error?.message || '删除作品失败')
  }
}

const repairManualVideo = async () => {
  if (!selectedVideo.value || selectedVideo.value.source_type !== 'manual') return
  if (!repairUrl.value.trim()) return ElMessage.warning('请粘贴完整的作品分享文本')
  repairingManual.value = true
  try {
    const videoId = selectedVideo.value.id
    const token = ++selectionToken
    stopPolling()
    const res = await benchmarkApi.replaceManualIdeaRadarVideoUrl(
      videoId,
      repairUrl.value.trim(),
    )
    if (token !== selectionToken || selectedVideo.value?.id !== videoId) return
    selectedVideo.value = { ...selectedVideo.value, ...(res.data?.video || {}) }
    videos.value = videos.value.map((item) => item.id === selectedVideo.value.id ? selectedVideo.value : item)
    applyTaskState(res.data?.task)
    repairDialog.value = false
    repairUrl.value = ''
    if (['pending', 'processing'].includes(res.data?.task?.status)) {
      startPolling(selectedVideo.value.id, token)
    }
    ElMessage.success('链接已更新，正在本机重新解析')
  } catch (error) {
    ElMessage.error(error?.message || '更新作品链接失败')
  } finally {
    repairingManual.value = false
  }
}

const retrySelectedVideo = async () => {
  if (!selectedVideo.value) return
  const videoId = selectedVideo.value.id
  const token = ++selectionToken
  stopPolling()
  analyzing.value = true
  try {
    const res = await benchmarkApi.analyzeIdeaRadarVideo(videoId, {
      force: true,
      forceTranscription: true,
    })
    if (token !== selectionToken || selectedVideo.value?.id !== videoId) return
    applyTaskState(res.data)
    if (['pending', 'processing'].includes(res.data?.status)) startPolling(videoId, token)
  } finally {
    analyzing.value = false
  }
}

const selectVideo = async (video) => {
  selectionToken += 1
  const token = selectionToken
  stopPolling()
  selectedVideo.value = video
  radar.value = null
  taskState.value = null
  analyzing.value = true
  try {
    const res = await benchmarkApi.getIdeaRadarStatus(video.id)
    if (token !== selectionToken) return
    applyTaskState(res.data)
    if (!res.data?.cleaned_transcript && res.data?.status === 'idle') {
      const task = await benchmarkApi.analyzeIdeaRadarVideo(video.id, { forceTranscription: true })
      if (token !== selectionToken) return
      applyTaskState(task.data)
      if (['pending', 'processing'].includes(task.data?.status)) startPolling(video.id, token)
    } else if (['pending', 'processing'].includes(res.data?.status)) {
      startPolling(video.id, token)
    }
  } catch (error) {
    console.error('获取作品事实数据失败:', error)
    ElMessage.error('获取作品事实数据失败')
  } finally {
    analyzing.value = false
  }
}

const applyTaskState = (state) => {
  taskState.value = state || null
  radar.value = state?.status === 'success' ? state.radar_json : null
}

const stopPolling = () => {
  if (pollingTimer) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

const startPolling = (videoId, token) => {
  stopPolling()
  pollingTimer = setTimeout(async () => {
    try {
      const res = await benchmarkApi.getIdeaRadarStatus(videoId)
      if (token !== selectionToken) return
      applyTaskState(res.data)
      if (!['success', 'failed'].includes(res.data?.status)) {
        startPolling(videoId, token)
      }
    } catch (error) {
      if (token === selectionToken) startPolling(videoId, token)
    }
  }, 2000)
}

const openDetail = (video) => {
  detailOpen.value = true
  if (selectedVideo.value?.id !== video.id || !taskState.value) selectVideo(video)
}

const closeDetail = () => {
  detailOpen.value = false
  stopPolling()
  selectionToken += 1
  selectedVideo.value = null
  radar.value = null
  taskState.value = null
}

// 抽屉收起后不再轮询；再次打开同一条作品会重新读取状态。
watch(detailOpen, (open) => {
  if (!open) {
    stopPolling()
    selectionToken += 1
    taskState.value = null
  }
})

const openVideoInspector = (video) => {
  const sourceUrl = video?.video_url || radar.value?.source?.video_url || selectedVideo.value?.video_url
  if (!sourceUrl) {
    ElMessage.warning('原作品链接缺失，暂时无法进入视频解析')
    return
  }
  router.push({ path: '/video-inspector', query: { url: sourceUrl } })
}

const openOriginal = async (url) => {
  if (!url) {
    ElMessage.warning('原作品链接缺失')
    return
  }
  try {
    await systemApi.openUrl(url)
  } catch (error) {
    // Keep a browser fallback for remote deployments where the backend cannot launch a local app.
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

onMounted(fetchVideos)
onBeforeUnmount(() => {
  stopPolling()
  localStorage.setItem(LAST_SEEN_KEY, String(Date.now()))
})
</script>

<style lang="scss" scoped>
.idea-radar { min-height: 100%; }

.filter-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chip-divider {
  width: 1px;
  height: 16px;
  margin: 0 2px;
  background: var(--sau-line);
}

.result-count {
  flex: none;
  color: var(--sau-muted);
  font-size: 11px;
}

.day-list { min-height: 240px; }

.day { margin-bottom: 22px; }

.day-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 2px 8px;
}

.day-name { color: var(--sau-ink); font-size: 13px; font-weight: 600; }
.day-date { color: var(--sau-muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.day-line { flex: 1; height: 1px; background: var(--sau-divider); }
.day-count { color: var(--sau-muted); font-size: 11px; }

.rows {
  overflow: hidden;
  border: 1px solid var(--sau-line);
  border-radius: 12px;
  background: var(--sau-paper);
}

.row {
  position: relative;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 9px 14px 9px 10px;
  cursor: pointer;
  outline: none;
  transition: background-color 160ms ease;

  & + & { border-top: 1px solid var(--sau-divider); }

  &:hover,
  &:focus-visible { background: var(--sau-paper-muted); }

  &.active { background: var(--sau-accent-soft); }

  &.active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 10px;
    bottom: 10px;
    width: 2px;
    border-radius: 0 2px 2px 0;
    background: var(--sau-accent);
  }

  &.deleted { opacity: 0.5; }
}

.row-enter-active {
  transition: opacity 240ms ease, transform 280ms var(--sau-ease-out);
  transition-delay: calc(min(var(--i), 10) * 25ms);
}
.row-leave-active { transition: opacity 180ms ease; }
.row-enter-from { opacity: 0; transform: translateY(6px); }
.row-leave-to { opacity: 0; }

.cover {
  position: relative;
  display: grid;
  place-items: center;
  width: 40px;
  height: 52px;
  overflow: hidden;
  border-radius: 6px;
  background: var(--sau-soft);
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  font-weight: 600;

  img { width: 100%; height: 100%; object-fit: cover; }
}

.row-main { min-width: 0; }

.row-top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.row-title {
  min-width: 0;
  overflow: hidden;
  color: var(--sau-ink);
  font-size: 13px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 5px;
  color: var(--sau-muted);
  font-size: 11px;
}

.row-account { color: var(--sau-ink-soft); }
.row-tag { color: var(--sau-muted); }

.row-side {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 44px;
}

.row-time {
  color: var(--sau-muted);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  transition: opacity 120ms ease;
}

.row-actions {
  position: absolute;
  right: 0;
  top: 50%;
  display: flex;
  gap: 6px;
  padding-left: 28px;
  background: linear-gradient(to right, transparent, var(--sau-paper-muted) 24px);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-50%);
  transition: opacity 140ms ease;

  .el-button + .el-button { margin-left: 0; }
}

.row:hover,
.row:focus-within {
  .row-actions { opacity: 1; pointer-events: auto; }
  .row-time { opacity: 0; }
}

.row.active .row-actions { background: linear-gradient(to right, transparent, var(--sau-accent-soft) 24px); }

.detail-drawer :deep(.el-drawer__body) { padding: 0; }

.result-panel {
  min-height: 100%;
  padding: 24px;
}

.source-bar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;

  h2 {
    margin: 4px 0 0;
    font-size: 24px;
    color: var(--sau-ink);
  }
}

.source-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.metric-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin: 4px 0 18px;

  > div {
    padding: 10px 12px;
    border: 1px solid var(--sau-line);
    border-radius: 8px;
    background: var(--sau-paper-muted);
    display: grid;
    gap: 4px;
  }

  span { color: var(--sau-ink-soft); font-size: 12px; }
  strong { color: var(--sau-ink); font-size: 16px; }
}

.source-account {
  color: var(--sau-ink-soft);
  font-size: 13px;
}

.formula {
  display: inline-flex;
  padding: 8px 12px;
  background: var(--sau-ink);
  color: #fff;
  border-radius: 6px;
  font-size: 13px;
  margin-bottom: 18px;
}

.analysis-basis {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--sau-ink-soft);
  font-size: 13px;
  margin-bottom: 16px;
}

.transcript-box {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--sau-ink);
  max-height: 360px;
  overflow: auto;
  padding: 4px 8px 12px;
}

.completion-log {
  margin-bottom: 18px;
}

.breakdown-card {
  border: 1px solid var(--sau-line);
  background: var(--sau-warm-soft);
  border-radius: 8px;
  padding: 16px;

  h3 {
    margin: 0 0 12px;
    color: var(--sau-ink);
  }

  p {
    color: var(--sau-ink);
    line-height: 1.7;
  }
}

.breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;

  ul {
    margin: 8px 0 0;
    padding-left: 18px;
  }

  li {
    margin-bottom: 6px;
    line-height: 1.6;
    color: var(--sau-ink);
  }
}

.task-state-card {
  min-height: 440px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 760px;
  margin: 0 auto;
}

.progress-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 14px;

  strong {
    color: var(--sau-ink);
    font-size: 28px;
  }
}

.progress-stage {
  color: var(--sau-ink);
  font-size: 20px;
  font-weight: 650;
}

.progress-message {
  margin-top: 6px;
  color: var(--sau-ink-soft);
  font-size: 14px;
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 10px;
  color: var(--sau-ink-soft);
  font-size: 13px;
}

.task-log {
  margin-top: 24px;
  border-top: 1px solid var(--sau-line);
  padding-top: 16px;
}

.task-log-title {
  margin-bottom: 10px;
  color: var(--sau-ink);
  font-size: 14px;
  font-weight: 650;
}

.log-list {
  max-height: 240px;
  overflow-y: auto;
  font-size: 13px;
}

.log-entry {
  display: grid;
  grid-template-columns: 70px 48px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid var(--sau-line);
}

.log-time,
.log-percent {
  color: var(--sau-muted);
  font-variant-numeric: tabular-nums;
}

.log-message {
  min-width: 0;
  color: var(--sau-ink);
  overflow-wrap: anywhere;
}

.section-block {
  margin-top: 18px;
}

.section-label {
  font-size: 13px;
  font-weight: 650;
  color: var(--sau-ink-soft);
  margin-bottom: 8px;
}

.big-viewpoint {
  font-size: 20px;
  line-height: 1.55;
  color: var(--sau-ink);
  font-weight: 650;
  padding: 16px;
  background: var(--sau-paper-muted);
  border-left: 4px solid var(--sau-cinnabar);
  border-radius: 8px;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.insight-box {
  border: 1px solid var(--sau-line);
  border-radius: 8px;
  padding: 14px;

  ul {
    margin: 0;
    padding-left: 18px;
  }

  li {
    color: var(--sau-ink);
    line-height: 1.7;
    margin-bottom: 5px;
  }
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.title-list {
  display: grid;
  gap: 10px;
}

.adaptation-list {
  display: grid;
  gap: 12px;
}

.adaptation-card {
  border: 1px solid var(--sau-line);
  border-radius: 10px;
  padding: 14px;
  background: var(--sau-paper);

  p {
    margin: 8px 0 0;
    color: var(--sau-ink-soft);
    line-height: 1.65;
  }
}

.adaptation-heading {
  display: flex;
  align-items: center;
  gap: 10px;

  strong { color: var(--sau-ink); line-height: 1.5; }
}

.empty-note {
  padding: 14px;
  border: 1px dashed var(--sau-line);
  border-radius: 8px;
  color: var(--sau-ink-soft);
}

.title-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--sau-line);
  border-radius: 8px;
  background: var(--sau-paper);

  span {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--sau-cinnabar);
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    font-size: 12px;
  }

  strong {
    color: var(--sau-ink);
    line-height: 1.55;
  }
}

.script-box {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 14px;
  border-radius: 6px;
  background: var(--sau-ink);
  color: #f9fafb;
  font-family: inherit;
  line-height: 1.7;
}

@media (max-width: 980px) {
  .insight-grid,
  .breakdown-grid {
    grid-template-columns: 1fr;
  }

  .idea-radar .page-header {
    display: block;
  }

  .idea-radar .header-actions {
    margin-top: 12px;
  }

  .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .sau-page-counts { display: none; }
  .filter-line { flex-direction: column; align-items: flex-start; }
  .row { grid-template-columns: 36px minmax(0, 1fr); }
  .cover { width: 36px; height: 46px; }
  .row-side { grid-column: 1 / -1; justify-content: flex-start; }
  .row-actions { position: static; flex-wrap: wrap; padding-left: 0; background: none; opacity: 1; pointer-events: auto; transform: none; }
  .row-time { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .row, .row-actions, .row-enter-active, .row-leave-active { transition: none; }
}
</style>
