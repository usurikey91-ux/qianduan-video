import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import About from '../views/About.vue'
import BenchmarkManagement from '../views/BenchmarkManagement.vue'
import IdeaRadar from '../views/IdeaRadar.vue'
import OwnContentReview from '../views/OwnContentReview.vue'
import AgentModels from '../views/AgentModels.vue'
import VideoInspector from '../views/VideoInspector.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    redirect: '/'
  },
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/material-management',
    name: 'MaterialManagement',
    redirect: '/video-inspector'
  },
  {
    path: '/benchmark-management',
    name: 'BenchmarkManagement',
    component: BenchmarkManagement
  },
  {
    path: '/idea-radar',
    name: 'IdeaRadar',
    component: IdeaRadar
  },
  {
    path: '/own-content-review',
    name: 'OwnContentReview',
    component: OwnContentReview
  },
  {
    path: '/agent-models',
    name: 'AgentModels',
    component: AgentModels
  },
  {
    path: '/video-inspector',
    name: 'VideoInspector',
    component: VideoInspector
  },
  // Legacy publishing URLs intentionally redirect to the analysis workspace.
  // The workbench no longer performs account login or video publishing.
  { path: '/publish-center', redirect: '/idea-radar' },
  { path: '/account-management', redirect: '/idea-radar' },
  { path: '/koubo-studio', redirect: '/idea-radar' },
  {
    path: '/about',
    name: 'About',
    component: About
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
