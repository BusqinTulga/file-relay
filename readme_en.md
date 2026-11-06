# FileRelay

Temporary file relay between paired browsers. Match a 1–4 digit passcode; the first two browsers join directly, later browsers require approval from an existing device. Each file uploads independently, with resumable transfers, a shared list and native browser downloads.

Local disk, SQLite, one worker. New installations default to 1 GB per file and 500 GB per site. Administrators can lower both limits, which take effect immediately for uploads. Files last up to 24 hours, or 10 minutes after the first complete download, whichever is earlier.

```sh
docker compose build
docker compose up -d
```

Use HTTPS in production. For isolated local HTTP testing, set `APP_ENV=development`. Complete first-run setup and visit `/#/admin` for the three administration pages: overview, files and settings.

Retired anonymous sharing, presigned uploads, NAS file operations, external storage, text sharing and MCP are removed. A versioned database migration removes their unused schema and configuration while retaining Relay files, credentials, reservations, leases and original deadlines. See the [runtime and upgrade guide](docs/guide/filerelay.md), [cleanup inventory](docs/admin-cleanup-status.md), and [API contract](docs/api/relay.md).

Based on [FileCodeBox](https://github.com/vastsa/FileCodeBox), with upstream author information and the [LGPL-3.0 license](LICENSE) retained. [简体中文](readme.md).
