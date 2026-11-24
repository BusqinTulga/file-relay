export interface ConfigState {
  name: string
  description: string
  show_admin_addr: number
  admin_token: string
  admin_session_expire: number
  open_upload: number
  upload_size: number
  storage_limit: number
  data_root?: string
}
export interface PublicConfigMeta {
  version?: string
}
export interface PublicConfigPayload {
  config: Partial<ConfigState>
  meta?: PublicConfigMeta
}
