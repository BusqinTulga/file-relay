export interface DashboardData {
  active_files: number
  pending_files: number
  published_bytes: number
  reserved_bytes: number
  occupied_bytes: number
  available_bytes: number
  disk_free_bytes: number
  sys_start: number | null
  upload_size: number
  storage_limit: number
  open_upload: number
  file_ttl: number
  retry_window: number
}
