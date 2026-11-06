# FileRelay／文件接力：运行与验收

本版依据 [实施计划](../plan.md) v1.3 开发，供全新安装使用。只支持本地存储、SQLite 和单 worker。沿用 FileCodeBox 的管理员认证、设置和主题基础；公开首页使用同一页面上传和接收，不使用提取码取件。

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

仅在本机 HTTP 测试时：

```sh
APP_ENV=development docker compose up -d --build
```

公网运行保留默认 `APP_ENV=production`，必须由 HTTPS 访问。反向代理保留 Host，传递实际协议 `X-Forwarded-Proto`，并将 `FORWARDED_ALLOW_IPS` 设置为真实代理的 IP 或网段。不要为了省事设置为 `*`。部署者配置 NAS 挂载、CPU 架构、域名、TLS、代理上传体积和超时；这些值没有写死在项目中。支持 Docker 为 NAS 的架构构建镜像，当前本机验证架构见 [验证记录](../implementation-status.md)。

默认端口 12345，默认数据根 `/app/data`。`FILERELAY_DATA_ROOT` 可覆盖数据根；`WORKERS=1` 固定为首版运行约束，不能通过增加 worker 扩容。`APP_ENV` 决定 Cookie 的 Secure 属性；`LOG_LEVEL`、`ACCESS_LOG`、`FORWARDED_ALLOW_IPS` 和 `TIMEOUT_KEEP_ALIVE` 沿用运行配置。浏览器凭证只存 Cookie，服务端只存凭证 SHA256，不设置应用层 30/90 天强制过期；Cookie 仍受浏览器的保存策略限制。

当前发布规则定义于 `apps/relay/config.py`，修改这些规则需要重新评估验收，不通过旧后台保存策略改变：

| 规则 | 值 |
| --- | --- |
| 单文件 / 全站上限 | 1,000,000,000 / 500,000,000,000 字节（十进制 GB） |
| 总保留期 / 首次完整发送后窗口 | 24 小时 / 10 分钟；采用两者较早值 |
| 加入申请 / 上传会话期限 | 10 分钟 / 24 小时 |
| 分片 / 自动轮询 / 清理扫描 | 4 MiB / 2 秒 / 60 秒 |
| 下载租约 / 续租 / 最长保护 | 90 秒 / 15 秒 / 8 小时 |

8 小时保护上限相当于 1 GB 文件约 35 KB/s；这是首版的有限保护边界，已验证背压下续租和断连，未代表全部真实移动网络均已测完。到期或删除后拒绝新请求，已经进入的传输在有效租约内继续；达到最长保护时间会结束传输。Range 支持单区间，但任何 206 都不触发领取；不做跨 Range 整体完成判断。

管理员仍从 `/#/admin` 登录。后台可查看全站容量、下载和删除文件；删除使用相同租约与重试清理。Relay 文件不能改为永久或延长过期时间。旧的上传大小、保存策略、外部存储等配置仅为兼容代码保留，不改变 Relay 首版规则；新流程固定写入本地存储。NAS 原文件仍可由管理员浏览与明确删除，首版关闭新建 NAS 引用分享；撤销旧引用记录不删除原文件。MCP、公开 `/share`、`/chunk`、`/presign`、`/api/presign` 均返回 410，管理员 Token 也不能重开这些入口。

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
.venv/bin/pip install pytest pytest-asyncio httpx ruff mypy 'moto[s3,server]'
.venv/bin/ruff check .
.venv/bin/python scripts/mypy_ratchet.py
cd frontend
pnpm test
pnpm build
cd ..
.venv/bin/pytest -q
docker compose config --quiet
docker build -t filerelay:verification .
.venv/bin/python scripts/verify_relay_container.py filerelay:verification
```

后端测试必须允许绑定本机临时端口。测试包在应用导入前创建独立临时根，数据库和写入文件不会使用仓库 `data/`。真实进程测试另外设置临时根并运行完整 lifespan 和磁盘迁移，验证重复启动、凭证/倒计时持久化、TCP 断连和备份恢复。镜像验证脚本创建专属随机命名容器和数据卷，结束后只删除自己创建的容器和卷。

## 备份与恢复

备份时先停止写入（例如 `docker compose stop`），同时备份整个数据卷；SQLite 数据库、WAL/SHM（如果存在）和 `relay/` 文件必须是同一时点的副本。可使用 NAS 卷快照或把已停止服务的数据目录完整归档。不要只复制 `filecodebox.db`，也不要在上传过程中各自复制数据库和文件。

恢复到空卷，使用匹配版本的镜像，再启动单 worker。数据库迁移有登记，重复启动不会重建；恢复 Cookie 仍需原浏览器保存原凭证。文件截止时间不因恢复而重置；已到期或待删除的文件在启动清理中处理，失败则保留状态下一轮重试。备份内容已到期时不应重新向用户开放。无旧 FileCodeBox 数据导入或升级兼容承诺。
