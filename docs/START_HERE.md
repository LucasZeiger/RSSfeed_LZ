# Using NewsLens

Start with the demo, then connect real feeds. This guide describes the Horizon-based version.

**Current state:** the code is in `/workspace/RSSfeed_LZ` and has not been pushed to GitHub. The synthetic demo works. Real collection in this cloud environment is blocked by public DNS/outbound access; AI and market providers are optional and have not been tested with live accounts.

## 1. Start the demo

Prerequisites on a new machine: Python 3.12+, uv, Node.js 22+ and npm. Use Linux/macOS or WSL. On another machine, first transfer or push this checkout; cloning the currently empty GitHub repository will not fetch this local implementation.

In the current cloud terminal:

```bash
cd /workspace/RSSfeed_LZ
export UV_CACHE_DIR=/tmp/newslens-uv-cache
uv sync --frozen
npm ci --prefix web --cache /tmp/newslens-npm-cache
uv run newslens demo
npm run dev --prefix web
```

The writable cache locations are useful in this cloud environment; normal machines can use the tools' default caches. Open the address printed by Vite. If a server is already running on port 5173, use it rather than starting another; Vite otherwise chooses the next available port. Keep the terminal open. Ctrl+C stops the website server.

The banner says DEMO. All demo articles, publishers and market prices are fictional. No API keys are needed.

## 2. Explore the website

1. Start on **All news**. Use **United States**, **United Kingdom** or **Austria** to narrow the region. Austrian originals remain German.
2. Search for a topic or ticker, such as `NVDA`. Adjust the time window, publisher, perspective and financial-relevance filters.
3. Click a story headline. Read **What happened**, then compare the original headlines and excerpts across left/centre/right/unknown.
4. Switch **Articles / Publishers** to distinguish article volume from distinct publishers. Several feeds from the same configured publisher count once when they share `publisher_id`.
5. Follow an original source link to verify reporting. Demo links use example.com and are not real articles. In real mode, the default headline/overview are attributed source material rather than independently written neutral summaries.
6. Read **Possible economic consequences** as scenarios. Then inspect related instruments and dated price context separately. A nearby price change does not establish causation.
7. Open **Markets** or **Watchlist** for configured instruments. Missing live prices are expected until a market provider is enabled.
8. Open **Display & data settings** to choose a dataset. Filters and dataset/navigation preferences persist on this browser.

The **Refresh** button reloads published JSON. It does not fetch RSS or call AI. Collection is a separate terminal command or scheduled GitHub job.

## 3. Switch to real news

Keep the development server running. Open another terminal and run:

```bash
cd /workspace/RSSfeed_LZ
export UV_CACHE_DIR=/tmp/newslens-uv-cache
uv run newslens collect
uv run newslens validate
```

A successful or partial collection writes `web/public/data/latest.json`; the command prints source outcomes and article/story counts. Review partial failures. A total failure exits nonzero and retains previous valid output, writing the failed attempt to `status.json`.

Then choose **Switch to real news** or **Display & data settings → Real RSS data**. Appending `?data=live` explicitly selects real mode; `?data=demo` explicitly selects demo mode. A query parameter overrides saved preferences.

**Current cloud blocker:** public DNS and outbound HTTPS access to the configured feed hosts must work. Required hosts are `feeds.bbci.co.uk`, `www.theguardian.com`, `moxie.foxnews.com`, `rss.orf.at` and `www.derstandard.at`, plus any redirect destinations. A network allowlist alone does not fix missing DNS. Use a machine/GitHub runner with working DNS or update the environment. Do not remove URL or TLS safeguards. Real mode never falls back to fictional articles.

## 4. Choose sources and political classifications

Edit `config/feeds.yaml`, then run `collect` again. The browser has no administrative write controls.

- `enabled`: include/exclude a feed.
- `id`: stable unique feed identity; avoid changing it casually.
- `publisher_id`: shared publisher identity for multiple feeds.
- `country`: feed-edition region (`US`, `UK`, `AT`), not automatic event geolocation.
- `language`: `en` or `de`; cross-language clustering is deferred.
- `category`: Politics, World, Business or Technology for the corresponding navigation views.
- `political_leaning`: left, centre, right or unknown.

Example from the current configuration:

```yaml
- id: bbc-world
  publisher_id: bbc
  name: BBC World
  url: https://feeds.bbci.co.uk/news/world/rss.xml
  enabled: true
  category: World
  country: UK
  language: en
  political_leaning: unknown
```

Any non-unknown political label needs `classification.reviewer`, `classification.methodology` and `classification.reviewed_at`. Starter labels for Guardian US, Fox Politics and DER STANDARD are editorial proposals pending your review. Unknown never means centre; centre never means more accurate. Labels have different national contexts. Missing coverage refers only to configured sources.

## 5. Adjust the watchlist

Edit `config/instruments.yaml`, then run `collect`. Example:

