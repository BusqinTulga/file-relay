import api from './client'
import type { ApiResponse, ConfigState, PublicConfigPayload } from '@/types'
export class ConfigService {
  static getConfig(): Promise<ApiResponse<ConfigState>> {
    return api.get('/admin/config/get')
  }
  static getUserConfig(): Promise<ApiResponse<PublicConfigPayload>> {
    return api.get('/api/v1/config')
  }
  static updateConfig(config: Partial<ConfigState>): Promise<ApiResponse> {
    return api.patch('/admin/config/update', config)
  }
}
