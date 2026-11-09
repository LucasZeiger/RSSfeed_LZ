# Horizon migration validation

Migration performed on 9 November 2026 against Horizon revision `0a8d740b1a774f27ba9ffb612227ab87832a138c`. See [UPSTREAM.md](../UPSTREAM.md) for the preserved checkpoint, code provenance, customisation boundaries and upstream update procedure.

- The original standalone NewsLens is preserved locally at `checkpoint/newslens-before-horizon` (`a4d58b0`). Horizon's complete reachable history was fetched; the migration merge retains both parents and the upstream MIT licence.
- Locked Python dependencies installed with uv 0.13.5 on Python 3.12.14. Both `horizon --help` and `newslens --help` execute. `newslens demo`, schema generation and schema validation execute without API credentials.
- **1,001 tests passed** in the full combined Python suite, including inherited Horizon tests and NewsLens adapter tests. New tests exercise richer Atom content selection through the actual upstream parser, conditional/partial collection outcomes, source-preserving semantic grouping, model-loop reuse, hard language/time boundaries and publisher identity across multiple feeds.
- Two upstream test modules that mocked HTTP still made live example-domain DNS calls. Their DNS fixtures were made deterministic without disabling public-address validation or removing assertions. The custom comparison profile lives outside Horizon's default profile catalog, retaining original briefing profile behavior.
- Frontend lint, TypeScript compilation and production build pass. **Six Chromium tests passed**, exercising the dashboard, source dialogs, filters/preferences, mobile overflow, synthetic/real separation and failed-refresh retention.

## External checks and limits

A fresh `newslens collect` invocation reached the integrated guarded transport and Horizon public-address validator but all configured feeds failed public DNS validation in this cloud runtime. It exited nonzero, wrote failure status, and did not create an empty or fabricated live dataset. The earlier proxied BBC probe also returned CONNECT 403. Actual live feed ingestion is unverified here; using Horizon does not bypass the environment's egress policy.

Model enrichment, semantic grouping and market integrations were tested with fixtures/mocked providers, not paid-account calls. All original upstream source/delivery capabilities remain available through Horizon's CLI/MCP, but only RSS/Atom is currently adapted into the comparison website. No remote workflow, GitHub push, visibility change or public deployment was performed. The inherited Docker template was updated for Python/package compatibility but no container build/run was performed.

The previous standalone prototype's 27-test record is superseded by the combined migration suite. Current test totals and artifact paths are recorded in the final task response.
