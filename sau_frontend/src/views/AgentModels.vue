<template>
  <div class="agent-models-page">
    <header class="page-header">
      <div><p class="eyebrow">Workspace Settings</p><h1>设置</h1><p>{{ factsOnlyMode ? '配置采集服务和视频解析服务；当前不启用 AI 分析或文案改写。' : '配置采集服务、视频解析服务和 AI 模型；发布由独立工具负责。' }}</p></div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </header>

    <section v-if="factsOnlyMode" class="settings-section facts-mode-notice">
      <div class="section-heading">
        <div><h2>事实模式已启用</h2><p>AI 分析和文案改写目前不参与流程，已有模型配置仍会保留。</p></div>
        <el-button @click="showAiSettings = !showAiSettings">{{ showAiSettings ? '收起 AI 配置' : '展开 AI 配置' }}</el-button>
      </div>
    </section>

    <section v-if="!factsOnlyMode || showAiSettings" class="settings-section local-ai-section">
      <div class="section-heading">
        <div><h2>本机 Codex AI（可选）</h2><p>复用当前电脑已经登录的 Codex CLI；不启用也不影响通用 AI 模型服务。</p></div>
        <el-tag :type="codexStatus.type" effect="plain">{{ codexStatus.label }}</el-tag>
      </div>
      <div class="local-ai-grid">
        <div><span>CLI 版本</span><strong>{{ codexCli.version || '未检测到' }}</strong></div>
        <div><span>登录状态</span><strong>{{ codexCli.authenticated ? '已通过 ChatGPT 登录' : '未登录' }}</strong></div>
        <div><span>分析模型</span><el-input v-model="codexModel" placeholder="gpt-5.6-sol" /></div>
      </div>
      <div class="section-actions">
        <el-button type="primary" :disabled="!codexCli.available || !codexCli.authenticated" :loading="configuringCodex" @click="configureCodex">
          {{ codexCli.selectedForViralAnalysis ? '更新并继续使用' : '设为爆款拆解模型' }}
        </el-button>
        <span v-if="!codexCli.available" class="inline-help">未安装时仍可使用下方通用 AI 服务，或保持本地规则降级。</span>
        <span v-else-if="!codexCli.authenticated" class="inline-help">请先在终端运行 codex login。</span>
      </div>
    </section>

    <section v-if="!factsOnlyMode || showAiSettings" class="settings-section universal-ai-section">
      <div class="section-heading">
        <div><h2>通用 AI 模型服务</h2><p>可连接不同厂商、中转站或本地模型服务，不依赖 ChatGPT/Codex 登录；连接信息只保存在当前电脑。</p></div>
        <el-tag :type="connectionStatus.type" effect="plain">{{ connectionStatus.label }}</el-tag>
      </div>
      <el-form :model="aiForm" label-position="top" class="connection-form universal-ai-form">
        <el-form-item label="厂商名称"><el-input v-model="aiForm.providerName" placeholder="例如：DeepSeek、Claude、自建中转站" /></el-form-item>
        <el-form-item label="接口协议">
          <el-select v-model="aiForm.protocol">
            <el-option label="OpenAI 兼容协议" value="openai-compatible" />
            <el-option label="Anthropic 原生协议" value="anthropic" />
            <el-option label="Google Gemini 原生协议" value="gemini" />
          </el-select>
        </el-form-item>
        <el-form-item label="API 地址"><el-input v-model="aiForm.baseUrl" :placeholder="apiUrlPlaceholder" /></el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="aiForm.apiKey" type="password" show-password :placeholder="aiForm.apiKeyConfigured ? '已配置，留空保持不变' : '填写该厂商提供的 Key'" />
        </el-form-item>
        <el-form-item label="模型名"><el-input v-model="aiForm.model" placeholder="填写厂商实际模型 ID" /></el-form-item>
        <el-form-item label="超时（秒）"><el-input-number v-model="aiForm.timeout" :min="10" :max="1800" :step="10" /></el-form-item>
      </el-form>
      <div class="section-actions">
        <el-button type="primary" :loading="savingIndependent" @click="saveIndependent">保存并用于爆款拆解</el-button>
        <el-button :loading="testingIndependent" @click="testIndependent">测试模型</el-button>
      </div>
      <p class="secret-note">DeepSeek、通义、智谱、Moonshot、OpenRouter 和多数中转站可优先选择 OpenAI 兼容协议；Claude、Gemini 也可选择原生协议。API Key 不会显示在页面响应中，也不会进入 Git。</p>
    </section>

    <section class="settings-section">
      <div class="section-heading"><div><h2>可选外部能力服务</h2><p>不配置也不影响基础账号管理和公开数据采集；地址可指向本机、局域网或公网服务。</p></div><el-tag :type="integrationStatus.type" effect="plain">{{ integrationStatus.label }}</el-tag></div>
      <el-form :model="integrationForm" label-position="top" class="connection-form integration-form">
        <el-form-item label="OpenCLI Admin 地址"><el-input v-model="integrationForm.opencliAdminBaseUrl" placeholder="https://collector.example.com/api/v1" /></el-form-item>
        <el-form-item label="OpenCLI Admin Token"><el-input v-model="integrationForm.opencliAdminApiToken" type="password" show-password :placeholder="integrationForm.opencliAdminApiTokenConfigured ? '已配置，留空保持不变' : '可选 Bearer Token'" /></el-form-item>
        <el-form-item label="视频解析服务地址"><el-input v-model="integrationForm.videoJiexiBaseUrl" placeholder="https://parser.example.com" /></el-form-item>
        <el-form-item label="视频解析服务 Token"><el-input v-model="integrationForm.videoJiexiApiToken" type="password" show-password :placeholder="integrationForm.videoJiexiApiTokenConfigured ? '已配置，留空保持不变' : '可选 Bearer Token'" /></el-form-item>
        <el-form-item label="共享目录回退（可选）"><el-input v-model="integrationForm.videoJiexiDownloadDir" placeholder="仅在服务没有文件接口时填写" /></el-form-item>
      </el-form>
      <div class="section-actions"><el-button type="primary" :loading="savingIntegrations" @click="saveIntegrations">保存集成配置</el-button><el-button :loading="testingIntegration" @click="testIntegration">检查视频解析服务</el-button></div>
    </section>

    <section v-if="!factsOnlyMode || showAiSettings" class="settings-section">
      <div class="section-heading">
        <div><h2>模型配置</h2><p>上方快捷配置会自动创建模型；这里保留高级手动配置。</p></div>
        <el-button type="primary" :icon="Plus" @click="openEditor()">添加模型</el-button>
      </div>
      <el-table :data="models" v-loading="loading" empty-text="还没有配置 Agent 模型">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="provider" label="Provider" min-width="130" />
        <el-table-column prop="model" label="Model" min-width="220" show-overflow-tooltip />
        <el-table-column label="推理" width="90"><template #default="s">{{ s.row.reasoningEffort || '默认' }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="s"><el-tag :type="s.row.enabled ? 'success' : 'info'" effect="plain">{{ s.row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="210" fixed="right"><template #default="s">
          <el-button link type="primary" :loading="testingModelId === s.row.id" @click="testModel(s.row)">测试</el-button>
          <el-button link @click="openEditor(s.row)">编辑</el-button>
          <el-button link type="danger" @click="removeModel(s.row)">删除</el-button>
        </template></el-table-column>
      </el-table>
    </section>

    <section v-if="!factsOnlyMode || showAiSettings" class="settings-section">
      <div class="section-heading"><div><h2>任务模型</h2><p>开始新任务时读取，切换不会改变历史结果。</p></div></div>
      <div class="task-row">
        <div><strong>爆款拆解</strong><span>正文结构、传播机制与内容机会</span></div>
        <el-select v-model="taskModels.viralAnalysis" placeholder="选择 Agent 模型" clearable>
          <el-option v-for="item in enabledModels" :key="item.id" :label="`${item.name} · ${item.model}`" :value="item.id" />
        </el-select>
        <el-button type="primary" :loading="savingTask" @click="saveTaskModel">保存</el-button>
      </div>
    </section>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑 Agent 模型' : '添加 Agent 模型'" width="560px">
      <el-form :model="editor" label-position="top">
        <el-form-item v-if="discoveredModels.length" label="服务模型目录">
          <el-select v-model="catalogSelection" filterable clearable placeholder="选择后自动填写" @change="applyCatalogModel">
            <el-option v-for="item in discoveredModels" :key="`${item.provider}:${item.model}`" :label="`${item.provider} · ${item.name}`" :value="`${item.provider}\n${item.model}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称"><el-input v-model="editor.name" placeholder="例如：高质量拆解" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Provider"><el-input v-model="editor.provider" placeholder="例如：openrouter" /></el-form-item>
          <el-form-item label="Model"><el-input v-model="editor.model" placeholder="模型 ID" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="推理强度"><el-select v-model="editor.reasoningEffort"><el-option label="服务默认" value="" /><el-option label="Low" value="low" /><el-option label="Medium" value="medium" /><el-option label="High" value="high" /></el-select></el-form-item>
          <el-form-item label="服务等级"><el-input v-model="editor.serviceTier" placeholder="留空使用默认" /></el-form-item>
        </div>
        <el-form-item label="启用"><el-switch v-model="editor.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editorVisible = false">取消</el-button><el-button type="primary" :loading="savingModel" @click="saveModel">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { agentModelsApi } from '@/api/agentModels'
