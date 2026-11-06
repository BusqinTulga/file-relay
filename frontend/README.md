# FileRelay frontend

Vue 3 + TypeScript + Vite. Use Node 20 and pnpm 9.15.9.

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm build
```

Vite proxies `/api`, `/admin` and `/setup` to `127.0.0.1:12345`. The production build goes to `../themes/2024` and is served by FastAPI. See [architecture](ARCHITECTURE.md) and [runtime guide](../docs/guide/filerelay.md).
