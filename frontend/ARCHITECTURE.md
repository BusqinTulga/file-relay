# FileRelay 前端架构

- 页面：`RelayView` 为配对、上传和接收首页；后台仅有概览、文件管理和系统设置，另有管理员登录页。
- 页面和组件通过 `composables` 调用业务动作，不直接调用接口；composable 从 `services/index.ts` 导入服务。
- `useRelay` 负责配对、轮询及上传队列；`relay.ts` 使用独立 Cookie/CSRF 客户端，设备认证错误不会清除管理员令牌。
- 管理员服务通过 `services/client.ts` 使用 Bearer；`useAdminFiles`、`useDashboardStats`、`useSystemConfig` 各自维护局部页面状态，页面触发首次加载。
- `configStore` 只缓存公开配置。管理员密码、JWT 签名密钥和部署参数不进入公开缓存；上传前必须重新读取有效策略，不能依赖缓存上限。
- `config-form.ts` 负责十进制单位与整数字节的精确转换；`relay-sha256.ts` 负责完整内容增量 SHA256；管理员下载的 Blob 保存由 `download-action.ts` 处理，首页下载使用浏览器原生 attachment。
- 共用组件保持现有主题；持久化访问集中在 `*-storage.ts`。通知计时归 `alertStore`。
- NAS、MCP、文本分享、旧提取码、预签名上传、ZIP 打包、二维码、内容预览与旧发送记录体系已删除，不保留兼容业务实现。

验证：`pnpm test`、`pnpm build`（含架构检查、vue-tsc 和生产构建）。
