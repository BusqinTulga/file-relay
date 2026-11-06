import api from './client'
import type { ApiResponse, DashboardData } from '@/types'
export class StatsService {
  static getDashboard(): Promise<ApiResponse<DashboardData>> {
    return api.get('/admin/dashboard')
  }
}