import { integrationsApi } from '@/api/integrations'

const loading = ref(false), savingIndependent = ref(false), testingIndependent = ref(false)
const discovering = ref(false), savingModel = ref(false), savingTask = ref(false)
const configuringCodex = ref(false), codexModel = ref('gpt-5.6-sol')
const testingModelId = ref(''), editorVisible = ref(false), editingId = ref(''), catalogSelection = ref('')
const factsOnlyMode = ref(false), showAiSettings = ref(false)
const savingIntegrations = ref(false), testingIntegration = ref(false)
const models = ref([]), discoveredModels = ref([])
const taskModels = reactive({ viralAnalysis: '' })
const connectionStatus = reactive({ type: 'info', label: '未测试' })
const codexStatus = reactive({ type: 'info', label: '正在检测' })
const codexCli = reactive({ available: false, authenticated: false, configured: false, selectedForViralAnalysis: false, version: '', model: null })
const integrationStatus = reactive({ type: 'info', label: '未检查' })
const aiForm = reactive({ providerName: '自定义 AI', protocol: 'openai-compatible', baseUrl: '', apiKey: '', apiKeyConfigured: false, model: 'gpt-5.6-sol', timeout: 300 })
const integrationForm = reactive({ opencliAdminBaseUrl: '', opencliAdminApiToken: '', opencliAdminApiTokenConfigured: false, videoJiexiBaseUrl: '', videoJiexiApiToken: '', videoJiexiApiTokenConfigured: false, videoJiexiDownloadDir: '' })
const emptyEditor = () => ({ name: '', provider: '', model: '', reasoningEffort: '', serviceTier: '', enabled: true })
const editor = reactive(emptyEditor())
const enabledModels = computed(() => models.value.filter((item) => item.enabled))
const apiUrlPlaceholder = computed(() => ({
  anthropic: '例如：https://api.anthropic.com/v1',
  gemini: '例如：https://generativelanguage.googleapis.com/v1beta',
}[aiForm.protocol] || '例如：https://你的服务域名/v1'))

