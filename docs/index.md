# FileRelay／文件快传

输入相同的 1 至 4 位数字口令，在设备之间逐项传递文件。前两台设备直接加入，后续设备由已有设备批准。浏览器记住配对，上传后自动共享列表。

使用本地磁盘、SQLite 和单 worker。后台仅保留概览、文件管理、系统设置；新安装默认单文件 5 GB、全站 500 GB，可在后台调低并即时生效。文件最多保留 24 小时，首次完整下载后保留 10 分钟。

- [运行、部署、备份与数据库升级](guide/filerelay.md)
- [API 契约](api/relay.md)
- [后台精简计划](admin-simplification-plan.md)
- [代码与数据库清理结果](admin-cleanup-status.md)

基于 FileCodeBox 改造，保留上游作者信息及 LGPL-3.0 许可。未链接到当前导航的旧 FileCodeBox 文档仅为历史参考。
