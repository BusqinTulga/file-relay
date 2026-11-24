export default {
  simple: {
    overviewHint: 'Storage and runtime status for file relay',
    refresh: 'Refresh',
    loading: 'Loading…',
    activeFiles: 'Available files',
    pendingFiles: 'Awaiting cleanup',
    available: 'Available quota',
    diskFree: 'Free disk space',
    capacity: 'Storage usage',
    limit: 'Site storage limit',
    occupied: 'Occupied quota',
    published: 'Published files',
    reserved: 'Reserved uploads and residual chunks',
    overQuota: 'Usage exceeds the new limit. New uploads are paused until space is released.',
    capacityHint:
      'Application quota and free disk space are separate. Pending deletion still occupies quota.',
    rules: 'Current policy',
    fileLimit: 'Single file limit',
    upload: 'Allow uploads',
    enabled: 'Enabled',
    paused: 'Paused',
    retention: 'Retention',
    retentionValue: 'Up to {hours} hours; {minutes} minutes after the first complete download',
    uptime: 'Uptime',
    hours: '{hours} hours',
    saving: 'Saving automatically…',
    unsaved: 'Unsaved changes',
    saved: 'Changes saved successfully',
    retrySave: 'Retry saving',
    invalidSize: 'Enter a valid size before changing the unit.',
    site: 'Site information',
    siteName: 'Site name',
    description: 'Description',
    adminEntry: 'Show admin link on the home page',
    hidden: 'Hidden',
    uploadCapacity: 'Uploads and capacity',
    unitsHint: 'Maximum: 5 GB per file, 500 GB per site. Zero does not mean unlimited.',
    changeHint:
      'Lowering the file limit stops oversized unfinished uploads. Lowering quota preserves existing reservations. Published files retain their deadlines.',
    administrator: 'Administrator',
    password: 'Change password',
    passwordHint: 'Leave blank to keep the current password',
    sessionDays: 'Session duration in days',
    passwordEffect:
      'At least 8 characters. Changing the password requires signing in again; paired devices are unaffected.',
    storageRules: 'Storage and retention',
    localDisk: 'Local disk storage',
    fixedRules:
      'Files last up to 24 hours, or 10 minutes after the first complete download. The data directory is configured at deployment.',
    filename: 'File name',
    status: 'Status',
    search: 'Search',
    fileCount: '{count} files',
    size: 'Size',
    uploadTime: 'Published',
    expires: 'Expires',
    actions: 'Actions',
    details: 'Details',
    download: 'Download',
    delete: 'Delete',
    empty: 'No matching files',
    previous: 'Previous',
    next: 'Next',
    adminDownloadHint:
      'A complete administrator download also starts the shared 10-minute retry window.',
    firstSent: 'First complete send',
    cleanupError: 'Cleanup error',
    status_all: 'All',
    status_waiting: 'Awaiting download',
    status_retry: 'Retry window',
    status_expired: 'Expired',
    status_pending: 'Awaiting cleanup',
    status_cleanup_failed: 'Cleanup failed'
  },
  admin: {
    session: {
      loggedIn: 'Signed in, open admin console',
      loggedOut: 'Sign in to admin console'
    },
    logout: 'Logout',
    dashboard: {
      title: 'Overview'
    },
    fileManage: {
      title: 'File Management'
    },
    settings: {
      title: 'System Settings'
    }
  },
  utils: {
    time: {
      forever: 'Forever',
      day: 'day',
      hour: 'hour',
      minute: 'minute',
      second: 'second'
    }
  },
  common: {
    close: 'Close',
    day: 'day'
  },
  send: {
    uploadArea: {
      placeholder: 'Click or drag files here to upload',
      description: 'Supports various common formats',
      retry: 'Retry',
      selectedFiles: '{count} files selected',
      status: {
        initializing: 'Preparing upload...',
        uploading: 'Uploading files...',
        confirming: 'Confirming upload...',
        success: 'Upload complete!'
      }
    }
  }
}
