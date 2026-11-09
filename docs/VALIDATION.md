# Validation record

Validated in the implementation cloud environment on 9 November 2026:

- Python 3.12.14, Node.js 24.22.1, uv 0.13.5; locked dependency installation.
- **27 passed** offline Python tests for RSS/Atom parsing, date normalisation, URL deduplication, unsafe destinations and redirects, size limits, conditional HTTP, clustering grouping/false positives/time/language/stable identity, pipeline repeatability/partial/total failure, financial matching, market cache/budget/returns, AI output references, settings bounds and output coverage counts.
- **6 passed** browser tests in system Chromium: demo labelling, source links and dialog keyboard access; region/search/insufficient evidence; persisted preferences; real mode without demo fallback; preservation after failed refresh; mobile navigation and no horizontal overflow; desktop screenshot inspection.
- Python lint/format validation, TypeScript type check, frontend lint and production build all passed. A separately served production build at `/RSSfeed_LZ/` rendered all six stories and opened the source dialog without browser exceptions.

Live RSS failed before collection: public DNS was unavailable and the proxy denied BBC HTTPS with a CONNECT 403. No successful live collection is claimed. Paid market/AI integrations were exercised with mocked HTTP responses only. GitHub workflows and public hosting were prepared locally, not run remotely. Environment draft persistence could not be confirmed because the configuration tool returned INVALID_ARGUMENT.

See the final task report for the latest executed test counts. A schema-valid/mock-tested integration does not establish live provider access, publishing rights or deployment success.
