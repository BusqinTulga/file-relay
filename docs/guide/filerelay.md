# FileRelay／文件快传：运行与验收

本版依据原始实施计划及 [后台精简计划](../admin-simplification-plan.md) 开发，支持全新安装与现有 FileRelay 数据库升级。只支持本地存储、SQLite 和单 worker。沿用 FileCodeBox 的管理员认证、设置和主题基础；公开首页使用同一页面上传和接收，不使用提取码取件。

## 本地开发

后端使用 Python 3.12，前端使用 Node 20 和 pnpm 9.15.9。首次运行：

```sh
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.lock.txt
cd frontend
corepack enable
corepack prepare pnpm@9.15.9 --activate
pnpm install --frozen-lockfile
pnpm build
cd ..
FILERELAY_DATA_ROOT=/tmp/filerelay-development APP_ENV=development .venv/bin/uvicorn main:app --host 127.0.0.1 --port 12345
```

打开 `http://127.0.0.1:12345`，首次设置管理员密码后进入首页。开发目录不要与正式目录相同。前端实时开发可另在 `frontend/` 运行 `pnpm dev`；Vite 将 `/api`、`/admin`、`/setup` 同源代理到后端。开发时使用 `APP_ENV=development`；不要给开发服务添加跨站 CORS。

## Docker / NAS Container Manager

```sh
docker compose build
docker compose up -d
```

Compose 从当前仓库构建前后端，没有拉取上游主题或运行上游业务镜像。数据卷 `relay-data` 同时保存数据库与文件；不要执行 `docker compose down -v`，该命令会销毁数据卷。单纯 `docker compose down`、`up -d --build` 或重建容器不会删除卷。

默认 Compose 项目名为 `filerelay`，对应现有的 `filerelay_relay-data` 数据卷，容器名为 `file-relay`。如果之前使用了自定义项目名，升级时继续用原来的项目名，以便挂载原数据卷。

仅在本机 HTTP 测试时：

```sh
APP_ENV=development docker compose up -d --build
```

生产模式默认支持 HTTP 和 HTTPS。同一域名或 IP 上，配对 Cookie 可以跨协议使用，CSRF 仍校验请求来源和令牌。HTTP 会明文传输凭证和文件。仅提供 HTTPS 的部署可以设置 `FILERELAY_ALLOW_HTTP=false`，恢复 Cookie 的 `Secure` 属性。

配置 HTTPS 反向代理时，保留 Host，传递实际协议 `X-Forwarded-Proto`，并将 `FORWARDED_ALLOW_IPS` 设置为真实代理的 IP 或网段。部署时配置 NAS 挂载、CPU 架构、域名、TLS、代理上传体积和超时。当前本机验证架构见 [验证记录](../implementation-status.md)。

默认端口 12345，默认数据根 `/app/data`。`FILERELAY_DATA_ROOT` 可覆盖数据根；`WORKERS=1` 固定为首版运行约束，不能通过增加 worker 扩容。`LOG_LEVEL`、`ACCESS_LOG`、`FORWARDED_ALLOW_IPS` 和 `TIMEOUT_KEEP_ALIVE` 沿用运行配置。浏览器凭证只存 Cookie，服务端只存凭证 SHA256，不设置应用层 30/90 天强制过期；Cookie 仍受浏览器的保存策略限制。

单文件和全站容量由后台设置并持久化，所有上传入口、公开配置和后台概览使用同一执行值。其他固定规则定义于 `apps/relay/config.py`：

| 规则 | 值 |
| --- | --- |
| 单文件 / 全站上限 | 新安装默认 1,000,000,000 / 500,000,000,000 字节，可在后台调低；0 不表示无限 |
| 总保留期 / 首次完整发送后窗口 | 24 小时 / 10 分钟；采用两者较早值 |
| 加入申请 / 上传会话期限 | 10 分钟 / 24 小时 |
| 分片 / 自动轮询 / 清理扫描 | 4 MiB / 2 秒 / 60 秒 |
| 下载租约 / 续租 / 最长保护 | 90 秒 / 15 秒 / 8 小时 |

