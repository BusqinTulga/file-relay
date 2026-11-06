export default {
  simple: {
    overviewHint: '查看文件接力的容量与运行状态',
    refresh: '刷新',
    loading: '正在读取…',
    activeFiles: '有效文件',
    pendingFiles: '等待清理',
    available: '剩余额度',
    diskFree: '磁盘可用空间',
    capacity: '容量使用',
    limit: '全站容量上限',
    occupied: '实际占用额度',
    published: '已发布文件',
    reserved: '上传预留及残留分片',
    overQuota: '当前占用已超过新额度，暂时无法新增上传。',
    capacityHint: '应用额度与磁盘可用空间分别计算；待清理文件在实体删除前仍占用额度。',
    rules: '当前规则',
    fileLimit: '单文件上限',
    upload: '开放上传',
    enabled: '已开启',
    paused: '已暂停',
    retention: '文件保留',
    retentionValue: '最多 {hours} 小时，首次完整下载后 {minutes} 分钟',
    uptime: '运行时长',
    hours: '{hours} 小时',
    unsaved: '有未保存的修改',
    settingsHint: '设置保存后立即生效',
    save: '保存修改',
    saved: '已保存',
    site: '站点信息',
    siteName: '站点名称',
    description: '简介',
    noticeTitle: '通知标题',
    noticeContent: '通知内容',
    adminEntry: '首页显示管理入口',
    hidden: '已隐藏',
    uploadCapacity: '上传与容量',
    unitsHint: '1 MB = 1,000,000 字节；单文件最多 1 GB，全站最多 500 GB；0 不表示无限。',
    changeHint:
      '调低单文件上限会停止超限的在途上传；调低总额度保留已预留上传。已发布文件继续按原期限保留。',
    administrator: '管理员',
    password: '修改密码',
    passwordHint: '留空保留当前密码',
    sessionDays: '登录有效天数',
    passwordEffect: '密码至少 8 位；修改后需要重新登录，已配对设备不受影响。',
    storageRules: '存储与保留规则',
    localDisk: '使用本地磁盘存储',
    fixedRules: '文件最多保留 24 小时，首次完整下载后保留 10 分钟。数据目录由部署环境指定。',
    filename: '文件名',
    status: '状态',
    search: '查找',
    fileCount: '共 {count} 个文件',
    deleteSelected: '删除选中项（{count}）',
    selectAll: '选择本页全部文件',
    size: '大小',
    uploadTime: '上传时间',
    expires: '有效截止时间',
    actions: '操作',
    details: '详情',
    download: '下载',
    delete: '删除',
    empty: '没有符合条件的文件',
    previous: '上一页',
    next: '下一页',
    adminDownloadHint: '管理员完整下载同样会启动全组共享的 10 分钟重试窗口。',
    firstSent: '首次完整发送',
    cleanupError: '清理错误',
    deleteConfirm: '删除这 {count} 个文件？已开始的下载可继续完成。',
    status_all: '全部',
    status_waiting: '待领取',
    status_retry: '重试窗口中',
    status_expired: '已到期',
    status_pending: '等待清理',
    status_cleanup_failed: '清理失败'
  },
  admin: {
    session: {
      loggedIn: '已登录，进入管理后台',
      loggedOut: '登录管理后台'
    },
    logout: '退出登录',
    dashboard: {
      title: '概览'
    },
    fileManage: {
      title: '文件管理'
    },
    settings: {
      title: '系统设置'
    }
  },
  common: {
    close: '关闭',
    day: '天'
  },
  send: {
    uploadArea: {
      placeholder: '点击或拖放文件到此处上传',
      description: '支持各种常见格式',
      retry: '重试',
      selectedFiles: '已选择 {count} 个文件',
      status: {
        initializing: '正在初始化上传...',
        uploading: '正在上传文件...',
        confirming: '正在确认上传...',
        success: '上传成功！'
      }
    }
  }
}
