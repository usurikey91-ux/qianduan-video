<template>
  <el-container class="app-shell">
    <el-aside
      :width="mobileSidebarOpen || !isCollapse ? '248px' : '72px'"
      class="app-sidebar"
      :class="{ 'mobile-open': mobileSidebarOpen }"
    >
      <div class="brand">
        <div class="brand-mark">拆</div>
        <div v-show="!isCollapse || mobileSidebarOpen" class="brand-copy">
          <strong>自媒体内容拆解</strong>
          <span>跨平台事实复盘工作台</span>
        </div>
      </div>

      <el-menu
        :router="true"
        :default-active="activeMenu"
        :collapse="isCollapse && !mobileSidebarOpen"
        class="sidebar-menu"
      >
        <el-menu-item index="/benchmark-management">
          <el-icon><Aim /></el-icon>
          <template #title>对标内容库</template>
        </el-menu-item>
        <el-menu-item index="/idea-radar">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>入选作品列表</template>
        </el-menu-item>
        <el-menu-item index="/platform-connections">
          <el-icon><Connection /></el-icon>
          <template #title>账号连接</template>
        </el-menu-item>
        <el-menu-item index="/own-content-review">
          <el-icon><TrendCharts /></el-icon>
          <template #title>作品复盘</template>
        </el-menu-item>
        <el-menu-item index="/video-inspector">
          <el-icon><VideoPlay /></el-icon>
          <template #title>视频解析</template>
        </el-menu-item>
        <el-menu-item index="/material-management">
          <el-icon><FolderOpened /></el-icon>
          <template #title>素材管理</template>
        </el-menu-item>
        <el-menu-item index="/agent-models">
          <el-icon><Setting /></el-icon>
          <template #title>设置</template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div v-show="!isCollapse || mobileSidebarOpen" class="sidebar-note">
          <span>本周重点</span>
          <strong>把每条内容变成下一条的证据</strong>
        </div>
        <div v-if="!isCollapse || mobileSidebarOpen" class="theme-switch" role="group" aria-label="界面主题">
          <button :class="{ active: theme === 'light' }" :aria-pressed="theme === 'light'" @click="setTheme('light')">
            <el-icon><Sunny /></el-icon><span>日间</span>
          </button>
          <button :class="{ active: theme === 'dark' }" :aria-pressed="theme === 'dark'" @click="setTheme('dark')">
            <el-icon><Moon /></el-icon><span>夜间</span>
          </button>
        </div>
        <button v-else class="theme-icon-toggle" :aria-label="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'" @click="toggleTheme">
          <el-icon><Sunny v-if="theme === 'dark'" /><Moon v-else /></el-icon>
        </button>
      </div>
    </el-aside>

    <button v-if="mobileSidebarOpen" class="sidebar-backdrop" aria-label="关闭侧边栏" @click="mobileSidebarOpen = false" />

    <el-container class="workspace">
      <el-header class="topbar">
        <button class="icon-button" aria-label="切换侧边栏" @click="toggleSidebar">
          <el-icon><Fold /></el-icon>
        </button>
        <div class="topbar-title">
          <span>{{ routeMeta.kicker }}</span>
          <strong>{{ routeMeta.title }}</strong>
        </div>
        <div class="topbar-actions">
          <template v-if="showWorkspaceActions">
            <el-button text :icon="Refresh">同步数据</el-button>
            <el-button type="primary" :icon="Plus">新建复盘</el-button>
          </template>
          <el-tag v-if="route.path !== '/video-inspector'" type="info" effect="plain">本机模式</el-tag>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Aim,
  Connection,
  DataAnalysis,
  Fold,
  Plus,
  Refresh,
  Setting,
  Sunny,
  Moon,
  TrendCharts,
  VideoPlay,
  FolderOpened
} from '@element-plus/icons-vue'

const route = useRoute()
const isCollapse = ref(false)
const mobileSidebarOpen = ref(false)
const preferredTheme = localStorage.getItem('sau-theme')
const theme = ref(preferredTheme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))

const pageMeta = {
  '/': { kicker: 'Benchmark', title: '对标内容库' },
  '/benchmark-management': { kicker: 'Benchmark', title: '对标内容库' },
  '/idea-radar': { kicker: 'Evidence', title: '入选作品列表' },
  '/platform-connections': { kicker: 'Connections', title: '账号连接' },
  '/own-content-review': { kicker: 'Review', title: '作品复盘' },
  '/video-inspector': { kicker: 'Video Jiexi', title: '视频解析' },
  '/material-management': { kicker: 'Materials', title: '素材管理' },
  '/data': { kicker: 'Data', title: '数据明细' },
  '/agent-models': { kicker: 'Settings', title: '设置' }
}

const activeMenu = computed(() => route.path)
const routeMeta = computed(() => pageMeta[route.path] || pageMeta['/'])
const showWorkspaceActions = computed(() => !['/platform-connections', '/own-content-review', '/agent-models', '/video-inspector'].includes(route.path))

