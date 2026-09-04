import { http } from '@/utils/request'

export const videoJiexiApi = {
  status: () => http.get('/integrations/video-jiexi/status'),
  openFolder: () => http.post('/integrations/video-jiexi/open-folder'),
  inspect: (url, cookieBrowser = '') => http.post('/integrations/video-jiexi/inspect', { url, cookieBrowser }),
  download: (inspectionId, formatId, kind = 'video') => http.post('/integrations/video-jiexi/download', { inspectionId, formatId, kind }),
  task: (taskId) => http.get(`/integrations/video-jiexi/tasks/${taskId}`),
  importMaterial: (taskId) => http.post('/integrations/video-jiexi/import', { taskId })
}
