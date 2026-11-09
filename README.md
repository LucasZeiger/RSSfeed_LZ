# NewsLens

**See the whole story.** A self-hostable news comparison dashboard with source-linked financial context. English interface; US and UK coverage with German-language Austrian reporting. Static React frontend, Python batch collector, versioned JSON, no database or persistent Python server.

The repository's visibility is never changed by the application or its workflows. A deployed website can be public even when this repository is private.

## Quick start — no keys required

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22+ and npm. Linux/macOS are supported; use WSL on Windows (the collector uses a POSIX file lock).

```sh
uv sync --frozen
npm ci --prefix web
uv run python -m backend.cli demo
npm run dev --prefix web
```

Open the development server's printed address in your browser. The default development mode is **synthetic demo**: six stories, fourteen articles, three fictional political perspectives plus unknown, an Austrian story in German, insufficient-coverage examples and simulated prices. A persistent banner labels the entire experience. Fictional source links use `example.com` and are not real news.

```sh
# Real news: network access and public DNS required, no API keys required
uv run python -m backend.cli collect
uv run python -m backend.cli validate
```

Choose **Switch to real news**, select Real RSS in Display & data settings, or append `?data=live` to the website URL. `?data=demo` explicitly selects the synthetic dataset. Real mode never substitutes fabricated content. If no real output exists, it shows an actionable empty/error state. Region, navigation and dataset preferences persist in localStorage; browser storage failure is harmless.

For restricted managed cloud environments, see [development setup and current network limitations](docs/DEVELOPMENT.md). Live feed requests could not be verified in the implementation environment because outbound feed access was denied and DNS was unavailable. The candidate URLs in the starter configuration must be verified on the deployment runner; update or disable any publisher that rejects automated RSS access. The offline fixture tests do not claim live availability.

## What is implemented

- Dark, responsive dashboard, category/region navigation, search, time/publisher/political/financial filters, source-count cards and accessible native story dialogs.
- Source-linked, side-by-side left/centre/right/unknown headlines with classification provenance, article counts and distinct-publisher counts. Unknown is never silently centre.
- Configurable RSS 2.0 / Atom ingestion, bounded concurrency, one-second per-host request spacing, timeout/size/deadline limits, conditional HTTP, bounded retry/backoff and redirect validation.
- UTC normalisation, HTML removal, exact URL deduplication, bounded seen state, conservative same-language clustering and best-effort stable story IDs.
- Deterministic financial categories, evidence-linked mechanisms, positive/negative scenarios and asset matching against a small US-focused watchlist with a few UK instruments.
- Optional cached Alpha Vantage daily-price adapter; optional OpenAI-compatible structured analysis adapter. Both are disabled by default and have mocked offline tests. Neither has been validated against a paid account.
- Versioned JSON schema, backend and browser validation, atomic output replacement, per-feed failure isolation, retention of prior valid output on total collection failure and separate run-status reporting.
- CI, hourly scheduled/manual ingestion, bounded generated-state persistence and optional Pages deployment. No deployment was performed during implementation.

Dedicated kiosk features and cross-language clustering are deferred by the agreed [scope](docs/SCOPE.md). There is no administrative write UI, user account system, full-article scraping, portfolio storage, trading signal or price prediction.

## Project layout

```text
backend/
  cli.py             collection, validation, demo and schema commands
  models.py          public Pydantic data contract
  feeds.py           safe bounded fetches and RSS/Atom parsing
  normalize.py       URL, text and timestamp helpers
  cluster.py         event similarity and persistent identity reuse
  financial.py       evidence-linked financial mechanism rules
  export.py          atomic JSON reads/writes
  demo.py            deterministic synthetic dataset
  market/alpha.py    cached daily prices and aligned benchmark returns
  ai/provider.py     optional schema-validated model interpretation
config/              feeds.yaml, instruments.yaml, settings.yaml
fixtures/            offline RSS and Atom samples
web/src/             React UI, types, generated JSON schema and styles
web/e2e/             Playwright functional and responsive checks
web/public/data/     demo.json; collector publishes latest.json/status.json
data/               bounded private pipeline state and market cache
.github/workflows/   CI, hourly updates and optional deployment
docs/                agreed scope and development instructions
GLOSSARY.md          settled domain language
```

