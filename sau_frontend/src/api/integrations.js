import { http } from '@/utils/request'

export const integrationsApi = {
  getSettings: () => http.get('/settings/integrations'),
  saveSettings: (data) => http.put('/settings/integrations', data),
  videoJiexiStatus: () => http.get('/integrations/video-jiexi/status')
}
