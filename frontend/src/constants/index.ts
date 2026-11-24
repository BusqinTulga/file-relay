export const STORAGE_KEYS = {
  COLOR_MODE: 'colorMode',
  ADMIN_PASSWORD: 'adminPassword',
  TOKEN: 'token',
  TOKEN_EXPIRES_AT: 'tokenExpiresAt',
  CONFIG: 'config'
} as const

export const THEME_MODES = {
  LIGHT: 'light',
  DARK: 'dark',
  SYSTEM: 'system'
} as const

export const API_STATUS_CODES = {
  SUCCESS: 200,
  UNAUTHORIZED: 401,
  SETUP_REQUIRED: 428,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  SERVER_ERROR: 500
} as const

export const TIME_CONSTANTS = {
  ALERT_DURATION: 5000, // 5秒
  REQUEST_TIMEOUT: 300000000
} as const

export const ROUTES = {
  HOME: '/',
  SEND: '/send',
  ADMIN: '/admin',
  LOGIN: '/login',
  DASHBOARD: '/admin/dashboard',
  FILE_MANAGE: '/admin/files',
  SETTINGS: '/admin/settings'
} as const

export const ROUTE_NAMES = {
  RETRIEVE: 'Retrieve',
  SEND: 'Send',
  ADMIN: 'Manage',
  LOGIN: 'Login',
  DASHBOARD: 'Dashboard',
  FILE_MANAGE: 'FileManage',
  SETTINGS: 'Settings'
} as const
