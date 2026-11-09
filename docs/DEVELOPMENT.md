# Development environment

Use the existing checkout in an isolated cloud task. Do not create a Git worktree unless explicitly requested.

```sh
cd /workspace/RSSfeed_LZ
UV_CACHE_DIR=/tmp/newslens-uv-cache uv sync --frozen
npm ci --prefix web --cache /tmp/newslens-npm-cache
.venv/bin/python -m backend.cli demo
npm run dev --prefix web -- --port 5173
```

Dependency caches use writable temporary locations in the managed environment. Use standard cache defaults on other machines. Nothing requires a globally installed package or privileged installation. Processes must restart in a new task; installed dependencies alone do not start the site.

Validation:

```sh
.venv/bin/pytest -q
.venv/bin/ruff check backend tests
.venv/bin/ruff format --check backend tests
npm run lint --prefix web
npm run build --prefix web
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e --prefix web
```

Outside this cloud image, install the Playwright browser with `cd web && npx playwright install chromium`, then run `npm run test:e2e` without the executable override.

## Current cloud network limitation

At implementation time, public DNS lookup failed both inside and outside the command sandbox. A direct proxied HTTPS request to the BBC feed received a CONNECT 403. The runtime custom outbound list was empty. Live feed retrieval therefore could not be verified here. The collector intentionally does not bypass its public-address DNS check when DNS is unavailable.

Required feed destinations: `feeds.bbci.co.uk`, `www.theguardian.com`, `moxie.foxnews.com`, `rss.orf.at`, `www.derstandard.at`; redirect hosts must also be permitted if a publisher changes them. Optional providers require `www.alphavantage.co` and the configured AI endpoint host. Public DNS must work in the collector execution environment. The pipeline can run on an ordinary machine or GitHub Actions runner without changing the static website architecture.

Saving reusable environment scripts and required feed domains through the cloud draft API returned `INVALID_ARGUMENT`; persistence could not be confirmed. The tested local instructions are retained here. This is independent of the GitHub workflow files.
