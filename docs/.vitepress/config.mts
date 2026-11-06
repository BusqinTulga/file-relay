import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'FileRelay／文件接力',
  description: '设备间临时文件接力与管理',
  lang: 'zh-CN',
  cleanUrls: true,
  lastUpdated: true,
  head: [['link', { rel: 'icon', href: '/logo_small.png' }]],
  locales: {
    root: { label: '简体中文', lang: 'zh-CN' },
    en: { label: 'English', lang: 'en-US' }
  },
  themeConfig: {
    nav: [
      { text: '首页 / Home', link: '/' },
      { text: '运行与升级 / Operations', link: '/guide/filerelay' },
      { text: 'API', link: '/api/relay' }
    ],
    sidebar: [
      { text: 'FileRelay', items: [
        { text: '运行、备份与升级', link: '/guide/filerelay' },
        { text: '接口契约', link: '/api/relay' },
        { text: '后台精简计划', link: '/admin-simplification-plan' },
        { text: '代码与数据库清理结果', link: '/admin-cleanup-status' },
        { text: '原始产品计划', link: '/plan' }
      ] }
    ],
    socialLinks: [{ icon: 'github', link: 'https://github.com/BusqinTulga/FileRelay' }],
    footer: { message: 'Based on FileCodeBox · LGPL-3.0' }
  }
})