```yaml
- symbol: NVDA
  name: NVIDIA
  exchange: NASDAQ
  currency: USD
  sector: Semiconductors
  aliases: [nvidia]
  keywords: [semiconductor, chip export]
  benchmark: SPY
```

This is a watchlist, not a portfolio or trading recommendation. Matching uses explicit names/phrases. Do not use generic ticker words as aliases. Optional market symbols must match the provider's exchange-specific conventions. GBX means pence, not pounds.

## 6. Enable AI only if wanted

The no-key workflow already collects, groups and compares news and explains rule-based financial exposure.

For model enrichment:

1. Set `ai_enabled: true` in `config/settings.yaml`.
2. Edit `config/horizon-ai.json` using Horizon's provider configuration. The default is OpenAI and expects backend environment variable `NEWSLENS_AI_KEY`. A local Ollama provider is another option; see Horizon's configuration documentation.
3. Supply the credential securely in your shell environment or as a GitHub Actions secret. Do not put it in the JSON, frontend or chat. `.env.example` is a template; this collector does not automatically load `.env`.
4. Run `uv run newslens collect` again.

Optional overrides: `NEWSLENS_AI_MODEL`, `NEWSLENS_AI_BASE_URL` (API base URL, e.g. ending in `/v1`, not `/chat/completions`). `semantic_clustering_enabled: true` permits model-assisted grouping when AI is enabled. Invalid/unavailable AI leaves deterministic functionality available with a status warning.

The comparison profile is in `config/profiles/newslens-comparison/`. It permits feed material only, requires article references and has no research tools. The original Horizon briefing profiles remain in `profiles/`. Model interpretation is not independently verified fact.

## 7. Enable historical prices only if wanted

1. Confirm Alpha Vantage account entitlements and display/redistribution rights, especially for a public website.
2. Provide `ALPHA_VANTAGE_API_KEY` in the backend environment or GitHub Actions secrets.
3. Set `market_enabled: true` in `config/settings.yaml`.
4. Run the collector. The conservative adapter can take about a minute per uncached instrument; cached runs are faster.

Default limits: one provider request per minute and 20 requests per UTC day. Data is cached in `data/markets-cache.json`. Prices are dated, unadjusted daily closes, not live quotes; splits/distributions can distort returns. No key means no real price data, not simulated substitute prices. Optional provider hosts must be allowed by the execution environment.

## 8. Build and automate

After a successful real collection:

```bash
VITE_DATA_MODE=live npm run build --prefix web
npm run preview --prefix web
```

Deploy the contents of `web/dist`. Building copies the current public JSON into the output; collecting afterward does not update an existing build. Rebuild after data changes. For GitHub project Pages, build with `BASE_PATH=/RSSfeed_LZ/`; for a root domain, use `/`.

To automate on GitHub after the local code has been pushed to your private repository's default branch:

1. Enable GitHub Actions. **Update news** supports manual execution and runs hourly at minute 17; schedules may be delayed.
2. Allow that workflow its scoped contents-write permission to persist bounded generated data/state. Protected branches may need another persistence strategy.
3. Add optional API secrets only if using those providers. No keys are required for RSS ingestion.
4. Leave `ENABLE_PAGES` unset until you intend public deployment. For Pages, confirm private-repository plan eligibility, choose GitHub Actions as the Pages source, and set repository variable `ENABLE_PAGES=true`.

A private repository does not guarantee a private website. Deployment has not been activated. Imported upstream docs deployment stays disabled. Other static hosts are supported; see README.md.

## Troubleshooting

| What you see | Meaning / next step |
| --- | --- |
| DEMO banner or simulated prices | You are viewing fictional data. Choose real mode only after collection succeeds. |
| No real dataset has been published | Run the collector and review source outcomes; do not rename demo.json to latest.json. |
| UnsafeURLError / failed feeds in this cloud | DNS/outbound access is blocked. Restore network access; retain security checks. |
| Pipeline partial | Healthy sources contributed, but others failed. Inspect the reported source IDs. |
| Stale dataset or failed refresh | The site retains its previous valid output. Check the ingestion job and redeploy/rebuild as needed. |
| Insufficient coverage for comparison | Fewer than two known political perspectives were collected for that story. Add/review sources; do not force labels. |
| Market price data not configured | Expected without the optional key, feature flag and provider access. Qualitative exposure still works. |
| AI unavailable | Check the feature flag, Horizon provider configuration and required backend credential. |
| Repeated or missing event groups | Lexical clustering is conservative; optional model grouping is imperfect too. Review thresholds and real examples. |

## Which command should I use?

- `uv run newslens ...`: prepares data for this comparison website.
- `uv run horizon ...`: Horizon's original AI-driven briefing workflow. Its other source connectors and delivery channels are available there, but are not all integrated into the comparison dashboard.

Full reference: README.md. Upstream integration/history: UPSTREAM.md. Previous prototype checkpoint: local branch `checkpoint/newslens-before-horizon`.
