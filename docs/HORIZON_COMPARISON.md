# Horizon compared with the pre-migration NewsLens prototype

**Historical review:** this document describes the standalone prototype before the Horizon migration. The current implementation reuses Horizon; see [UPSTREAM.md](../UPSTREAM.md).

Source review: 9 November 2026. Horizon revision inspected: [`0a8d740b1a774f27ba9ffb612227ab87832a138c`](https://github.com/Thysrael/Horizon/tree/0a8d740b1a774f27ba9ffb612227ab87832a138c). Cloned outside the application checkout at `/workspace/tools/Horizon`. This is a source inspection, not a live execution or benchmark of Horizon. No Horizon application code has been incorporated into NewsLens.

## Core difference

Horizon is an AI-driven, profile-based daily briefing generator. NewsLens is a source-preserving event comparison website with optional enrichment. They share Python, feedparser, httpx, Pydantic, file-based output and static hosting, but their central data models and selection policies differ.

| Area | Horizon implementation | Current NewsLens implementation | Practical consequence |
| --- | --- | --- | --- |
| Pipeline | Fetch → URL merge → AI analysis → profile thresholds → AI topic merge → category balancing → enrichment → localised Markdown/delivery | Fetch → URL dedup → retained article state → lexical event clusters → coverage metrics → financial rules → optional AI/prices → JSON | Horizon selects a digest; NewsLens retains collected reporting for comparison. |
| Sources | RSS/Atom, Hacker News, Reddit, Telegram, X, GitHub, OpenBB company news, OSS Insight, GDELT, Google News | RSS/Atom only | Horizon has substantially broader connector infrastructure. Many connectors need separate accounts or dependencies. |
| RSS implementation | Async client, task group, three-feed semaphore, per-host locks, 429 handling; chooses the longest supported content/summary candidate; supports optional extraction | Thread pool capped at four, per-host request spacing, bounded redirects/bytes/time, retry/backoff, ETag/Last-Modified; summary field limited to 600 characters | Horizon handles richer feed content; NewsLens has conditional-request state and deliberately bounded excerpts. |
| Missing publication time | Attempts published/updated/created and excludes items without a usable date | Uses published/updated structured fields; missing/future times become flagged collection times | NewsLens retains uncertain-date items, which can appear recent even when their real publication time is unknown. |
| URL deduplication | Normalises more tracking parameters, default ports and trailing slashes; groups by URL and requested profile; keeps richest content and merges metadata/content | Canonical URL hash, fewer tracking parameters, query sorting; first retained article wins | Horizon preserves more supplemental content. NewsLens can lose secondary feed attribution for an identical URL; distinct article URLs remain separately represented. |
| Same-event grouping | LLM identifies identical-event groups per profile; highest-scored representative survives, with duplicate source text/comments appended | Requires three shared headline terms, Jaccard threshold 0.32, same language, 48-hour anchor window; preserves article records and reuses story IDs | Horizon can potentially recognise paraphrases that lexical matching misses; no accuracy comparison was performed. Its merge output cannot directly supply reliable publisher-level coverage counts. |
| Ranking and filters | Configurable 0–10 AI scoring rubrics, thresholds and balanced-digest category caps | Recency first, publisher count as tie-breaker; user filters; no AI importance score | Horizon has richer relevance selection. NewsLens avoids hiding perspectives because they failed an importance threshold. |
| Editorial configuration | JSON profile definitions plus Markdown matching/analysis/enrichment prompts, optional blocks and allowlisted tools | YAML source/watchlist/settings; comparison schema and financial rules in Python | Horizon makes editorial treatment much more configurable without Python changes. |
| AI | Multiple native/compatible providers, provider fallback chains, local Ollama, ChatGPT authentication, retries and token accounting; normal full briefing path uses AI | One opt-in OpenAI-compatible adapter with schema and article-reference checks; deterministic core | Horizon has much broader AI infrastructure. It can avoid paid API keys with a suitable local/authenticated provider, but that is still a model dependency. |
| Research/context | Allowlisted web search and historical-summary search; optional community comments and full-text extraction | Feed excerpts only; no web research, historical context retrieval or community ingestion | Horizon can generate deeper context. Broader material changes provenance, copyright, network and prompt-injection boundaries. |
| Politics | Processing-profile classification, e.g. finance versus tech; no dedicated left/centre/right/unknown publisher coverage model found in inspected code | Explicit source political classifications, country context, provenance, article/publisher metrics and original-headline columns | Horizon's "classification" means a different thing; it does not implement the comparison feature NewsLens needs. |
| Finance | OpenBB company-news/optional filing source and a finance-news editorial profile with summary/background/optional impact; prompts warn against trading advice and causal overclaims | Deterministic exposure rules, explicit instrument matches/evidence, scenario fields, optional dated Alpha Vantage prices and aligned benchmark returns | Horizon already has financial-news analysis; its OpenBB scraper is not a historical-price dashboard. |
| State/output | JSON configuration and subscriber state; dated Markdown summaries with historical retrieval; MCP has run persistence | Bounded article/seen/cluster/market JSON state, atomic latest dataset and independent attempted-run status | Both use files. Horizon's historical summary search is not the same as NewsLens's persistent article-to-story identity. |
| Website | Jekyll/Markdown Pages site with custom CSS/JavaScript, score badges and English/Chinese controls | React/TypeScript/Vite/Tailwind static application, interactive source comparisons, market charts, browser filters/preferences, English UI and German originals | Reusing Horizon does not supply NewsLens's existing dashboard experience. |
| Operations/delivery | CLI, Docker, setup wizard, MCP server, email, webhooks, WeChat; disabled daily workflow template plus docs deployment | CLI, hourly update workflow, CI and opt-in static Pages deployment | Horizon offers far broader automation/delivery interfaces. NewsLens currently focuses on the website. |

## Most important gaps in NewsLens

1. **Semantic story matching.** The current lexical algorithm will miss differently worded reports of the same event. Demo headlines deliberately share substantial wording; demo success does not establish realistic paraphrase performance. A reviewed US/UK/German event fixture set should guide any improvement.
2. **Context and analysis depth.** Without optional AI, live titles/overviews are attributed source excerpts; deterministic comparison does not establish factual agreements, omissions or disagreements. Horizon has a much more developed enrichment pipeline.
3. **Feed-content handling.** NewsLens currently reads `summary`, while Horizon considers Atom/RSS content alternatives and chooses the richest supported text. Improving feed-provided content selection is compatible with the feed-only scope; unrestricted article extraction is not.
4. **Connector/provider extensibility.** NewsLens has minimal provider interfaces. Horizon already has a common scraper contract, extensive source implementations, configurable profiles and AI provider fallback/usage handling.
5. **Live evidence.** NewsLens has offline and browser validation, but live ingestion here remains blocked by cloud DNS and outbound policy. This review does not remove that blocker or establish Horizon would work on the same network.

## Reuse recommendation

Keep NewsLens's Article → Story data model, source/publisher classifications, evidence links, static JSON contract and React interface. Selectively adapt Horizon's feed-content handling, provider abstractions and editorial-profile approach. Its finance-news profile is a useful reference for evidence-sensitive summaries and meaningful economic baselines.

Any semantic grouping adapter should return candidate article-ID groups, validate them, and keep every constituent publisher/headline/link. Do not directly substitute Horizon's representative-item merge or apply its score thresholds before measuring coverage: those operations can remove the evidence the comparison is meant to display. Optional AI must stay optional for the basic workflow. Embeddings or LLM grouping need offline evaluation and a lexical fallback, with uncertainty visible.

A wholesale use of Horizon's orchestrator would require an explicit integration layer, changes to its AI-first selection assumptions and a structured output adapter. It would also import delivery/source capabilities outside the agreed V1. This is an architectural integration task, not a drop-in dependency swap.

## Security and licence observations

Horizon is MIT-licensed. Reuse is allowed with preservation of its copyright and permission notice in copied/substantial portions; check licences of any newly introduced dependencies too.

Both projects have public-destination URL checking, but wiring differs: Horizon's trafilatura extractor calls `safe_request`, while the inspected RSS scraper uses its async client's automatic redirects directly. NewsLens applies its public-DNS check before every feed redirect and bounds response size. This is a specific source-level observation, not a security audit or proof one project is secure. Both need appropriate egress controls to address separate DNS resolution and connection behavior.

## Primary source locations

Horizon links are pinned to the inspected revision:

- [Pipeline, URL merge, semantic topic merge and digest selection](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/orchestrator.py)
- [RSS ingestion and content selection](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/scrapers/rss.py)
- [Content/analysis/artifact models](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/models.py)
- [Profile system](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/processing/profiles.py)
- [Finance-news profile](https://github.com/Thysrael/Horizon/tree/0a8d740b1a774f27ba9ffb612227ab87832a138c/profiles/finance-news)
- [OpenBB company-news scraper](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/scrapers/openbb.py)
- [AI clients and fallbacks](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/ai/client.py)
- [Historical-summary retrieval](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/processing/history.py)
- [URL security helpers](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/src/url_security.py)
- [MIT licence](https://github.com/Thysrael/Horizon/blob/0a8d740b1a774f27ba9ffb612227ab87832a138c/LICENSE)

NewsLens: `backend/cli.py`, `backend/feeds.py`, `backend/cluster.py`, `backend/models.py`, `backend/financial.py`, `backend/market/alpha.py`, `backend/ai/provider.py`, `web/src/App.tsx`, `config/` and `.github/workflows/`.