const flattenCatalog = (payload) => {
  const found = new Map()
  const walk = (value, inherited = '') => {
    if (Array.isArray(value)) return value.forEach((item) => walk(item, inherited))
    if (!value || typeof value !== 'object') return
    const provider = String(value.provider || value.provider_id || value.slug || inherited || '')
    if (Array.isArray(value.models)) value.models.forEach((item) => {
      const model = typeof item === 'string' ? item : String(item?.id || item?.model || item?.name || '')
      const name = typeof item === 'string' ? item : String(item?.name || item?.label || model)
      if (provider && model) found.set(`${provider}:${model}`, { provider, model, name })
    })
    Object.values(value).forEach((item) => walk(item, provider))
  }
  walk(payload)
  return [...found.values()]
}

const loadAll = async () => {
  loading.value = true
  try {
    const [codex, universal, configured, integrations] = await Promise.all([agentModelsApi.getCodexCliStatus(), agentModelsApi.getUniversalAISettings(), agentModelsApi.getAgentModels(), integrationsApi.getSettings()])
    Object.assign(codexCli, codex.data || {})
    codexModel.value = codex.data?.model?.model || 'gpt-5.6-sol'
    Object.assign(codexStatus, codex.data?.available && codex.data?.authenticated
      ? { type: codex.data?.selectedForViralAnalysis ? 'success' : 'warning', label: codex.data?.selectedForViralAnalysis ? '已启用' : '可以启用' }
      : { type: 'info', label: codex.data?.available ? '尚未登录' : '未安装' })
    Object.assign(aiForm, universal.data, { apiKey: '' })
    Object.assign(connectionStatus, universal.data?.selectedForViralAnalysis
      ? { type: universal.data?.apiKeyConfigured ? 'success' : 'warning', label: universal.data?.apiKeyConfigured ? '已启用' : '已保存，未填 Key' }
      : { type: 'info', label: '未启用' })
    models.value = configured.data.models || []
    Object.assign(taskModels, configured.data.taskModels || {})
    factsOnlyMode.value = integrations.data?.factsOnlyMode === true
    Object.assign(integrationForm, integrations.data, { opencliAdminApiToken: '', videoJiexiApiToken: '' })
  } finally { loading.value = false }
}
const configureCodex = async () => {
  configuringCodex.value = true
  try {
    const r = await agentModelsApi.configureCodexCli(codexModel.value.trim() || 'gpt-5.6-sol')
    Object.assign(codexCli, r.data || {})
    Object.assign(codexStatus, { type: 'success', label: '已启用' })
    await loadAll()
    ElMessage.success('本机 Codex 已设为爆款拆解模型')
  } finally { configuringCodex.value = false }
}
const saveIntegrations = async () => {
  savingIntegrations.value = true
  try { const r = await integrationsApi.saveSettings(integrationForm); Object.assign(integrationForm, r.data, { opencliAdminApiToken: '', videoJiexiApiToken: '' }); ElMessage.success('集成配置已保存') } finally { savingIntegrations.value = false }
}
const testIntegration = async () => {
  testingIntegration.value = true
  try { const r = await integrationsApi.videoJiexiStatus(); if (r.data?.available !== false && r.data?.health?.ok) { Object.assign(integrationStatus, { type: 'success', label: '视频解析服务在线' }); ElMessage.success('视频解析服务连接正常') } else { Object.assign(integrationStatus, { type: 'warning', label: '未连接' }); ElMessage.warning(r.data?.error || '视频解析服务未连接') } } finally { testingIntegration.value = false }
}
const saveIndependent = async () => {
  if (!aiForm.providerName.trim()) return ElMessage.warning('请填写厂商名称')
  if (!aiForm.baseUrl.trim()) return ElMessage.warning('请填写 API 地址')
  if (!aiForm.model.trim()) return ElMessage.warning('请填写模型名')
  savingIndependent.value = true
  try {
    const r = await agentModelsApi.saveUniversalAISettings(aiForm)
    Object.assign(aiForm, r.data, { apiKey: '' })
    Object.assign(connectionStatus, { type: r.data?.apiKeyConfigured ? 'success' : 'warning', label: r.data?.apiKeyConfigured ? '已启用' : '已保存，未填 Key' })
    await loadAll()
    ElMessage.success('通用 AI 已设为爆款拆解模型')
  } finally { savingIndependent.value = false }
}
const testIndependent = async () => {
  testingIndependent.value = true
  try { const r = await agentModelsApi.testUniversalAI(); Object.assign(connectionStatus, { type: 'success', label: '连接正常' }); ElMessage.success(`模型测试成功，耗时 ${r.data.elapsedMs} ms`) }
  catch { Object.assign(connectionStatus, { type: 'danger', label: '连接失败' }) }
  finally { testingIndependent.value = false }
}
const discoverModels = async (refresh = false) => {
  discovering.value = true
  try { const r = await agentModelsApi.discoverModels(refresh); discoveredModels.value = flattenCatalog(r.data); ElMessage.success(`已读取 ${discoveredModels.value.length} 个模型`) }
  finally { discovering.value = false }
}
const openEditor = (model = null) => { editingId.value = model?.id || ''; Object.assign(editor, emptyEditor(), model || {}); catalogSelection.value = ''; editorVisible.value = true }
const applyCatalogModel = (value) => {
  if (!value) return
  const [provider, model] = value.split('\n'), selected = discoveredModels.value.find((x) => x.provider === provider && x.model === model)
  Object.assign(editor, { provider, model, name: editor.name || selected?.name || model })
}
const saveModel = async () => {
  if (!editor.name.trim() || !editor.provider.trim() || !editor.model.trim()) return ElMessage.warning('请填写名称、Provider 和 Model')
  savingModel.value = true
  try { editingId.value ? await agentModelsApi.updateAgentModel(editingId.value, editor) : await agentModelsApi.createAgentModel(editor); editorVisible.value = false; await loadAll(); ElMessage.success('Agent 模型已保存') }
  finally { savingModel.value = false }
}
const removeModel = async (model) => { await ElMessageBox.confirm(`确定删除“${model.name}”吗？`, '删除模型', { type: 'warning' }); await agentModelsApi.deleteAgentModel(model.id); await loadAll(); ElMessage.success('模型已删除') }
const testModel = async (model) => { testingModelId.value = model.id; try { const r = await agentModelsApi.testAgentModel(model.id); ElMessage.success(`测试成功，耗时 ${r.data.elapsedMs} ms`) } finally { testingModelId.value = '' } }
const saveTaskModel = async () => { savingTask.value = true; try { await agentModelsApi.saveTaskModels(taskModels); ElMessage.success('爆款拆解模型已保存') } finally { savingTask.value = false } }
onMounted(loadAll)
</script>

