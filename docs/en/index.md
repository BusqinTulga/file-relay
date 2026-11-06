# FileRelay

Pair browsers with the same 1–4 digit passcode. The first two browsers join directly; later browsers require approval. Upload files independently, resume transfers and download from the shared list.

Local storage, SQLite and one worker. Administration has three pages: overview, files and settings. Defaults are 1 GB per file and 500 GB per site; administrators can lower both limits, effective immediately. Files last up to 24 hours or 10 minutes after the first complete download, whichever is earlier.

- [Operations, backup and upgrade guide](../guide/filerelay.md)
- [API contract](../api/relay.md)
- [Code and database cleanup results](../admin-cleanup-status.md)

Based on FileCodeBox, retaining upstream author information and LGPL-3.0. Legacy FileCodeBox documentation outside the current navigation is historical reference only.
