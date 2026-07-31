"""Manual verification script — run `python verify.py` from the etl MVP folder.

Loads the organizer official CSVs and prints the deterministic pipeline output on
real data for all five coins, plus a few evidence-policy examples. Read-only,
offline, no LLM. This is for eyeballing real numbers; correctness is enforced by
`python -m pytest`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

from adapters.alternative_me import fetch_fear_greed
from adapters.binance import fetch_binance_daily
from adapters.cryptopanic import fetch_cryptopanic_news
from adapters.organizer_csv import default_data_dir, load_organizer_csv
from evidence.processor import build_ledger
from reasoning.llm_client import FakeLLMClient
from reasoning.research_extractor import NewsRecord, extract_news_facts


def _sample_klines(n: int, start: date = date(2026, 6, 1), base: float = 70000.0) -> list:
    rows = []
    for i in range(n):
        day = start + timedelta(days=i)
        price = base + (i % 7) * 50 - (i % 5) * 30 + i * 2  # wiggle so vol/zscore != 0
        ot = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)
        rows.append(
            [ot, f"{price}", f"{price + 40}", f"{price - 40}", f"{price}", f"{100 + i}",
             ot + 86_400_000 - 1, "0", 0, "0", "0", "0"]
        )
    return rows
from data.indicators import max_drawdown, realized_volatility, simple_return
from data.market_series import closes
from data.market_worker import build_market_evidence
from data.regime import build_regime_evidence, classify_regime
from evidence.policies import (
    SourceClass,
    ConfidenceSignals,
    independence_group,
    max_confidence,
    reliability_for,
)

ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"]


def main() -> None:
    data_dir = default_data_dir()
    if not (data_dir / "BTC_daily_ohlcv.csv").exists():
        print(f"[!] 找不到官方資料集：{data_dir}")
        print("    確認 hoya-bit-hackathon-agent 與 etl MVP 在同一層。")
        return

    print("=" * 70)
    print("市場指標（官方 CSV，截至各檔最後一日）")
    print("=" * 70)
    print(f"{'幣':<5}{'筆數':>6}{'最後日期':>14}{'收盤':>14}"
          f"{'14日報酬':>12}{'30日波動':>12}{'90日回撤':>12}")
    for asset in ASSETS:
        bars = load_organizer_csv(data_dir / f"{asset}_daily_ohlcv.csv")
        c = closes(bars)
        print(
            f"{asset:<5}{len(bars):>6}{bars[-1].date.isoformat():>14}{c[-1]:>14,.2f}"
            f"{simple_return(c, 14):>12.4%}"
            f"{realized_volatility(c, 30):>12.4f}"
            f"{max_drawdown(c, 90):>12.2%}"
        )

    print()
    print("=" * 70)
    print("Evidence 政策示範（deterministic，不用 LLM）")
    print("=" * 70)
    print("reliability：")
    print(f"  主辦 CSV            -> {reliability_for(SourceClass.ORGANIZER_CSV)}")
    print(f"  交易所 API          -> {reliability_for(SourceClass.EXCHANGE_MARKET_API)}")
    print(f"  原始新聞頁          -> {reliability_for(SourceClass.ORIGINAL_NEWS_PAGE)}")
    print(f"  新聞聚合(未取原頁)  -> {reliability_for(SourceClass.NEWS_AGGREGATOR)}")
    print(f"  Fear & Greed        -> {reliability_for(SourceClass.FEAR_GREED)}")

    print("independence group（同一原始來源不會被算成多個獨立來源）：")
    print(f"  api.binance.com     -> {independence_group(source_url='https://api.binance.com/api/v3/klines')}")
    print(f"  CryptoPanic 轉 CoinDesk -> "
          f"{independence_group(original_publisher='coindesk.com', source_url='https://cryptopanic.com/n/1')}")

    print("confidence 上限：")
    print(f"  2 獨立群 + high 證據 -> {max_confidence(ConfidenceSignals(2, 'high'))}")
    print(f"  只有 1 個獨立群      -> {max_confidence(ConfidenceSignals(1, 'high'))}")
    print(f"  有矛盾證據           -> {max_confidence(ConfidenceSignals(2, 'high', has_material_conflict=True))}")

    print()
    print("=" * 70)
    print("Market Worker 產出的 EvidenceDraft（BTC，截至 2026-05-31）")
    print("=" * 70)
    btc_bars = load_organizer_csv(data_dir / "BTC_daily_ohlcv.csv")
    result = build_market_evidence("BTC", btc_bars, analysis_as_of=date(2026, 5, 31))
    print(f"狀態：{result.status}｜證據筆數：{len(result.drafts)}")
    for d in result.drafts:
        print(f"  - [{d.reliability}] {d.normalized_fact}")
        print(f"      來源={d.source_name} 獨立群={d.independence_group} 依據={d.content_reference}")
    if result.degradation:
        print(f"  降級揭露：{result.degradation}")

    print()
    print("=" * 70)
    print("CryptoPanic 新聞 EvidenceDraft（示範樣本回應，非 live）")
    print("=" * 70)
    sample = {
        "results": [
            {
                "title": "Bitcoin ETF sees record inflows",
                "published_at": "2026-05-30T12:00:00Z",
                "url": "https://cryptopanic.com/news/1/click",
                "source": {"title": "CoinDesk", "domain": "coindesk.com"},
                "currencies": [{"code": "BTC"}],
            },
            {
                "title": "Analysts warn of BTC pullback risk",
                "published_at": "2026-05-29T08:00:00Z",
                "url": "https://cryptopanic.com/news/2/click",
                "source": {"title": "The Block", "domain": "theblock.co"},
                "currencies": [{"code": "BTC"}],
            },
        ]
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=sample)))
    news = fetch_cryptopanic_news(
        assets=["BTC"],
        analysis_as_of=datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc),
        client=client,
        api_token="demo-token",
    )
    print(f"狀態：{news.status}｜新聞證據筆數：{len(news.drafts)}")
    for d in news.drafts:
        print(f"  - [{d.reliability}] {d.normalized_fact}")
        print(f"      來源={d.source_name} 獨立群={d.independence_group} 時間={d.published_at.date()}")

    print()
    print("=" * 70)
    print("LLM 語意抽取 EvidenceDraft（FakeLLM mock，非真 API；正式接 Bedrock）")
    print("=" * 70)
    records = [
        NewsRecord(
            asset="BTC",
            title="Bitcoin ETF sees record inflows",
            body="Spot bitcoin ETFs recorded their largest single-day net inflow "
            "since launch, according to issuer filings.",
            source_name="CoinDesk",
            publisher_domain="coindesk.com",
            source_url="https://cryptopanic.com/news/1",
            published_at=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )
    ]
    # FakeLLM stands in for the GPT mock / Bedrock client — deterministic, offline.
    # 結構化抽取：判相關性 → 分類事件 → 抽多筆無立場事實（一篇 → 多筆證據）。
    fake_llm = FakeLLMClient(
        '{"relevant": true, "event_type": "etf_flow", '
        '"facts": ["美國現貨比特幣 ETF 出現上市以來最大單日淨流入", '
        '"發行商申報文件為此數據來源"]}'
    )
    extracted = extract_news_facts(records, llm=fake_llm)
    print(f"狀態：{extracted.status}｜一篇新聞抽出 {len(extracted.drafts)} 筆事實")
    for d in extracted.drafts:
        print(f"  - [{d.reliability}] {d.normalized_fact}")
        print(f"      {d.content_reference}")

    print()
    # Binance live market (sample klines via MockTransport) -> 2nd market independence group
    binance_bars, _ = fetch_binance_daily(
        "BTC",
        analysis_as_of=datetime(2026, 9, 30, tzinfo=timezone.utc),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_sample_klines(95)))
        ),
    )
    binance_ev = build_market_evidence(
        "BTC", binance_bars, analysis_as_of=date(2026, 9, 30),
        source_name="Binance Spot", independence_group="binance.com",
        source_url="https://api.binance.com/api/v3/klines",
    )
    # Fear & Greed (sample) -> adds the "social/sentiment" source type
    fng_ts = int(datetime(2026, 5, 30, tzinfo=timezone.utc).timestamp())
    fng = fetch_fear_greed(
        analysis_as_of=datetime(2026, 5, 31, tzinfo=timezone.utc),
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
            "data": [{"value": "28", "value_classification": "Fear", "timestamp": str(fng_ts)}],
            "metadata": {"error": None}}))),
    )

    # Market regime — synthesize indicators into a readable state (answers "市場狀態/是否盤整")
    print("=" * 70)
    print("市場狀態（Market Regime，由指標綜合判定）")
    print("=" * 70)
    regime = classify_regime("BTC", btc_bars, analysis_as_of=date(2026, 5, 31))
    regime_ev = build_regime_evidence("BTC", btc_bars, analysis_as_of=date(2026, 5, 31))
    if regime is not None:
        label_map = {"trending_up": "趨勢向上", "trending_down": "趨勢向下",
                     "range_bound": "區間盤整", "high_volatility": "高波動", "mixed": "方向不明"}
        print(f"  BTC 目前判定：【{label_map[regime.label]}】")
        print(f"    14 日報酬 {regime.return_window_pct:+.2%}｜"
              f"波動處於自身歷史第 {regime.vol_percentile*100:.0f} 百分位｜"
              f"區間位置 {regime.range_position*100:.0f}%")
    print()
    print("=" * 70)
    print("★ 統一證據帳本（所有來源合併 → 去重 → 排序 → 統一 ID/欄位）")
    print("=" * 70)

    all_drafts = (
        list(result.drafts) + list(regime_ev.drafts) + list(binance_ev.drafts)
        + list(news.drafts) + list(extracted.drafts) + list(fng.drafts)
    )
    ledger = build_ledger(all_drafts)
    print(f"合併 {len(all_drafts)} 張卡 → 去重後 {len(ledger.items)} 筆"
          f"（去重掉 {ledger.dropped_duplicates}）｜"
          f"來源類型 {ledger.source_type_count} 種、獨立來源群 {ledger.independence_group_count} 個")
    print(f"{'ID':<8}{'可信度':<8}{'類型':<8}{'來源':<20}{'事實'}")
    print("-" * 70)
    for i in ledger.items:
        fact = i.normalized_fact if len(i.normalized_fact) <= 32 else i.normalized_fact[:31] + "…"
        print(f"{i.evidence_id:<8}{i.reliability:<8}{i.source_type:<8}{i.source_name:<20}{fact}")

    print()
    print("=" * 70)
    print("單筆完整欄位（上表只印 5 欄；每筆其實帶完整來源標記）")
    print("=" * 70)
    fields = ("evidence_id", "content_hash", "asset", "source_type", "source_name",
              "source_url", "published_at", "fetched_at", "query_or_parameters",
              "content_reference", "normalized_fact", "reliability",
              "independence_group", "metric_name", "metric_value")

    def dump(label, item):
        print(f"[{label}]")
        for f in fields:
            v = getattr(item, f)
            if f == "content_hash" and v:
                v = v[:16] + "…"  # 64-hex，截短顯示
            print(f"  {f:<18}: {v}")
        print()

    news_item = next((i for i in ledger.items if i.source_type == "news"), None)
    market_item = next((i for i in ledger.items if i.source_type == "market"), None)
    if news_item:
        dump("新聞證據 完整欄位", news_item)
    if market_item:
        dump("市場證據 完整欄位", market_item)

    print("[OK] 市場來自官方 CSV（deterministic）；新聞為示範樣本；LLM 抽取用 FakeLLM mock；"
          "所有來源已合併成一份統一帳本，且每筆都帶完整來源標記（正式改用 Bedrock 只換一行）。")


if __name__ == "__main__":
    main()
