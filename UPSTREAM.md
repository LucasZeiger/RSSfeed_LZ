# Horizon upstream and NewsLens customisation

NewsLens is a private customisation of [Thysrael/Horizon](https://github.com/Thysrael/Horizon), not a separately implemented replacement backend. Horizon's Git history and MIT licence are retained. The configured `upstream` remote points to the original project; `origin` remains the owner's repository.

Imported upstream revision: `0a8d740b1a774f27ba9ffb612227ab87832a138c` (350 commits in its reachable history).

The earlier standalone NewsLens implementation is preserved at local branch `checkpoint/newslens-before-horizon`, commit `a4d58b0`. This is a local checkpoint, not a pushed backup or a published branch.

## Reused upstream code

- `src/scrapers/rss.py`: RSS/Atom entry parsing, content/date handling, task scheduling, concurrency, per-host locks and per-entry failure isolation. NewsLens subclasses this collector and uses a safe conditional transport adapter.
- `src/url_security.py`: public-address DNS validation for the NewsLens transport.
- `src/processing/topics.py`: the non-destructive form of Horizon's semantic grouping, extracted from the original orchestrator. Both the original briefing's merge stage and NewsLens's source-preserving story grouping call this shared function.
- `src/ai/client.py`: actual provider factory and provider implementations, including native providers, compatible endpoints, fallback chains, authentication options and usage accounting.
- `src/processing/profiles.py` and `src/ai/enricher.py`: profile loading, prompt construction, structured artifacts, retry/validation and enrichment. The custom comparison profile permits feed evidence only, without web/history tools.
- Original `horizon`, `horizon-mcp`, `horizon-wizard`, provider setup and notification commands, source connectors, built-in profiles, tests, Docker files and documentation remain available.

## NewsLens additions

- `backend/horizon.py`: maps configured publishers to Horizon RSS sources and maps ContentItems to publisher-attributed Articles. It preserves explicit publisher identity across multiple feeds, errors/304 outcomes and explicitly permits flagged collection-time fallback when a feed date is missing/invalid/future.
- `backend/transport.py`: limited-size streaming, conditional HTTP state, standard-port policy, redirect validation and bounded retries. It calls Horizon's public-address validator instead of maintaining another DNS safety implementation.
- `backend/cluster.py`: offline lexical fallback, stable story identity, coverage counts, and validation of model-proposed groups against language/time bounds. It keeps all article records; Horizon's lossy representative-item merge is not used by the comparison website.
- `backend/ai/provider.py`: a thin adapter to Horizon's provider factory and ContentEnricher, with NewsLens-specific article/sentence-reference checks. A shared asyncio runner keeps pooled provider requests on one event loop.
- `config/profiles/newslens-comparison/`: the source-comparison editorial policy and structured blocks. The existing upstream finance-news and other profiles are retained.
- Existing financial exposure/price context, bounded JSON persistence, React website, demo dataset and browser tests.

The superseded custom RSS parser and bespoke OpenAI HTTP client have been removed from the active implementation. They remain recoverable through the checkpoint branch.

## Configuration and boundaries

The website's source list is `config/feeds.yaml`; publisher country, language and political classifications stay separate from Horizon's processing-profile classification. Optional model configuration uses Horizon's AIConfig schema in `config/horizon-ai.json`, selected only when `ai_enabled` is true in `config/settings.yaml`. `semantic_clustering_enabled` controls optional model grouping; no model is required for collection, comparison or financial rules.

The website currently connects Horizon's **RSS/Atom source path**. Other upstream connectors and delivery services are available through Horizon's original CLI/MCP/configuration, but their results are not yet mapped into NewsLens's publisher/coverage contract. Wiring them into the dashboard is a further integration, not an already completed feature.

Optional semantic grouping considers up to 40 newest articles per run; enrichment considers up to ten stories and 30 excerpts per story. All source articles remain in the dataset. Model proposals cannot join different languages or clusters spanning more than the configured event window. Failed/unconfigured AI leaves lexical grouping and deterministic comparison available; it does not fabricate summaries.

Horizon's normal briefing command continues to use its original AI-driven score/filter/merge behavior. NewsLens uses a separate publisher-preserving path. The guarded transport guarantees described in the NewsLens README apply to `newslens collect`, not every inherited connector or command.

## Upstream changes kept small

1. RSS parsing is exposed as a transport-independent method; its original fetch method delegates to it. Date fallback, entry bounds and concurrency overrides are optional and preserve original defaults.
2. Semantic grouping is extracted into a reusable function. The original orchestrator still chooses the highest-scored representative and merges text/comments, using those same groups.
3. Packaging adds the NewsLens CLI/module, dependency group and small extra dependencies. The inherited Docker template is aligned with Python 3.12 and includes the extension/configuration; container execution was not validated in this task.
4. Two HTTP-mocked upstream test modules now use deterministic example-domain DNS, keeping URL safety checks and assertions active without a live network dependency.
5. NewsLens site deployment remains opt-in. Horizon's imported docs-deployment workflow was renamed `.disabled` to prevent accidental publication from the private fork. The original disabled daily-summary workflow stays disabled.

## Updating upstream

Use the existing checkout, with a clean committed worktree:

```sh
git fetch upstream main
git log --oneline HEAD..upstream/main
git merge upstream/main
UV_CACHE_DIR=/tmp/newslens-uv-cache uv sync
uv run pytest
npm ci --prefix web
npm run lint --prefix web
npm run build --prefix web
```

Resolve changes to the shared RSS/grouping hooks explicitly. Do not reset local customisation or blindly overwrite the lockfile. Review and regenerate the lockfile when dependency declarations change. Run upstream regression tests together with `tests/newslens`; do not substitute fixture-only adapter tests for the inherited suite. Nothing in this procedure changes repository visibility, enables publication or pushes commits automatically.
