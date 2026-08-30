import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import AccountManagement from '../views/AccountManagement.vue'
import PublishCenter from '../views/PublishCenter.vue'
import About from '../views/About.vue'
import DataView from '../views/DataView.vue'
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
    path: '/account-management',
    name: 'AccountManagement',
    component: AccountManagement
  },
  {
    path: '/material-management',
    name: 'MaterialManagement',
    redirect: '/publish-center'
  },
  {
    path: '/publish-center',
    name: 'PublishCenter',
    component: PublishCenter
  },
  {
    path: '/data',
    name: 'DataView',
    component: DataView
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
    path: '/koubo-studio',
    name: 'KouboStudio',
    redirect: '/publish-center'
  },
  {
    path: '/video-inspector',
    name: 'VideoInspector',
    component: VideoInspector
  },
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
