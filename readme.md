# FileRelay／文件快传

根据 [FileRelay 实施计划](docs/plan.md) 开发的设备间临时文件中转。输入相同的 1 至 4 位数字口令完成前两台设备配对，后续设备经已有设备确认后加入；浏览器记住配对，逐文件上传、自动共享列表和原生下载。

本版使用本地存储、SQLite、单 worker；新安装默认单文件 5 GB、全站 500 GB，后台可在此范围内调低。设置保存后立即控制普通上传、分片和续传。发布后最多保留 24 小时，首次服务端完整发送后保留 10 分钟供重试，不提供永久保存。基于 FileCodeBox 的源码和视觉基础改造，保留上游许可与作者信息。

```sh
docker compose build
docker compose up -d
```

公网使用 HTTPS；本机 HTTP 验证使用 `APP_ENV=development docker compose up -d --build`。首次访问设置管理员密码；后台入口为 `/admin/dashboard`。数据卷持久化，重新构建不会重建数据库。

- [运行、部署、备份恢复和实机验收](docs/guide/filerelay.md)
- [API 契约](docs/api/relay.md)
- [实施与验证记录](docs/implementation-status.md)
- [后台精简与限制修复计划](docs/admin-simplification-plan.md)
- [代码与数据库清理清单](docs/admin-cleanup-status.md)
- [原始产品计划](docs/plan.md)

旧公开分享、逐文件提取码、预签名和 MCP 已关闭。实际 NAS 部署、域名、HTTPS 和四类目标浏览器实机验收由部署时完成，已执行的开发验证见验证记录。

后台只保留概览、文件管理、系统设置。废弃功能的代码、依赖、表、字段及配置会通过版本化迁移清理，保留现有 Relay 文件、配对凭证和倒计时。首次升级前自动备份 SQLite；升级与恢复步骤见运行说明。

基于 [FileCodeBox](https://github.com/vastsa/FileCodeBox) 改造，保留上游作者信息和 [LGPL-3.0 许可](LICENSE)。[English](readme_en.md)。
