import { http } from '@/utils/request'

export const benchmarkApi = {
  getPlatforms: () => http.get('/benchmark/platforms'),

  bindOpencliMonitorAccount: (accountRef, platform = 'douyin') => {
    return http.post('/benchmark/monitor/accounts', { accountRef, platform })
  },

  getOpencliMonitorAccounts: (platform = '') => {
    return http.get('/benchmark/monitor/accounts', platform ? { platform } : undefined)
  },

  getOpencliMonitorRules: () => http.get('/benchmark/monitor/rules'),

  updateOpencliMonitorRules: (rules) => http.put('/benchmark/monitor/rules', rules),

  checkOpencliMonitorAccount: (accountId) => {
    return http.post(`/benchmark/monitor/accounts/${accountId}/check`)
  },

  removeOpencliMonitorAccount: (accountId) => {
    return http.delete(`/benchmark/monitor/accounts/${accountId}`)
  },

  updateOpencliMonitorAccount: (accountId, displayName) => {
    return http.patch(`/benchmark/monitor/accounts/${accountId}`, { displayName })
  },

  updateOpencliMonitorAccountRules: (accountId, monitoringRules) => {
    return http.patch(`/benchmark/monitor/accounts/${accountId}`, { monitoringRules })
  },

  setOpencliMonitorAccountEnabled: (accountId, enabled) => {
    return http.patch(`/benchmark/monitor/accounts/${accountId}`, { enabled })
  },

  getOpencliMonitorWorks: (platform = '') => {
    return http.get('/benchmark/monitor/works', platform ? { platform } : undefined)
  },

  addDouyinAccount: (homepageUrl) => {
    return http.post('/benchmark/douyin/accounts', { homepageUrl })
  },

  getDouyinAccounts: () => {
    return http.get('/benchmark/douyin/accounts')
  },

  syncDouyinAccount: (id) => {
    return http.post(`/benchmark/douyin/accounts/${id}/sync`)
  },

  deleteDouyinAccount: (id) => {
    return http.delete(`/benchmark/douyin/accounts/${id}`)
  },

  getDouyinVideos: (id) => {
    return http.get(`/benchmark/douyin/accounts/${id}/videos`)
  },

  getDouyinVideoAnalysis: (videoId) => {
    return http.get(`/benchmark/douyin/videos/${videoId}/analysis`)
  },

  createDouyinVideoAnalysis: (videoId, force = false) => {
    return http.post(`/benchmark/douyin/videos/${videoId}/analysis`, { force })
  },

  autoDiscoverDouyinAccounts: ({ keywords, limit = 5, maxVideos = 10 }) => {
    return http.post('/benchmark/douyin/auto-discover', { keywords, limit, maxVideos })
  },

  getIdeaRadarVideos: (limit = 80, days = 0) => {
    return http.get('/idea-radar/douyin/videos', { limit, days })
  },

  analyzeIdeaRadarVideo: (videoId, options = {}) => {
    return http.post(`/idea-radar/douyin/videos/${videoId}/analyze`, {
      force: Boolean(options.force),
      forceTranscription: Boolean(options.forceTranscription)
    })
  },

  getIdeaRadarStatus: (videoId) => {
    return http.get(`/idea-radar/douyin/videos/${videoId}/status`)
  }
}