`uv.lock` and `web/package-lock.json` pin resolved dependencies. Fonts are self-hosted package assets; demo mode needs no external news, font, AI or market service.

## Configure RSS sources

Edit `config/feeds.yaml`. Each entry needs a unique ID, publisher name, real feed URL, enabled flag, category, country (`US`, `UK`, `AT`), language (`en`, `de`) and political leaning. Supported UI categories are Politics, World, Business and Technology; All news also includes other configured categories. Geography describes the configured feed edition, not an automatically inferred event location. Feed metadata/category is the initial classification; article tags are retained but do not override it.

```yaml
feeds:
  - id: publisher-id
    name: Publisher name
    url: https://publisher.example/rss
    enabled: true
    category: Politics
    country: US
    language: en
    political_leaning: unknown
```

The URL above illustrates the format, not a working feed. Starter candidates include BBC World/Business, Guardian US, Fox Politics, ORF and DER STANDARD. Every run reports individual source outcomes. Disable feeds that are unavailable or whose reuse terms do not suit your deployment. Content stays limited to short feed excerpts (600 characters), original headlines and attribution links; no full-article scraping.

### Political classifications

Use `left`, `centre`, `right` or `unknown`. A classified publisher must have all of:

```yaml
political_leaning: left
classification:
  reviewer: Your name or review process
  methodology: Reason for the classification in this country's political context
  reviewed_at: '2026-11-09'
```

Guardian US, Fox Politics and DER STANDARD have explicitly marked **editorial proposals pending owner review**, not commercial bias ratings. Public-service and other unreviewed publishers remain unknown. Review those proposals before relying on the live comparison; change or remove any classification you disagree with. Country-contextual left/right labels are not directly interchangeable across the US, UK and Austria. The UI explains this limitation.

Coverage bars show only the configured, collected dataset. Article counts and publisher counts are distinct. Deduplicated syndicated URLs do not multiply article counts. Fewer than two known political categories produces **Insufficient coverage for comparison.** Missing coverage means none was found in configured sources, not none exists. Different framing is not proof of dishonesty; a centre label is not a truthfulness score.

### Clustering and interpretation

URLs are canonicalised by dropping fragments and known tracking parameters while preserving other query parameters. Exact article URLs share an identifier; repeated entries and already-seen IDs are not ingested twice.

Clustering compares normalised headline token sets, requires at least three shared non-stopword terms and a configurable Jaccard similarity threshold (default 0.32). Articles must have the same language and lie within 48 hours of the cluster's anchor article. Comparing against an anchor limits transitive topic drift. Existing article-to-story assignments preserve a cluster's prior ID where possible; merges use the dominant prior identity and splits may receive new IDs. Ambiguous articles can remain singleton stories. This is conservative lexical matching, not semantic understanding; missed matches and false merges remain possible.

Without AI, the live title and overview are clearly identified source headlines/excerpts, not independently authored neutral summaries. The comparison shows exact headlines and shared words, and does **not** invent factual agreements, omissions or disagreements. Published times missing, invalid or in the future are conservatively replaced with collection time and flagged.

## Financial exposure and market APIs

Edit `config/instruments.yaml` to change the watchlist: symbol, exchange, currency, sector, aliases, evidence keywords and optional benchmark. It is a watchlist, not a record of ownership. Generic ticker words are not matched: explicit company aliases or configured sector phrases must occur in an article's title/excerpt.

Rules cover rates/inflation, trade/tariffs, energy, semiconductor controls, defence spending, earnings, disruptions and government spending/regulation. Each exposure includes the triggering articles, economic mechanism, possible benefits/pressures, horizon, uncertainties and explanations for any asset match. A sector can be relevant even when no individual asset has enough evidence.

