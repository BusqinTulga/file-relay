# FileRelay v1 接口契约

基础路径 `/api/relay`，同源 Cookie 认证，JSON 使用 snake_case。公开协议已关闭。所有响应禁止缓存；设备 401 与管理员 401 相互独立。

`GET /session` 用于启动，返回 `paired`、`csrf`，已加入设备另返回 `passcode`、`device_id`、`session_id`。未配对时下发 HttpOnly CSRF 引导 Cookie。所有写操作必须带与当前会话一致的 `X-Relay-CSRF` 和同源 `Origin`；浏览器队列固定携带开始时的 `X-Relay-Session`，凭证更换后旧队列被拒绝。原生下载只使用 Cookie。Cookie 使用 Path=/、HttpOnly、SameSite=Strict，生产额外 Secure。

| 方法与路径 | 输入 / 结果 |
| --- | --- |
| POST `/pair` | JSON `{passcode: "007"}`；前两台直接加入，其余返回 pending、request_id、expires，并设置独立申请 Cookie |
| POST `/pairing/status` | 申请浏览器查询；approved 时原子加入、签发新 Cookie、迁移本设备文件；其他返回 pending / rejected / expired |
| GET `/pairing/requests` | 当前组待确认申请 id、expires；仅已加入设备 |
| POST `/pairing/requests/{id}` | JSON `{approve: true/false}`；仅当前组设备，重复处理返回已有结果 |
| GET `/files` | 当前会话 session_id 与有效文件 files；无客户端 group 参数 |
| GET `/files/{id}` | 有效文件元数据：id、name、size、sha256、published、expires、first_sent |
| GET / HEAD `/files/{id}/download` | attachment，支持单区间 Range；HEAD、206、预取不领取 |
| DELETE `/files/{id}` | 立即关闭新访问，持久化待删；已有租约允许继续 |
| POST `/uploads` | JSON name、size、完整 sha256、chunked；返回 id、state、chunk_size、已完成 chunks；同设备同身份匹配续传 |
| GET `/uploads/{id}` | 当前设备/组/原会话的状态和已完成分片；完成后含 file |
| PUT `/uploads/{id}/content` | 普通/零字节文件原始 body，`X-Chunk-SHA256`；会话仅一个分片 |
| PUT `/uploads/{id}/chunks/{index}` | 原始 body，`X-Chunk-SHA256`；索引和确切长度检查 |
| POST `/uploads/{id}/complete` | 连续性、各片长度/哈希、合并总长与完整 SHA256 校验后发布；重复/并发返回同一 file |
| DELETE `/uploads/{id}` | 标记 cancelled，后台清理；已发布文件必须用文件删除接口 |

待确认凭证只能查自己的状态，不能代替设备凭证访问文件或上传。重新配对原凭证有效时保留 device_id，原 session 失效；旧上传取消，不迁入新组。目标批准前没有文件迁移。批准处理与凭证签发各自持久化，轮询领取时在同一事务中协调签发、加入与文件迁移；重复批准不重复加入。

上传状态为 uploading、merging、completed、cancelled、cleaned。过期会话请求返回 410，扫描回收；merging 崩溃后可以通过完整重校验完成，最终 file_id 与发布记录同事务提交。RelayUpload 是容量预留的拥有者，直到实体清理完成前不释放；已完成会话残留分片也计入占用。每个会话路径在写入前由服务器 UUID 确定；客户端文件名不能控制路径。

文件删除状态 active → pending → deleting → 移除记录。物理删除失败退回 pending 并保存错误，启动后继续。下载状态 active → completed / ended / abandoned，拥有有限 lease_until 与 protect_until。文件移动归属不改变 attempt 的 file_id，结束结果仍更新该文件。

错误：413 超出当前单文件限制；422 输入/完整性不符；401 未加入或凭证失效；403 来源/CSRF 或上传暂停；404 不存在、跨组、过期文件；409 原状态改变或不允许的状态；410 过期上传/旧协议；429 配对限流；507 额度/磁盘不足。API 与下载 404 即使 Accept=text/html 也不回落到 SPA。


## 有效上传策略与管理接口

`GET /api/v1/config` 返回 `{code, detail: {config, meta}}`；公开 config 包含站点名称、简介、通知、首页管理入口，以及 `upload_size`、`storage_limit`、`open_upload`。单位为整数字节；`meta.version` 为运行版本。公开配置不含管理员凭证、存储凭证或部署参数。首页开始处理每个队列项及重试前重新读取策略，服务端在新建、后续分片和最终发布阶段强制检查。

管理员使用独立 Bearer Token。保留以下 `/admin` 接口：

| 方法与路径 | 输入 / 结果 |
| --- | --- |
| POST `/login` | password；返回 token、expires_at、expires_in |
| GET `/verify`、POST `/logout` | 管理员会话校验和前端登出 |
| GET `/dashboard` | active_files、pending_files、published_bytes、reserved_bytes、occupied_bytes、available_bytes、disk_free_bytes、sys_start、当前限制和固定保留规则 |
| GET `/file/list` | page≥1、size 1–100、keyword、status；返回 files、total |
| GET `/file/detail?id=…` | 只读文件元数据、status、cleanup_error，不返回配对口令和凭证 |
| GET / HEAD `/file/download?id=…` | 管理员下载，同样使用租约并在首次完整发送后计时 |
| DELETE `/file/delete` | JSON `{id}`，标记待删 |
| POST `/file/batch-delete` | JSON `{ids}`，最多 100 项，返回 deleted 和逐项 failed |
| GET `/config/get` | 允许编辑的配置和只读 data_root；密码字段始终为空 |
| PATCH `/config/update` | 仅允许 name、description、notify_title、notify_content、admin_token、admin_session_expire、show_admin_addr、open_upload、upload_size、storage_limit；其他字段 422 |

文件状态为 waiting、retry、expired、pending、cleanup_failed，筛选还支持 all。修改密码会轮换管理员 JWT 签名密钥，已配对设备不受影响。移除的管理 API 返回 JSON 404，不提供旧协议兼容别名。
