"""Live source composition — real-time market + sentiment, no LLM, no key.

These factories build the plain callables the deterministic pipeline injects
(`load_bars` and `extra_drafts`). All HTTP lives here in the adapter layer;
`orchestration/` receives only callables, so its no-`httpx` boundary holds.

Neither source needs credentials: Binance spot klines and the Alternative.me
Fear & Greed index are public. Bedrock (news extraction, reasoning) is a
separate, credentialed layer added on top.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

import httpx

from hoya_agent.adapters.alternative_me import fetch_fear_greed
from hoya_agent.adapters.binance import fetch_binance_daily
from hoya_agent.data.types import MarketBar
from hoya_agent.evidence.types import EvidenceDraft

# Binance caps klines at 1000/request; 1000 daily bars ≈ 2.7 years, enough for a
# stable anomaly sigma (needs ≥365) without pagination. Deeper history (the ~5y
# the exchange can serve) is a startTime-paginated follow-up.
_DEFAULT_KLINE_LIMIT = 1000


def binance_bar_loader(
    analysis_as_of: datetime, *, limit: int = _DEFAULT_KLINE_LIMIT, timeout: float = 45.0
) -> Callable[[str], Sequence[MarketBar]]:
    """A sync `BarLoader(asset) -> bars` backed by live Binance daily klines.

    Raises ValueError when Binance yields nothing so the pipeline degrades that
    asset (its documented `load_bars` failure contract) rather than emitting an
    empty, misleading series.
    """

    def _load(asset: str) -> Sequence[MarketBar]:
        with httpx.Client() as client:
            bars, degradation = fetch_binance_daily(
                asset, analysis_as_of=analysis_as_of, client=client, limit=limit, timeout=timeout
            )
        if not bars:
            raise ValueError("; ".join(degradation) or f"Binance returned no bars for {asset}")
        return bars

    return _load


def fear_greed_drafts(
    analysis_as_of: datetime, *, timeout: float = 45.0
) -> Callable[[], tuple[list[EvidenceDraft], list[str]]]:
    """A sync `() -> (drafts, degradation)` for the live Fear & Greed index.

    Whole-market sentiment: one low-reliability `social` draft on its own
    independence group, so it adds a genuinely different source *type* to the
    ledger (the funnel stops being single-source) without any LLM call.
    """

    def _fetch() -> tuple[list[EvidenceDraft], list[str]]:
        with httpx.Client() as client:
            result = fetch_fear_greed(analysis_as_of=analysis_as_of, client=client, timeout=timeout)
        return list(result.drafts), list(result.degradation)

    return _fetch