8 小时保护上限相当于 1 GB 文件约 35 KB/s；5 GB 文件要在保护期内完成，速度需约 174 KB/s 以上。这是有限保护边界，已验证背压下续租和断连，未代表全部真实移动网络均已测完。到期或删除后拒绝新请求，已经进入的传输在有效租约内继续；达到最长保护时间会结束传输。Range 支持单区间，但任何 206 都不触发领取；不做跨 Range 整体完成判断。

管理员从 `/admin/dashboard` 登录，只有概览、文件管理、系统设置三个入口。文件列表提供文件名搜索、状态筛选、分页、只读详情和下载。系统设置修改后自动保存并立即生效。管理员完整下载也会启动共享的 10 分钟窗口。

系统设置保留站点信息、首页管理入口、管理员密码和登录有效天数，以及开放上传、单文件上限和总容量。新安装默认单文件上限为 5 GB，已有实例升级时保留原有上限。数据目录由部署环境管理。NAS 文件操作、外部存储、MCP、文本分享、提取码和过期策略编辑已删除。公开 `/share`、`/chunk`、`/presign`、`/api/presign`、`/mcp` 均返回 410，管理员 Token 也不能重开。

容量统一使用十进制单位，1 MB = 1,000,000 字节；已保存的字节值不会因为显示单位而取整改写。调低单文件上限会拒绝并取消超限的未完成上传，清理成功后释放预留；已发布文件不追溯删除。调低总容量可以低于当前占用，之后拒绝新增预留，已有合法预留可继续。暂停上传会阻止新会话、后续分片和发布，仍允许查询和取消；重新开放后，仍有效且符合当前限制的上传可继续。


## 两台设备及第三台加入

1. A 输入 `007`，B 输入同一口令，两台直接加入；`7` 与 `007` 不同。
2. A 选择文件，B 的前台列表自动出现；A、B 均可上传、下载和删除。
3. 第三浏览器输入 `007` 后等待，任意已加入设备同意即可；拒绝或等待超过 10 分钟均不加入。申请短 ID 用于在熟人之间核对请求。
4. 刷新及重开浏览器无需再输入口令。无痕、新浏览器或清除网站数据后视为新设备。
5. “重新输入口令”时停止旧队列。目标加入成功后，仅本浏览器上传的有效文件迁移，发布时间和既有清理倒计时保持原值；待确认期间文件留在原组。
6. 丢失 Cookie 后不能认领原设备文件；若无设备可以确认，使用另一未占用口令建立新配对。

共享短口令不代表真实个人身份，前两台直接加入属于已确认的产品规则。不要把口令当作公开发布文件的链接。

## 上传、下载及异常验收

多选照片、中文名称、普通文件、零字节文件以及大于 4 MiB 的文件；逐文件显示进度和失败原因，成功项不重复传。失败文件点重试；重选同名同大小文件时仍重新计算完整 SHA256，只有身份完全一致才续传。进度 95% 的发布阶段还没有成功，列表发布后才算完成。

下载通过浏览器原生 attachment，不将整个文件读入前端内存。服务端完整发送后显示“传输完成，将于指定时间清理”，这不承诺浏览器已经落盘。HEAD、元数据、可识别预取、Range 及中断均不启动 10 分钟窗口。反复完整下载不延长首次窗口。容量不足时拒绝新上传，不删除仍有效的文件腾空间。

| 实机组合 | 手动验收步骤 | 本次状态 |
| --- | --- | --- |
| iPhone Safari ↔ Mac Safari | 拍照/相册多选、中文文件、页面后台恢复、断网重试、原生下载及重开记忆 | 待实机执行 |
| iPhone Safari ↔ Windows Chrome | 双向多文件、第三浏览器审批、下载后 10 分钟清理 | 待实机执行 |
| Mac Safari ↔ Mac Chrome | 拖放与粘贴文件、跨标签页重新配对、旧列表和队列隔离 | 待实机执行 |
| Windows Chrome ↔ Mac Chrome | 大文件 SHA256 对比、下载中删除、慢速网络与断连、刷新不重置队列 | 待实机执行 |

