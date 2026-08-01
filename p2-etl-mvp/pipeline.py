"""Canonical end-to-end evidence pipeline — one function drives the whole P2 run.

`collect_evidence(asset)` gathers every source (market CSV + OKX + funding + regime
+ A5 attribution + A6 event timeline + news feeds + Google News + Reddit + Fear&Greed
+ LLM semantic extraction), builds the unified Evidence Ledger, and returns a Bundle.
`run_agent.py` (and the report renderer) call this so there is ONE source of truth.

- offline=True → only the organizer CSV (deterministic, no network/LLM).
- LLM provider auto-selects: Bedrock (BEDROCK_MODEL_ID) > GPT (OPENAI_API_KEY) > skip.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from adapters._assets import mentions
from adapters.alternative_me import fetch_fear_greed
from adapters.derivatives import fetch_funding_rate
from adapters.google_news import fetch_google_news
from adapters.okx import CANDLES_URL as OKX_URL
from adapters.okx import INDEPENDENCE_GROUP as OKX_GROUP
from adapters.okx import SOURCE_NAME as OKX_SOURCE
from adapters.okx import fetch_okx_daily
from adapters.organizer_csv import default_data_dir, load_organizer_csv
from adapters.reddit import fetch_reddit_posts
from adapters.rss import fetch_rss_news
from data.market_worker import build_market_evidence
from data.price_analysis import (
    build_attribution_evidence,
    build_comparison_evidence,
    build_event_timeline_evidence,
)
from data.regime import build_regime_evidence, classify_regime
from data.text_clean import clean_text
from evidence.processor import build_ledger
from evidence.types import EvidenceLedger
from reasoning.research_extractor import NewsRecord, extract_news_facts

UTC = timezone.utc
FEEDS = [
    ("https://www.coindesk.com/arc/outboundfeeds/rss?outputType=xml", "CoinDesk", "coindesk.com"),
    ("https://www.theblock.co/rss.xml", "The Block", "theblock.co"),
    ("https://bitcoinmagazine.com/feed", "Bitcoin Magazine", "bitcoinmagazine.com"),
    ("https://cryptoslate.com/feed/", "CryptoSlate", "cryptoslate.com"),
    ("https://decrypt.co/feed", "Decrypt", "decrypt.co"),
    ("https://cointelegraph.com/rss", "Cointelegraph", "cointelegraph.com"),
    ("https://www.newsbtc.com/feed/", "NewsBTC", "newsbtc.com"),
    ("https://bitcoinist.com/feed/", "Bitcoinist", "bitcoinist.com"),
    ("https://coinjournal.net/feed/", "CoinJournal", "coinjournal.net"),
]
_MAX_LLM = 10


@dataclass
class Bundle:
    asset: str
    as_of: date
    bars: list
    regime: object
    ledger: EvidenceLedger
    provider: str
    live_ok: bool
    notes: list[str] = field(default_factory=list)
    source_lines: list[str] = field(default_factory=list)
    drafts: list = field(default_factory=list)


@dataclass
class ComparisonBundle:
    asset_a: str
    asset_b: str
    as_of: date
    ledger: EvidenceLedger
    regime_a: object
    regime_b: object
    provider: str
    notes: list[str] = field(default_factory=list)
    comparison_facts: list[str] = field(default_factory=list)


def _rss_records(asset: str, client: httpx.Client, lookback_days: int = 30) -> list[NewsRecord]:
    now = datetime.now(UTC)
    earliest = now - timedelta(days=lookback_days)
    records: list[NewsRecord] = []
    for url, name, dom in FEEDS:
        try:
            resp = client.get(url, timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
        except (httpx.HTTPError, ET.ParseError):
            continue
        for item in root.iter("item"):
            t, d = item.find("title"), item.find("pubDate")
            desc, link = item.find("description"), item.find("link")
            if t is None or d is None or not (t.text or "").strip():
                continue
            title = t.text.strip()
            try:
                pub = parsedate_to_datetime(d.text)
            except (TypeError, ValueError):
                continue
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=UTC)
            if not mentions(asset, title) or pub > now or pub < earliest:
                continue
            records.append(NewsRecord(
                asset=asset, title=title, body=clean_text(desc.text if desc is not None else "") or title,
                source_name=name, publisher_domain=dom,
                source_url=(link.text if link is not None else url) or url, published_at=pub,
            ))
    return records


def collect_evidence(
    asset: str, *, offline: bool = False, client: httpx.Client | None = None,
    now: datetime | None = None, max_llm_articles: int = _MAX_LLM,
) -> Bundle:
    asset = asset.upper()
    now = now or datetime.now(UTC)
    data_dir = default_data_dir()
    drafts: list = []
    notes: list[str] = []
    lines: list[str] = []
    provider = "none"
    live_ok = True

    # 市場 + 市場狀態 + A6 事件時間軸（deterministic，官方 CSV）
    bars = load_organizer_csv(data_dir / f"{asset}_daily_ohlcv.csv")
    as_of = bars[-1].date
    m = build_market_evidence(asset, bars, analysis_as_of=as_of)
    r = build_regime_evidence(asset, bars, analysis_as_of=as_of)
    ev = build_event_timeline_evidence(asset, bars, analysis_as_of=as_of)
    drafts += list(m.drafts) + list(r.drafts) + list(ev.drafts)
    regime = classify_regime(asset, bars, analysis_as_of=as_of)
    lines.append(f"市場(官方CSV) {len(bars)} 筆 → {len(m.drafts)+len(r.drafts)+len(ev.drafts)} 證據")
    if asset != "BTC":  # A5 歸因 vs BTC
        btc = load_organizer_csv(data_dir / "BTC_daily_ohlcv.csv")
        drafts += list(build_attribution_evidence(asset, bars, btc, analysis_as_of=as_of).drafts)
        lines.append("歸因 vs BTC（相關性/beta）")

    if not offline:
        client = client or httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (research; hoya-market-agent/0.1)"},
            follow_redirects=True, timeout=15.0,
        )
        okx_bars, deg = fetch_okx_daily(asset, analysis_as_of=now, client=client)
        notes += deg
        if okx_bars:
            drafts += list(build_market_evidence(
                asset, okx_bars, analysis_as_of=okx_bars[-1].date,
                source_name=OKX_SOURCE, independence_group=OKX_GROUP, source_url=OKX_URL).drafts)
            lines.append(f"市場(OKX live) {len(okx_bars)} 筆")

        n_news = 0
        for url, name, dom in FEEDS:
            res = fetch_rss_news(asset, analysis_as_of=now, client=client,
                                 feed_url=url, source_name=name, publisher_domain=dom, lookback_days=30)
            drafts += list(res.drafts); notes += res.degradation; n_news += len(res.drafts)
        gn = fetch_google_news(asset, analysis_as_of=now, client=client, lookback_days=14)
        drafts += list(gn.drafts); notes += gn.degradation; n_news += len(gn.drafts)
        lines.append(f"新聞(9 媒體 + Google News) {n_news} 篇")

        records = _rss_records(asset, client)
        llm = None
        if os.getenv("BEDROCK_MODEL_ID") and records:
            from reasoning.bedrock_client import BedrockClient
            llm = BedrockClient(); provider = f"bedrock:{os.getenv('BEDROCK_MODEL_ID')}"
        elif os.getenv("OPENAI_API_KEY") and records:
            from reasoning.gpt_client import GptClient
            llm = GptClient(); provider = "openai-gpt (dev)"
        if llm is not None:
            ext = extract_news_facts(records[:max_llm_articles], llm=llm)
            drafts += list(ext.drafts); notes += ext.degradation
            lines.append(f"LLM 語意抽取({provider}) → {len(ext.drafts)} 筆事實")

        rd = fetch_reddit_posts(asset, analysis_as_of=now, client=client)
        drafts += list(rd.drafts); notes += rd.degradation
        lines.append(f"社群(Reddit) {len(rd.drafts)} 篇")
        fg = fetch_fear_greed(analysis_as_of=now, client=client)
        drafts += list(fg.drafts); notes += fg.degradation
        lines.append(f"情緒(Fear & Greed) {len(fg.drafts)} 筆")
        fr = fetch_funding_rate(asset, analysis_as_of=now, client=client)
        drafts += list(fr.drafts); notes += fr.degradation
        lines.append(f"衍生品(資金費率) {len(fr.drafts)} 筆")

    ledger = build_ledger(drafts)
    return Bundle(asset=asset, as_of=as_of, bars=bars, regime=regime, ledger=ledger,
                  provider=provider, live_ok=live_ok, notes=notes, source_lines=lines, drafts=drafts)


def collect_comparison(asset_a: str, asset_b: str, *, offline: bool = False) -> ComparisonBundle:
    """Lightweight 1–2 coin comparison (keeps the 1–2 coin contract). Each coin runs the
    full pipeline; cross-asset comparison evidence (relative return / correlation / beta /
    relative strength) is added. Cross-coin uses only returns/ratios — never base volume."""
    a, b = asset_a.upper(), asset_b.upper()
    ba = collect_evidence(a, offline=offline)
    bb = collect_evidence(b, offline=offline)
    as_of = min(ba.as_of, bb.as_of)
    comp = build_comparison_evidence(a, b, ba.bars, bb.bars, analysis_as_of=as_of)
    drafts = list(ba.drafts) + list(bb.drafts) + list(comp.drafts)
    ledger = build_ledger(drafts)
    facts = [d.normalized_fact for d in comp.drafts]
    return ComparisonBundle(
        asset_a=a, asset_b=b, as_of=as_of, ledger=ledger,
        regime_a=ba.regime, regime_b=bb.regime, provider=ba.provider,
        notes=ba.notes + bb.notes + comp.degradation, comparison_facts=facts,
    )
