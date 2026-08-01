"""單一入口：一行指令跑完整條 P2 pipeline。

    python run_agent.py BTC              # 完整 live 跑(多源 + Bedrock/GPT)+ 報告
    python run_agent.py ETH --offline    # 離線 deterministic(只用官方 CSV,不打網路/LLM)
    python run_agent.py BTC --no-report   # 跳過 HTML 報告

產出：主控台摘要 + artifacts/evidence.json +（預設）render/out/hoya-report-<ASSET>.html
LLM 供應商自動選：BEDROCK_MODEL_ID → Bedrock；OPENAI_API_KEY → GPT；都沒 → 略過。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from evidence.evidence_json import dump_evidence_json
from pipeline import collect_evidence

UTC = timezone.utc
_HERE = Path(__file__).resolve().parent


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="HOYA P2 evidence pipeline (one command).")
    parser.add_argument("asset", nargs="?", default="BTC", help="BTC/ETH/SOL/BNB/XRP")
    parser.add_argument("--offline", action="store_true", help="只用官方 CSV,不打網路/LLM")
    parser.add_argument("--no-report", action="store_true", help="不產 HTML 報告")
    args = parser.parse_args()
    asset = args.asset.upper()

    print("=" * 72)
    print(f"HOYA P2 Agent｜{asset}｜{'離線(deterministic)' if args.offline else '完整 live'}")
    print("=" * 72)

    bundle = collect_evidence(asset, offline=args.offline)
    for line in bundle.source_lines:
        print("  •", line)

    led = bundle.ledger
    print("-" * 72)
    print(f"統一帳本：{len(led.items)} 筆（去重掉 {led.dropped_duplicates}）｜"
          f"來源類型 {led.source_type_count} 種、獨立群 {led.independence_group_count} 個｜"
          f"LLM={bundle.provider}｜狀態={getattr(bundle.regime, 'label', '-')}")

    # ① evidence.json（比賽固定 artifact）
    run_id = f"agent-{asset.lower()}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    ev_path = _HERE / "artifacts" / "evidence.json"
    dump_evidence_json(led, ev_path, asset=asset, analysis_as_of=bundle.as_of,
                       run_id=run_id, run_mode="rehearsal", llm_provider=bundle.provider)
    print(f"[artifact] evidence.json → {ev_path}")

    # ② HTML 報告(重用 renderer)
    if not args.no_report:
        from render_report import build_values, render
        template = (_HERE / "render" / "report_template.html").read_text(encoding="utf-8")
        values = build_values({
            "asset": bundle.asset, "as_of": bundle.as_of, "bars": bundle.bars,
            "regime": bundle.regime, "ledger": led, "notes": bundle.notes, "live_ok": bundle.live_ok,
        })
        out_path = _HERE / "render" / "out" / f"hoya-report-{asset}.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render(values, template), encoding="utf-8")
        print(f"[report]   → {out_path}")

    if bundle.notes:
        print(f"\n揭露(degradation) {len(bundle.notes)} 則,例：{bundle.notes[0]}")
    print("\n完成。")


if __name__ == "__main__":
    main()
