import { http } from '@/utils/request'

export const platformConnectionsApi = {
  getAll: (probe = true) => http.get('/platform-connections', { probe: probe ? 1 : 0 }),

  startLogin: (platform, options = {}) => http.post(
    `/platform-connections/${platform}/login`,
    {
      acknowledgedRisk: Boolean(options.acknowledgedRisk),
      autoSync: options.autoSync !== false,
      limit: options.limit || 20
    }
  )
}