另已执行本机内置浏览器的配对、文件选择上传、原生下载与刷新记忆检查；不能用此替代以上四类组合。慢速/断连可在目标浏览器网络工具或真实移动网络中模拟，记录文件大小、完成时间和本机 SHA256；删除时应看见新请求被拒绝、已开始下载能在租约内完成。NAS HTTPS 和实机网络由部署者验收，本次未操作实际 NAS。

## 测试和自建镜像验证

```sh
.venv/bin/pip install pytest pytest-asyncio httpx ruff mypy
.venv/bin/ruff check .
.venv/bin/python scripts/mypy_ratchet.py
cd frontend
pnpm test
pnpm build
cd ..
.venv/bin/pytest -q
docker compose config --quiet
docker build -t file-relay:verification .
.venv/bin/python scripts/verify_relay_container.py file-relay:verification
```

后端测试必须允许绑定本机临时端口。测试包在应用导入前创建独立临时根，数据库和写入文件不会使用仓库 `data/`。真实进程测试另外设置临时根并运行完整 lifespan 和磁盘迁移，验证重复启动、凭证/倒计时持久化、TCP 断连和备份恢复。镜像验证脚本创建专属随机命名容器和数据卷，结束后只删除自己创建的容器和卷。

## 备份与恢复

备份时先停止写入（例如 `docker compose stop`），同时备份整个数据卷；SQLite 数据库、WAL/SHM（如果存在）和 `relay/` 文件必须是同一时点的副本。可使用 NAS 卷快照或把已停止服务的数据目录完整归档。不要只复制 `filecodebox.db`，也不要在上传过程中各自复制数据库和文件。

恢复到空卷，使用匹配版本的镜像，再启动单 worker。数据库迁移有登记，重复启动不会重建；恢复 Cookie 仍需原浏览器保存原凭证。文件截止时间不因恢复而重置；已到期或待删除的文件在启动清理中处理，失败则保留状态下一轮重试。备份内容已到期时不应重新向用户开放。不提供旧 FileCodeBox 业务导入；废弃实体的处置见下文归档说明。


## 本次结构清理的升级与回退

迁移 `migrations_010.py` 在接收业务请求和启动清理任务前执行。先使用 SQLite backup API 创建 `backups/before-schema-010.db`，覆盖 WAL 中已提交的数据，并检查备份完整性；随后在事务内重建精简后的文件表、删除废弃上传表及旧配置。备份失败或结构迁移失败会阻止启动。重试不覆盖原备份，重复启动不重建已删除的结构。

升级前仍建议停止旧服务并备份完整数据卷。自动数据库备份不能替代完整卷备份，也不会复制文件实体。配对凭证、文件 ID、上传归属、发布时间、首次发送时间、截止时间、在途上传、分片和租约保持原值。新安装运行同一迁移链，最终不会保留旧业务表。

旧 FileCodeBox 文件或 NAS 引用若仍有记录，会从活动数据库移入备份及 `backups/retired-assets-010.json` 目录清单，原实体和 NAS 原文件保持不动。该清单保留路径与归属信息供人工核对，不能当作新的 Relay 文件访问入口；这些归档实体不计入活动应用额度，仍占实际磁盘空间。备份目录包含历史凭证和路径，应与主数据库同等保护，不对外分享。

需要回退时先停止新服务，恢复升级前的完整卷备份并使用旧版本镜像。若升级后尚未接收写入，可恢复 `before-schema-010.db` 并确保没有旧 WAL/SHM 被混入；已有新写入后不能仅替换数据库，否则会丢失升级后的归属、时间和文件记录，应恢复同一时点的完整备份。恢复后再次升级会重新校验和执行未登记迁移。

本轮具体删除清单及验证结果见 [代码和数据库清理记录](../admin-cleanup-status.md)。
