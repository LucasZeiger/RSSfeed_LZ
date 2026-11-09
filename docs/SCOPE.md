# Agreed implementation scope

Implementation foundation: Horizon upstream, with NewsLens comparison/export and website additions. See [UPSTREAM.md](../UPSTREAM.md).

NewsLens is a static, publicly readable website backed by a batch Python pipeline. The repository remains private unless its owner changes that independently. The interface is English. Reporting focuses on the US and UK, with German-language Austrian reporting retained in German. Clustering is within a language; translation and cross-language matching are deferred.

The homepage combines regions with region/category/publisher/leaning/time/search/financial filters. Stories sort primarily by recency, secondarily by distinct publishers. The initial slice includes a full dashboard, source comparison and financial exposure, an explicit offline demo, and real RSS through the same versioned JSON contract. The watchlist is mostly US with minor UK instruments; it is not a portfolio.

Coverage shows article and distinct-publisher counts, including unknown classifications. Political labels are country-contextual editorial assessments with provenance and review dates. They do not establish accuracy. Deterministic financial rules explain possible exposure, never predictions or trading recommendations. No API keys are required. Prices and AI enrichment are optional and missing integrations are visible, never replaced by synthetic data in real mode.

V1 includes safe bounded ingestion, retained state, conservative stable story clustering, evidence links, atomic export, hourly automation, optional daily market adapter, AI interface, responsive website, offline tests, lint/type/build checks and deployment documentation. No kiosk features, mandatory authentication, translation, scraping, portfolio positions, trading signals or continuously running backend.

Acceptance: a developer can install, generate demo data, run the site, ingest configured real RSS and build static output. Offline tests exercise parsing, unsafe destinations, clustering false positives, persistence and financial/market behavior. Browser checks exercise filters, details, mobile layout, demo/real separation and preferences. Live integrations are reported separately from fixture-based validation.
