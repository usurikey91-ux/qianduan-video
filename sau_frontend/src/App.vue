<template>
  <el-container class="app-shell">
    <el-aside :width="isCollapse ? '72px' : '248px'" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">拆</div>
        <div v-show="!isCollapse" class="brand-copy">
          <strong>自媒体内容拆解</strong>
          <span>跨平台事实复盘工作台</span>
        </div>
      </div>

      <el-menu
        :router="true"
        :default-active="activeMenu"
        :collapse="isCollapse"
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
        <el-menu-item index="/agent-models">
          <el-icon><Setting /></el-icon>
          <template #title>设置</template>
        </el-menu-item>
      </el-menu>

      <div v-show="!isCollapse" class="sidebar-note">
        <span>本周重点</span>
        <strong>把每条内容变成下一条的证据</strong>
      </div>
    </el-aside>

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
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Aim,
  Connection,
  DataAnalysis,
  Fold,
  Plus,
  Refresh,
  Setting,
  TrendCharts,
  VideoPlay
} from '@element-plus/icons-vue'

const route = useRoute()
const isCollapse = ref(false)

const pageMeta = {
  '/': { kicker: 'Benchmark', title: '对标内容库' },
  '/benchmark-management': { kicker: 'Benchmark', title: '对标内容库' },
  '/idea-radar': { kicker: 'Evidence', title: '入选作品列表' },
  '/platform-connections': { kicker: 'Connections', title: '账号连接' },
  '/own-content-review': { kicker: 'Review', title: '作品复盘' },
  '/video-inspector': { kicker: 'Video Jiexi', title: '视频解析' },
  '/data': { kicker: 'Data', title: '数据明细' },
  '/agent-models': { kicker: 'Settings', title: '设置' }
}

const activeMenu = computed(() => route.path)
const routeMeta = computed(() => pageMeta[route.path] || pageMeta['/'])
const showWorkspaceActions = computed(() => !['/platform-connections', '/own-content-review', '/agent-models', '/video-inspector'].includes(route.path))

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

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
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  background:
    radial-gradient(circle at 20% 0%, rgba(197, 75, 60, 0.22), transparent 28%),
    linear-gradient(180deg, #1d2b3a 0%, #162332 100%);
  transition: width 0.24s ease;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 72px;
  padding: 0 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  background: var(--sau-cinnabar);
  color: #ffffff;
  font-weight: 800;
}

.brand-copy {
  min-width: 0;

  strong,
  span {
    display: block;
  }

  strong {
    color: #fffaf3;
    font-size: 16px;
  }

  span {
    margin-top: 2px;
    color: #b9c2c9;
    font-size: 12px;
  }
}

.sidebar-menu {
  border-right: 0;
  padding: 12px 10px;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #b9c2c9;
  --el-menu-hover-bg-color: rgba(255, 253, 249, 0.1);
  --el-menu-active-color: #1d2b3a;

  :deep(.el-menu-item) {
    height: 42px;
    margin-bottom: 4px;
    border-radius: 8px;
    color: #b9c2c9;
  }

  :deep(.el-menu-item.is-active) {
    background: rgba(255, 253, 249, 0.96);
    color: #1d2b3a;
    box-shadow: 0 6px 18px rgba(8, 17, 26, 0.18);
  }

  :deep(.el-menu-item:hover) {
    background: rgba(255, 253, 249, 0.1);
    color: #fffaf3;
  }
}

.sidebar-note {
  position: absolute;
  right: 14px;
  bottom: 14px;
  left: 14px;
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  background: rgba(255, 253, 249, 0.07);

  span,
  strong {
    display: block;
  }

  span {
    margin-bottom: 6px;
    color: #b9c2c9;
    font-size: 12px;
  }

  strong {
    color: #fffaf3;
    font-size: 13px;
    line-height: 1.5;
  }
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
  background: rgba(255, 253, 249, 0.88);
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
    color: var(--sau-brass);
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
  background:
    linear-gradient(rgba(255, 253, 249, 0.38), rgba(255, 253, 249, 0.38)),
    repeating-linear-gradient(0deg, transparent 0, transparent 31px, rgba(29, 43, 58, 0.018) 32px);
}

@media (max-width: 860px) {
  .app-sidebar {
    display: none;
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
