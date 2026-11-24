import { STORAGE_KEYS } from '@/constants'
import type { ConfigState } from '@/types'
export type PublicConfig = Pick<
  ConfigState,
  | 'name'
  | 'description'
  | 'show_admin_addr'
  | 'upload_size'
  | 'storage_limit'
  | 'open_upload'
>
export const DEFAULT_PUBLIC_CONFIG: PublicConfig = {
  name: 'FileRelay／文件快传',
  description: '在你的设备之间，轻松传递文件',
  show_admin_addr: 0,
  upload_size: 0,
  storage_limit: 0,
  open_upload: 0
}
export const DEFAULT_CONFIG_STATE: ConfigState = {
  ...DEFAULT_PUBLIC_CONFIG,
  admin_token: '',
  admin_session_expire: 30 * 86400
}
export function toPublicConfig(
  config: Partial<ConfigState> | null | undefined
): Partial<PublicConfig> {
  if (!config) return {}
  const name = ['FileRelay／文件接力', 'FileRelay・文件接力'].includes(config.name ?? '')
    ? DEFAULT_PUBLIC_CONFIG.name
    : config.name
  return Object.fromEntries(
    Object.keys(DEFAULT_PUBLIC_CONFIG)
      .filter((key) => config[key as keyof ConfigState] !== undefined)
      .map((key) => [key, key === 'name' ? name : config[key as keyof ConfigState]])
  )
}
export function readStoredConfig<T extends object = Partial<ConfigState>>(): T | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.CONFIG)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}
export function writeStoredConfig(config: object) {
  localStorage.setItem(STORAGE_KEYS.CONFIG, JSON.stringify(toPublicConfig(config)))
}