<style lang="scss" scoped>
.agent-models-page { max-width: 1180px; margin: 0 auto; color: var(--sau-ink); }
.page-header, .section-heading, .task-row { display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.page-header { margin-bottom: 28px; } .page-header p, .section-heading p { margin: 6px 0 0; color: var(--sau-muted); }
.eyebrow { color: var(--sau-accent) !important; font-size: 12px; font-weight: 700; text-transform: uppercase; }
h1 { margin: 0; font-size: 30px; letter-spacing: 0; } h2 { margin: 0; font-size: 18px; letter-spacing: 0; }
.settings-section { padding: 24px 0; border-top: 1px solid var(--sau-line); } .section-heading { margin-bottom: 20px; }
.connection-form { display: grid; grid-template-columns: 2fr 1.5fr 160px; gap: 18px; } .connection-form :deep(.el-form-item) { margin-bottom: 4px; }
.section-actions { display: flex; gap: 10px; margin-top: 18px; }
.local-ai-section { background:var(--sau-accent-soft); padding:24px; border:1px solid var(--sau-line); border-radius:8px; margin-bottom:24px; }
.universal-ai-section { background:var(--sau-paper-muted); padding:24px; border:1px solid var(--sau-line); border-radius:8px; margin-bottom:24px; }
.universal-ai-form { grid-template-columns:1fr 1fr 2fr 1.4fr 1fr 150px; }
.secret-note { margin:12px 0 0; color:var(--sau-muted); font-size:12px; }
.local-ai-grid { display:grid; grid-template-columns:1fr 1fr minmax(240px,1.2fr); gap:18px; }
.local-ai-grid > div { display:flex; flex-direction:column; gap:7px; } .local-ai-grid span,.inline-help { color:var(--sau-muted); font-size:13px; }
.local-ai-grid strong { color:var(--sau-ink); }
.task-row > div { display: flex; flex-direction: column; gap: 5px; min-width: 220px; } .task-row span { color: var(--sau-muted); font-size: 13px; }
.task-row .el-select { width: min(460px, 100%); margin-left: auto; } .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .connection-form, .form-grid, .local-ai-grid { grid-template-columns: 1fr; } .page-header, .section-heading, .task-row { align-items: stretch; flex-direction: column; } .task-row .el-select { width: 100%; margin-left: 0; } .section-actions { flex-wrap: wrap; } }
</style>
