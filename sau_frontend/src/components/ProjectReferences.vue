<template>
  <div class="project-references" aria-label="项目源码与参考项目">
    <span class="reference-label">源码与参考</span>
    <template v-for="(item, index) in visibleProjects" :key="item.url">
      <span v-if="index" class="separator">·</span>
      <el-link :href="item.url" target="_blank" type="primary" :title="item.description">
        {{ item.label }}
      </el-link>
      <span v-if="item.role" class="role">（{{ item.role }}）</span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  context: { type: String, default: 'all' }
})

const projects = [
  {
    label: '本工作台源码',
    url: 'https://github.com/usurikey91-ux/zimeiti-qianduan-neirong-chaijie',
    role: '二创入口',
    contexts: ['all', 'review', 'benchmark'],
    description: '当前自媒体内容拆解工作台源码'
  },
  {
    label: 'niupTang/douyin',
    url: 'https://github.com/niupTang/douyin',
    role: '项目底座',
    contexts: ['all', 'review'],
    description: '工作台早期项目结构与多平台能力参考'
  },
  {
    label: 'douyin-mcp',
    url: 'https://github.com/Kuhakucai/douyin-mcp',
    role: '抖音复盘连接器',
    contexts: ['all', 'review'],
    description: '当前抖音作品复盘实际使用的本地连接器'
  },
  {
    label: 'xiaohongshu-mcp',
    url: 'https://github.com/xpzouying/xiaohongshu-mcp',
    role: '小红书参考实现',
    contexts: ['all', 'review'],
    description: '小红书连接器的参考实现；当前同步链路使用 OpenCLI'
  },
  {
    label: 'OpenCLI',
    url: 'https://github.com/jackwener/opencli',
    role: '多平台采集',
    contexts: ['all', 'review', 'benchmark'],
    description: '当前小红书复盘与多平台公开数据采集工具'
  },
  {
    label: 'OpenCLI Admin',
    url: 'https://github.com/xjh1994/opencli-admin',
    role: '对标监控服务',
    contexts: ['all', 'benchmark'],
    description: '当前对标账号采集、巡检与热度判定服务的上游项目'
  }
]

const visibleProjects = computed(() => projects.filter((item) => item.contexts.includes(props.context)))
</script>

<style scoped>
.project-references {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 8px;
  color: #909399;
  font-size: 11px;
  line-height: 1.7;
}
.reference-label { margin-right: 3px; color: #606266; }
.separator, .role { color: #a8abb2; }
.project-references :deep(.el-link) { font-size: 11px; vertical-align: baseline; }
</style>