const toggleSidebar = () => {
  if (window.matchMedia('(max-width: 860px)').matches) {
    mobileSidebarOpen.value = !mobileSidebarOpen.value
    return
  }
  isCollapse.value = !isCollapse.value
}

const setTheme = (value) => { theme.value = value }
const toggleTheme = () => setTheme(theme.value === 'dark' ? 'light' : 'dark')

watch(theme, (value) => {
  document.documentElement.classList.toggle('dark', value === 'dark')
  document.documentElement.dataset.theme = value
  localStorage.setItem('sau-theme', value)
}, { immediate: true })

watch(() => route.path, () => { mobileSidebarOpen.value = false })

</script>

<style lang="scss" scoped>
.app-shell {
  min-height: 100vh;
  background: transparent;
}

.app-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  border-right: 1px solid var(--sau-sidebar-line);
  background: var(--sau-sidebar);
  transition: width 0.24s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 72px;
  padding: 0 18px;
  border-bottom: 1px solid var(--sau-sidebar-line);
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  background: var(--sau-accent);
  color: var(--sau-accent-contrast);
  font-weight: 800;
}

.brand-copy {
  min-width: 0;

  strong,
  span {
    display: block;
  }

  strong {
    color: var(--sau-sidebar-ink);
    font-size: 16px;
  }

  span {
    margin-top: 2px;
    color: var(--sau-sidebar-muted);
    font-size: 12px;
  }
}

.sidebar-menu {
  border-right: 0;
  padding: 12px 10px;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--sau-sidebar-muted);
  --el-menu-hover-bg-color: var(--sau-sidebar-hover);
  --el-menu-active-color: var(--sau-sidebar-active-ink);

  :deep(.el-menu-item) {
    height: 42px;
    margin-bottom: 4px;
    border-radius: 8px;
    color: var(--sau-sidebar-muted);
  }

  :deep(.el-menu-item.is-active) {
    background: var(--sau-sidebar-active);
    color: var(--sau-sidebar-active-ink);
    box-shadow: none;
  }

  :deep(.el-menu-item:hover) {
    background: var(--sau-sidebar-hover);
    color: var(--sau-sidebar-ink);
  }
}

.sidebar-footer {
  position: absolute;
  right: 12px;
  bottom: 12px;
  left: 12px;
  display: grid;
  gap: 10px;
}

.sidebar-note {
  padding: 14px;
  border: 1px solid var(--sau-sidebar-line);
  border-radius: 10px;
  background: var(--sau-sidebar-panel);

  span,
  strong {
    display: block;
  }

  span {
    margin-bottom: 6px;
    color: var(--sau-sidebar-muted);
    font-size: 12px;
  }

  strong {
    color: var(--sau-sidebar-ink);
    font-size: 13px;
    line-height: 1.5;
  }
}

.theme-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px;
  padding: 3px;
  border: 1px solid var(--sau-sidebar-line);
  border-radius: 8px;
  background: var(--sau-sidebar-control);

  button {
    min-height: 34px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--sau-sidebar-muted);
    cursor: pointer;
  }

  button.active {
    background: var(--sau-sidebar-control-active);
    color: var(--sau-sidebar-active-ink);
    box-shadow: 0 2px 8px rgba(63, 51, 21, 0.12);
  }
}

.theme-icon-toggle {
  width: 40px;
  height: 40px;
  justify-self: center;
  border: 1px solid var(--sau-sidebar-line);
  border-radius: 8px;
  background: var(--sau-sidebar-control);
  color: var(--sau-sidebar-ink);
  cursor: pointer;
}

.workspace {
  min-width: 0;
}

.topbar {
  height: 72px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid var(--sau-line);
  background: var(--sau-topbar);
  backdrop-filter: blur(12px);
}

.icon-button {
  width: 36px;
  height: 36px;
  border: 1px solid var(--sau-line);
  border-radius: 8px;
  background: var(--sau-paper);
  color: var(--sau-ink);
  cursor: pointer;
}

.topbar-title {
  min-width: 0;

  span,
  strong {
    display: block;
  }

  span {
  color: var(--sau-accent);
    font-size: 12px;
  }

  strong {
    margin-top: 2px;
    color: var(--sau-ink);
    font-size: 18px;
  }
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.app-main {
  min-height: calc(100vh - 72px);
  padding: 24px;
  overflow-y: auto;
  background: var(--sau-page);
}

.sidebar-backdrop { display: none; }

@media (max-width: 860px) {
  .app-sidebar {
    position: fixed;
    z-index: 40;
    width: 248px !important;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }

  .app-sidebar.mobile-open {
    transform: translateX(0);
    box-shadow: 18px 0 50px rgba(25, 27, 31, 0.24);
  }

  .sidebar-backdrop {
    position: fixed;
    z-index: 30;
    inset: 0;
    display: block;
    border: 0;
    background: rgba(25, 27, 31, 0.42);
  }

  .topbar {
    padding: 0 16px;
  }

  .topbar-actions {
    display: none;
  }

  .app-main {
    padding: 16px;
  }
}
</style>
