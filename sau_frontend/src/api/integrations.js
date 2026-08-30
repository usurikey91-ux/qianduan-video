import { http } from '@/utils/request'

export const integrationsApi = {
  getSettings: () => http.get('/settings/integrations'),
  saveSettings: (data) => http.put('/settings/integrations', data),
  publisherStatus: () => http.get('/integrations/publisher/status'),
  videoJiexiStatus: () => http.get('/integrations/video-jiexi/status')
}
