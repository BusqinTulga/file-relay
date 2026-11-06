import api, { rawApiClient } from './client'
import type { ApiResponse, AdminFile } from '@/types'
export class FileService {
  static list(params: {
    page: number
    size: number
    keyword: string
    status: string
  }): Promise<ApiResponse<{ files: AdminFile[]; total: number }>> {
    return api.get('/admin/file/list', { params })
  }
  static detail(id: number): Promise<ApiResponse<AdminFile>> {
    return api.get('/admin/file/detail', { params: { id } })
  }
  static remove(id: number): Promise<ApiResponse> {
    return api.delete('/admin/file/delete', { data: { id } })
  }
  static batchRemove(
    ids: number[]
  ): Promise<ApiResponse<{ deleted: number[]; failed: { id: number; reason: string }[] }>> {
    return api.post('/admin/file/batch-delete', { ids })
  }
  static async download(id: number): Promise<Blob> {
    const result = await rawApiClient.get('/admin/file/download', {
      params: { id },
      responseType: 'blob'
    })
    return result.data
  }
}
