import { http } from '@/utils/request'

export const ownContentApi = {
  previewDouyinImport: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.upload('/own/douyin/import/preview', formData)
  },

  importDouyinWorks: (file, accountName = '我的账号') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('accountName', accountName)
    return http.upload('/own/douyin/import', formData)
  },

  getDouyinWorks: (limit = 100) => {
    return http.get('/own/douyin/videos', { limit })
  },

  previewXiaohongshuImport: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.upload('/own/xiaohongshu/import/preview', formData)
  },

  importXiaohongshuWorks: (file, accountName = '我的小红书账号') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('accountName', accountName)
    return http.upload('/own/xiaohongshu/import', formData)
  },

  getXiaohongshuWorks: (limit = 100) => {
    return http.get('/own/xiaohongshu/videos', { limit })
  },

  getReviewSources: () => {
    return http.get('/own/review/sources')
  }
}
