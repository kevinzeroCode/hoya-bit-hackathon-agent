"""Full offline market scan across ALL five coins — shows the real data scale.

Processes every coin's COMPLETE organizer history into market + regime evidence,
then one ledger. Real data, no network, no keys, no LLM. This is the market side
"跑完全部資料"; the news/social side reaches full scale only with a live run
(real APIs + real LLM). Usage:  python run_full.py
"""

from __future__ import annotations

import sys
from datetime import date

from adapters.organizer_csv import default_data_dir, load_organizer_csv
from data.market_worker import build_market_evidence
from data.regime import build_regime_evidence
from evidence.processor import build_ledger

ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP"]
AS_OF = date(2026, 5, 31)
_LABEL = {"trending_up": "趨勢向上", "trending_down": "趨勢向下",
          "range_bound": "區間盤整", "high_volatility": "高波動", "mixed": "方向不明"}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    data_dir = default_data_dir()
    if not (data_dir / "BTC_daily_ohlcv.csv").exists():
        print(f"[!] 找不到官方資料集：{data_dir}")
        return

    print("=" * 70)
    print("全市場掃描：5 幣完整歷史 → 市場證據（真 CSV，離線）")
    print("=" * 70)
    all_drafts = []
    total_bars = 0
    from data.regime import classify_regime
    for asset in ASSETS:
        bars = load_organizer_csv(data_dir / f"{asset}_daily_ohlcv.csv")
        total_bars += len(bars)
        m = build_market_evidence(asset, bars, analysis_as_of=AS_OF)
        r = build_regime_evidence(asset, bars, analysis_as_of=AS_OF)
        all_drafts += list(m.drafts) + list(r.drafts)
        reg = classify_regime(asset, bars, analysis_as_of=AS_OF)
        state = _LABEL.get(reg.label, "-") if reg else "-"
        print(f"  {asset:<4} {len(bars):>5} 筆日K → {len(m.drafts) + len(r.drafts)} 筆證據"
              f"｜狀態：{state}")

    ledger = build_ledger(all_drafts)
    print()
    print(f"原始資料：{total_bars:,} 筆日K（5 幣 × {total_bars // len(ASSETS):,}）")
    print(f"濃縮後證據：{len(ledger.items)} 筆（去重掉 {ledger.dropped_duplicates}）")
    print("→ 這就是『信任提煉』：大量原始資料 → 少數高品質、可回溯的事實。")
    print()
    print(f"{'ID':<8}{'幣':<5}{'可信度':<8}{'事實'}")
    print("-" * 70)
    for i in ledger.items:
        fact = i.normalized_fact if len(i.normalized_fact) <= 42 else i.normalized_fact[:41] + "…"
        print(f"{i.evidence_id:<8}{i.asset:<5}{i.reliability:<8}{fact}")


if __name__ == "__main__":
    main()
