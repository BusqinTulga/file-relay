export type ThemeMode = 'light' | 'dark' | 'system'

export type AlertType = 'success' | 'error' | 'warning' | 'info'

export interface Alert {
  id: number
  message: string
  type: AlertType
  progress: number
  duration: number
  startTime: number
}
