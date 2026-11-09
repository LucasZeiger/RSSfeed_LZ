from datetime import UTC, datetime

import httpx

from backend.export import atomic_json, read_json
from backend.models import MarketSeries, Price


class AlphaVantage:
    def __init__(self, key, cache_path, budget=20):
        self.key, self.path, self.budget = key, cache_path, budget
        self.cache = read_json(cache_path, {"day": "", "requests": 0, "series": {}})
        day = datetime.now(UTC).date().isoformat()
        if self.cache["day"] != day:
            self.cache.update(day=day, requests=0)

    def daily(self, instrument):
        existing = self.cache["series"].get(instrument.symbol)
        if existing and existing["fetched_at"][:10] == self.cache["day"]:
            return MarketSeries.model_validate(existing)
        if self.cache["requests"] >= self.budget:
            if existing:
                return MarketSeries.model_validate(existing)
            raise ValueError("Daily market request budget exhausted")
        self.cache["requests"] += 1
        atomic_json(self.path, self.cache)
        # Sequential requests, at most one/minute, enforced by the pipeline caller.
        with httpx.Client(timeout=20) as client:
            response = client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": instrument.symbol,
                    "apikey": self.key,
                    "outputsize": "compact",
                },
            )
            response.raise_for_status()
        body = response.json()
        daily = body.get("Time Series (Daily)")
        if not daily:
            raise ValueError(
                "Provider returned no daily prices; check quota, symbol and entitlement"
            )
        prices = [
            Price(date=day, close=float(row["4. close"])) for day, row in sorted(daily.items())
        ][-60:]
        series = MarketSeries(
            symbol=instrument.symbol,
            currency=instrument.currency,
            exchange=instrument.exchange,
            source="Alpha Vantage / TIME_SERIES_DAILY (unadjusted)",
            fetched_at=datetime.now(UTC).isoformat(),
            prices=prices,
        )
        if len(prices) >= 2:
            series.change_pct = round((prices[-1].close / prices[-2].close - 1) * 100, 3)
        self.cache["series"][instrument.symbol] = series.model_dump()
        atomic_json(self.path, self.cache)
        return series


def benchmark_returns(series, instruments):
    by_symbol = {s.symbol: s for s in series}
    for instrument in instruments:
        asset = by_symbol.get(instrument.symbol)
        benchmark = by_symbol.get(instrument.benchmark)
        if asset is None or benchmark is None:
            continue
        ap, bp = (
            {p.date: p.close for p in asset.prices},
            {p.date: p.close for p in benchmark.prices},
        )
        common = sorted(ap.keys() & bp.keys())
        if len(common) >= 2 and common[-1] == asset.prices[-1].date:
            start, end = common[-2:]
            own = (ap[end] / ap[start] - 1) * 100
            bench = (bp[end] / bp[start] - 1) * 100
            asset.benchmark_change_pct = round(bench, 3)
            asset.excess_return_pct = round(own - bench, 3)
            asset.comparison_dates = [start, end]
