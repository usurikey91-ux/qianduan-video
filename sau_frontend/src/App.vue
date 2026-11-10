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
          <strong>内容拆解</strong>
        </div>
        <button v-show="!isCollapse || mobileSidebarOpen" class="collapse-button" aria-label="收起侧边栏" @click="toggleSidebar">
          <el-icon><ArrowLeft /></el-icon>
        </button>
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
        <el-menu-item index="/own-content-review">
          <el-icon><TrendCharts /></el-icon>
          <template #title>作品复盘</template>
        </el-menu-item>
        <el-menu-item index="/video-inspector">
          <el-icon><VideoPlay /></el-icon>
          <template #title>视频解析</template>
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
      <button v-if="isCollapse && !mobileSidebarOpen" class="expand-button" aria-label="展开侧边栏" @click="toggleSidebar">
        <el-icon><ArrowRight /></el-icon>
      </button>
      <button class="mobile-menu-button" aria-label="打开侧边栏" @click="toggleSidebar">
        <el-icon><Fold /></el-icon>
      </button>

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
  ArrowLeft,
  ArrowRight,
  DataAnalysis,
  Fold,
  Sunny,
  Moon,
  TrendCharts,
  VideoPlay,
} from '@element-plus/icons-vue'

const route = useRoute()
const isCollapse = ref(false)
const mobileSidebarOpen = ref(false)
const preferredTheme = localStorage.getItem('sau-theme')
const theme = ref(preferredTheme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))

const activeMenu = computed(() => route.path)

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
// Beav shell: the sidebar sits on the window background; the main area is a separate rounded layer laid on top.
.app-shell {
  min-height: 100vh;
  background: var(--sau-sidebar);
}

.app-sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: transparent;
  backdrop-filter: saturate(1.05) blur(24px);
  transition: width 280ms var(--sau-ease-out);
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 52px;
  padding: 0 12px 0 18px;
}

.brand-mark {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--sau-accent);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.brand-copy {
  flex: 1;
  min-width: 0;

  strong {
    display: block;
    overflow: hidden;
    color: var(--sau-sidebar-ink);
    font-size: 14px;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.collapse-button,
.expand-button,
.mobile-menu-button {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--sau-muted);
  cursor: pointer;

  &:hover { background: var(--sau-sidebar-hover); color: var(--sau-ink); }
}

.expand-button {
  position: fixed;
  z-index: 30;
  top: 14px;
  left: 76px;
}

.mobile-menu-button { display: none; }

.sidebar-menu {
  flex: 1;
  border-right: 0;
  padding: 6px 10px;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--sau-sidebar-muted);
  --el-menu-hover-bg-color: var(--sau-sidebar-hover);
  --el-menu-active-color: var(--sau-sidebar-active-ink);
  --el-menu-item-height: 36px;
  --el-menu-item-font-size: 13px;
  --el-menu-base-level-padding: 12px;

  :deep(.el-menu-item) {
    gap: 2px;
    height: 36px;
    margin-bottom: 2px;
    border-radius: 12px;
    color: var(--sau-sidebar-muted);
    font-weight: 400;
    transition: background-color 180ms ease, color 180ms ease;

    .el-icon { width: 17px; margin-right: 10px; font-size: 16px; }
  }

  :deep(.el-menu-item.is-active) {
    background: var(--sau-sidebar-active);
    color: var(--sau-sidebar-active-ink);
  }

  :deep(.el-menu-item:not(.is-active):hover) {
    background: var(--sau-sidebar-hover);
    color: var(--sau-sidebar-ink);
  }
}

.sidebar-footer {
  display: grid;
  gap: 8px;
  padding: 10px 14px 12px;
  border-top: 1px solid var(--sau-sidebar-line);
}

.sidebar-note {
  span,
  strong {
    display: block;
  }

  span {
    margin-bottom: 4px;
    color: var(--sau-muted);
    font-size: 11px;
  }

  strong {
    color: var(--sau-ink-soft);
    font-size: 12px;
    font-weight: 500;
    line-height: 1.5;
  }
}

.theme-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--sau-sidebar-line);
  border-radius: 8px;
  background: var(--sau-paper);

  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    min-height: 26px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--sau-muted);
    font-size: 12px;
    cursor: pointer;
  }

  button.active {
    background: var(--sau-paper-muted);
    color: var(--sau-ink);
  }
}

.theme-icon-toggle {
  justify-self: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--sau-sidebar-line);
  border-radius: 8px;
  background: var(--sau-paper);
  color: var(--sau-ink-soft);
  cursor: pointer;
}

.workspace {
  min-width: 0;
  padding: 8px 8px 8px 0;
}

.app-main {
  min-width: 0;
  min-height: calc(100vh - 16px);
  padding: 0;
  overflow: visible;
  border: 1px solid var(--sau-main-layer-border);
  border-radius: 12px;
  background: var(--sau-shell);
  background-color: var(--sau-page);
  box-shadow: 0 1px 2px rgba(30, 24, 16, 0.04), 0 8px 30px rgba(30, 24, 16, 0.05);
}

.sidebar-backdrop { display: none; }

@media (max-width: 860px) {
  .app-sidebar {
    position: fixed;
    z-index: 40;
    width: 248px !important;
    background: var(--sau-sidebar);
    transform: translateX(-100%);
    transition: transform 0.2s var(--sau-ease-out);
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

  .workspace { padding: 0; }

  .app-main { min-height: 100vh; border-radius: 0; border: 0; }

  .mobile-menu-button {
    position: fixed;
    z-index: 30;
    top: 14px;
    right: 14px;
    display: inline-grid;
    background: var(--sau-paper);
    box-shadow: var(--sau-ring);
  }
}
</style>