### Optional Alpha Vantage

1. Review current provider API, entitlement, display and redistribution terms. Public price display is **not enabled by default**; an API key does not grant redistribution rights.
2. Export `ALPHA_VANTAGE_API_KEY` in the backend environment (or add it as a GitHub Actions repository secret).
3. Set `market_enabled: true` in `config/settings.yaml` after confirming your use is permitted.
4. Run the collector. Add the provider host `www.alphavantage.co` to restricted network policies if needed.

The adapter uses `TIME_SERIES_DAILY`, cached once per UTC day, with a conservative maximum of one request per minute and 20 requests per day. Quotas vary by plan; lower the daily budget if needed. A budget exhaustion returns previously cached data when available. Provider failures preserve cached series with their original dates. Credentials stay in the backend. The `.env.example` is a template: `.env` files are not automatically loaded.

Prices are **unadjusted**, dated historical closes in each instrument's native currency (`GBX` means pence). Splits/distributions can distort returns. The last two available trading observations determine close-to-close change; weekends/holidays do not create fabricated prices. Benchmark returns use shared observation dates and report the comparison period. Currency conversion is out of scope. Some configured exchange symbols may require provider-specific corrections or entitlements. Missing data remains missing.

Price movements are observed data; mechanisms are scenarios; causation is not established. NewsLens never recommends buying/selling or generates price targets.

### Optional AI

Export `NEWSLENS_AI_KEY`; optionally set `NEWSLENS_AI_URL` (default OpenAI chat-completions endpoint) and `NEWSLENS_AI_MODEL`. Set `ai_enabled: true` and allow the configured endpoint host if network access is restricted. Add GitHub secrets/variables with those same names for scheduled runs. Only the ten newest stories per run are considered, limiting cost; this adapter does not continuously poll.

The adapter supplies only feed headlines/excerpts and IDs as untrusted user data with a separate system instruction, requests JSON, validates the result with Pydantic and requires article references for each substantive claim. It stores model identity and timestamp. Invalid output is discarded and deterministic comparison remains. Schema/reference validity cannot guarantee factual accuracy or eliminate prompt injection; review generated interpretations before relying on them. Source excerpts are sent to the chosen provider only when explicitly enabled.

## Data contract, state and freshness

`web/src/dataset.schema.json` is generated from `backend.models.Dataset`:

```sh
uv run python -m backend.cli schema
```

The public contract is one atomic `data/latest.json` file containing `schema_version: 1`, mode, generation timestamp, source/article/story/instrument lists, market series and run status. `data/demo.json` uses the same contract. `data/status.json` independently records the latest attempted run, so a failed ingestion can be visible while the previous valid dataset remains intact. The frontend validates downloaded data against the schema before replacing its current dataset.

An all-failed or empty run leaves the previous published dataset and state untouched, writes failure status and exits nonzero. A partial run retains recent articles from failed sources, continues healthy sources and reports errors. State is limited to seven days/1,500 articles and 10,000 seen IDs by default. Market series contain at most 60 observations per instrument. JSON files are bounded, but committing frequent updates still grows Git history over time; move persistence to object storage or periodically maintain history for long-lived installations.

The UI shows generation time, last completely successful collection, latest attempted failures and stale published data (>3 hours). Daily price dates and source attribution remain visible. Visible tabs reload published data at the configured interval (60 minutes default, minimum 5); hidden tabs skip requests. A refresh failure keeps the current valid display. No live backend is needed. Run only one local collector at a time; a file lock prevents simultaneous writes. GitHub workflow concurrency serialises scheduled updates.

## Tests and production build

```sh
uv run pytest -q
uv run ruff check backend tests
uv run ruff format --check backend tests
npm run lint --prefix web
npm run typecheck --prefix web
npm run build --prefix web
cd web
npx playwright install chromium
npm run test:e2e
```

