"""Market adapters expose dated observations, never forecasts."""

from typing import Protocol

from backend.models import Instrument, MarketSeries


class MarketDataProvider(Protocol):
    def daily(self, instrument: Instrument) -> MarketSeries: ...
