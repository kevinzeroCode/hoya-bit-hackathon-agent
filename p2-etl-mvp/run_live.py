"""Full LIVE run for one coin — REAL news + social + REAL LLM semantic extraction.

Run this on YOUR machine (needs outbound network). Free, no key:
  - News:      Decrypt + Cointelegraph RSS (first-party outlet feeds, medium)
  - Social:    Reddit r/CryptoCurrency (best-effort; 403 from datacenter IPs)
  - Sentiment: Alternative.me Fear & Greed (whole-market, low)
  - Market:    real organizer CSV (deterministic, high)
The LLM semantic layer (clean -> {relevant, event_type, facts[]}) runs on the SAME
real articles IF OPENAI_API_KEY is set (GptClient). No key -> that layer is skipped
and clearly disclosed, so nothing fake ever enters the ledger. Production swaps
GptClient -> BedrockClient (one line; both satisfy LLMClient).

    $env:OPENAI_API_KEY = "sk-..."      # optional: enables the LLM layer
    python run_live.py BTC
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from adapters._assets import mentions
from adapters.alternative_me import fetch_fear_greed
from adapters.organizer_csv import default_data_dir, load_organizer_csv
from adapters.okx import CANDLES_URL as OKX_URL
from adapters.okx import INDEPENDENCE_GROUP as OKX_GROUP
from adapters.okx import SOURCE_NAME as OKX_SOURCE
from adapters.okx import fetch_okx_daily
from adapters.reddit import fetch_reddit_posts
from adapters.rss import fetch_rss_news
from data.market_worker import build_market_evidence
from data.regime import build_regime_evidence, classify_regime
from data.text_clean import clean_text
from evidence.processor import build_ledger
from reasoning.research_extractor import NewsRecord, extract_news_facts

UTC = timezone.utc
# Six first-party crypto outlets — each a distinct independence group (medium).
# All verified reachable; parsed by fetch_rss_news (RFC-822 pubDate).
FEEDS = [
    ("https://www.coindesk.com/arc/outboundfeeds/rss?outputType=xml", "CoinDesk", "coindesk.com"),
    ("https://www.theblock.co/rss.xml", "The Block", "theblock.co"),
    ("https://bitcoinmagazine.com/feed", "Bitcoin Magazine", "bitcoinmagazine.com"),
    ("https://cryptoslate.com/feed/", "CryptoSlate", "cryptoslate.com"),
    ("https://decrypt.co/feed", "Decrypt", "decrypt.co"),
    ("https://cointelegraph.com/rss", "Cointelegraph", "cointelegraph.com"),
]
_MAX_LLM_ARTICLES = 8  # cap real GPT calls to control cost


def _rss_records(asset: str, client: httpx.Client, lookback_days: int = 30) -> list[NewsRecord]:
    """Parse the SAME live feeds into NewsRecords (title + body) for the LLM layer."""
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
            title_el, date_el = item.find("title"), item.find("pubDate")
            desc_el, link_el = item.find("description"), item.find("link")
            if title_el is None or date_el is None or not (title_el.text or "").strip():
                continue
            title = title_el.text.strip()
            try:
                published = parsedate_to_datetime(date_el.text)
            except (TypeError, ValueError):
                continue
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            if not mentions(asset, title) or published > now or published < earliest:
                continue
            body = clean_text(desc_el.text if desc_el is not None else "")
            records.append(
                NewsRecord(
                    asset=asset,
                    title=title,
                    body=body or title,
                    source_name=name,
                    publisher_domain=dom,
                    source_url=(link_el.text if link_el is not None else url) or url,
                    published_at=published,
                )
            )
    return records


def main() -> None:
    asset = (sys.argv[1] if len(sys.argv) > 1 else "BTC").upper()
    now = datetime.now(UTC)
    client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (research; hoya-market-agent/0.1)"},
        follow_redirects=True,
    )
    drafts = []
    notes: list[str] = []

    print("=" * 72)
    print(f"LIVE 完整跑：{asset}（真新聞 + 社群 + 情緒 + 市場，真 LLM 語意抽取）")
    print("=" * 72)

    # 1) 市場（真 CSV，deterministic，high）
    bars = load_organizer_csv(default_data_dir() / f"{asset}_daily_ohlcv.csv")
    as_of = bars[-1].date
    m = build_market_evidence(asset, bars, analysis_as_of=as_of)
    r = build_regime_evidence(asset, bars, analysis_as_of=as_of)
    drafts += list(m.drafts) + list(r.drafts)
    reg = classify_regime(asset, bars, analysis_as_of=as_of)
    print(f"[市場] CSV {len(bars)} 筆 → {len(m.drafts) + len(r.drafts)} 筆證據"
          f"（狀態：{reg.label if reg else '-'}，as_of={as_of}）")

    # 1b) 第二個獨立交易所（OKX live，high，okx.com）——高可信度市場層可交叉驗證
    okx_bars, okx_deg = fetch_okx_daily(asset, analysis_as_of=now, client=client)
    notes += okx_deg
    if okx_bars:
        om = build_market_evidence(
            asset, okx_bars, analysis_as_of=okx_bars[-1].date,
            source_name=OKX_SOURCE, independence_group=OKX_GROUP, source_url=OKX_URL,
        )
        drafts += list(om.drafts)
        print(f"[市場] OKX live {len(okx_bars)} 筆 → {len(om.drafts)} 筆證據"
              f"（獨立交易所，可與另一來源交叉驗證，as_of={okx_bars[-1].date}）")
    else:
        print("[市場] OKX live：無資料（已揭露）")

    # 2) 新聞（真 RSS 標題 → medium 原始新聞頁）
    news_hits = 0
    for url, name, dom in FEEDS:
        res = fetch_rss_news(asset, analysis_as_of=now, client=client,
                             feed_url=url, source_name=name, publisher_domain=dom, lookback_days=30)
        drafts += list(res.drafts)
        notes += res.degradation
        news_hits += len(res.drafts)
        print(f"[新聞] {name}: {len(res.drafts)} 篇")

    # 3) LLM 語意抽取（真 GPT，跑同一批真新聞 → 結構化無立場事實，low）
    records = _rss_records(asset, client)
    if os.getenv("OPENAI_API_KEY") and records:
        from reasoning.gpt_client import GptClient  # imported lazily; needs the key
        ext = extract_news_facts(records[:_MAX_LLM_ARTICLES], llm=GptClient())
        drafts += list(ext.drafts)
        notes += ext.degradation
        print(f"[LLM] OpenAI GPT 讀 {min(len(records), _MAX_LLM_ARTICLES)} 篇真新聞 "
              f"→ 抽出 {len(ext.drafts)} 筆結構化事實")
    else:
        why = "未設 OPENAI_API_KEY" if not os.getenv("OPENAI_API_KEY") else "無可用新聞"
        print(f"[LLM] 略過語意抽取（{why}）——不放任何假資料進帳本")

    # 4) 社群（真 Reddit，best-effort；datacenter IP 會 403）
    rd = fetch_reddit_posts(asset, analysis_as_of=now, client=client, limit=50)
    drafts += list(rd.drafts)
    notes += rd.degradation
    print(f"[社群] Reddit: {len(rd.drafts)} 篇" + (f"（{rd.degradation}）" if rd.degradation else ""))

    # 5) 情緒（真 Fear & Greed，全市場）
    fg = fetch_fear_greed(analysis_as_of=now, client=client)
    drafts += list(fg.drafts)
    notes += fg.degradation
    print(f"[情緒] Fear & Greed: {len(fg.drafts)} 筆")

    # 合併 → 去重 → 排序 → 統一帳本
    ledger = build_ledger(drafts)
    print()
    print(f"合併 {len(drafts)} 張卡 → 去重後 {len(ledger.items)} 筆"
          f"（去重掉 {ledger.dropped_duplicates}）｜來源類型 {ledger.source_type_count} 種、"
          f"獨立來源群 {ledger.independence_group_count} 個")
    print()
    print(f"{'ID':<8}{'可信度':<7}{'類型':<8}{'來源':<22}{'事實'}")
    print("-" * 72)
    for i in ledger.items:
        fact = i.normalized_fact if len(i.normalized_fact) <= 34 else i.normalized_fact[:33] + "…"
        print(f"{i.evidence_id:<8}{i.reliability:<7}{i.source_type:<8}{(i.source_name or '')[:20]:<22}{fact}")
    if notes:
        print("\n揭露（degradation）：")
        for n in notes:
            print("  -", n)


if __name__ == "__main__":
    main()