Python tests use RSS/Atom and HTTP fixtures, including correct and false-positive clusters, deduplication, conditional requests, unsafe destinations/redirects, size limits, partial/total failures, state repeatability, financial matching, market caching and AI reference rejection. Playwright tests exercise browser interaction, persistence, insufficient evidence, mobile overflow, source links, demo/real separation and retention after failed refresh. Tests do not depend on live news or paid APIs.

For a real-data static build:

```sh
uv run python -m backend.cli collect
VITE_DATA_MODE=live npm run build --prefix web
npm run preview --prefix web
```

Deploy the **contents of `web/dist`**. For a subdirectory deployment set `BASE_PATH=/your-repository/` at build time; Vite applies it to scripts and data requests. A query parameter explicitly overrides the saved dataset preference, which overrides the build default.

## Scheduled updates and private-repository hosting

Push the project to your private repository when ready. No push, visibility change or deployment is performed automatically by local setup.

- `ci.yml`: Python tests/lint/format, TypeScript checking, frontend lint/build and Playwright checks on pushes/PRs.
- `update-news.yml`: hourly at minute 17 (GitHub may delay scheduled runs), plus manual **Run workflow**. It must be on the default branch with Actions enabled. The job installs locked dependencies, collects/validates data and commits only bounded output/state using the repository-scoped `GITHUB_TOKEN`. Grant that workflow contents-write access; protected branches may need a different persistence strategy. Jobs are serialised and pushes are never forced. A conflicting user push fails safely; rerun instead of resetting user changes.
- `deploy.yml`: optional Pages build/deploy after a successful update or manual dispatch. It is disabled unless repository variable `ENABLE_PAGES` is exactly `true`. Set Pages source to **GitHub Actions** and enable the variable only when you intend public publication. It builds with real mode by default and requires a real dataset. Deployment uses only `pages:write` and `id-token:write` in its deployment job.

Private-repository Pages eligibility depends on your GitHub account/organisation plan. A private repository does **not** imply a private website. If Pages is unavailable, Cloudflare Pages or any static host can build with `npm ci --prefix web && VITE_DATA_MODE=live npm run build --prefix web`, output `web/dist`; use `/` as `BASE_PATH` for a root domain. A host that skips bot commits will need a deploy hook or separate artifact deployment. No hosting provider is required for local development.

Generated `latest.json`, `status.json`, state and market cache are ignored for normal local work. The update workflow explicitly stages its known outputs. State and caches are **not** included in the website artifact; public JSON contains only intended display content. Never place secrets or private portfolio data in any public dataset.

## Security boundaries and limitations

Requests permit only HTTP(S), standard ports and credential-free URLs. Public DNS results are checked for every destination and redirect; private/loopback/link-local/metadata addresses are rejected. DNS failure blocks fetching. HTTPS verification stays enabled. Streamed responses have decompressed byte and time bounds; malformed entries are isolated. React renders source text as text, never raw HTML.

The collector is a trusted-configuration batch tool, not a public URL-fetch service. DNS checks and the eventual connection can resolve separately (especially through a proxy): use an outbound firewall/proxy that also blocks private destinations to defend against DNS rebinding. Do not grant it private-network access or expose feed configuration as an untrusted public API. A controlled egress policy complements application checks. Market/AI endpoints are administrator-controlled backend settings.

Remaining limitations: current live-feed access is unverified in this cloud environment; lexical clustering can miss paraphrases; languages do not cross-cluster; classifications require human review; neutral live summaries require reviewed enrichment; market/AI account access and public price rights are unverified; deployment is prepared but not activated. The website is fully usable in explicit offline demo mode.

## Prioritised V2 roadmap

1. Verify and expand the real source set; calibrate event clustering with reviewed US/UK/Austrian examples.
2. Add human-reviewed event titles and claim-level evidence validation for optional model output.
3. Add multilingual/cross-language matching behind evaluation fixtures.
4. Move retained data/history to object storage or SQLite when Git persistence becomes cumbersome.
5. Improve market-provider entitlements, adjusted-price support and per-exchange calendars.
6. Revisit dedicated kiosk mode and accessibility preferences if needed.
