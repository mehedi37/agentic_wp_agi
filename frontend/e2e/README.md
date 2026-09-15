# Playwright e2e smoke test

Prerequisites: a running backend reachable at `NEXT_PUBLIC_API_BASE_URL`
(default `http://localhost:8000/api`) with the demo users and sample data
seeded -- e.g. `make up && make seed`, or the host-run equivalent
(`uv run python -m scripts.seed` from `backend/`, against a running
postgres/redis). The frontend dev server itself is started automatically
by `playwright.config.ts` unless `E2E_BASE_URL` is set to point at an
already-running one.

```
npx playwright install chromium   # once, downloads the browser binary
npm run test:e2e
```

The "approve a pending action" test skips itself (rather than failing) if
no pending action exists -- run `make seed` first to get one from the
sample data's planted escalations.
