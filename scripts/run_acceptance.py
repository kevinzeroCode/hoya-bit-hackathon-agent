"""Run the offline Gold local Exit path and print the evidence to record."""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, date, datetime
from pathlib import Path

from hoya_agent.application import ApplicationService, build_request
from hoya_agent.models import Asset, RunMode
from hoya_agent.orchestration.pipeline import OrganizerCsvPipeline

NOW = datetime(2026, 5, 31, 6, 0, tzinfo=UTC)


class FixedClock:
    def now_utc(self) -> datetime:
        return NOW

    def monotonic(self) -> float:
        return 1000.0


async def run_asset(root: Path, asset: Asset) -> object:
    service = ApplicationService(
        artifact_root=root,
        clock=FixedClock(),
        pipeline=OrganizerCsvPipeline(analysis_date=date(2026, 5, 31)),
        configured_sources=["public_market_data"],
        stdout=io.StringIO(),
    )
    request = build_request(
        question="請產生可追溯的市場分析，並揭露資料限制。",
        assets=[asset],
        run_mode=RunMode.rehearsal,
        now=NOW,
        analysis_as_of=NOW,
        run_id_suffix=asset.value.lower(),
    )
    return await service.run(request)


async def main() -> None:
    root = Path("artifacts") / "gold-local"
    for asset in (Asset.BTC, Asset.ETH):
        summary = await run_asset(root, asset)
        print(
            f"asset={asset.value} run_id={summary.run_id} mode={summary.run_mode.value} "
            f"terminal_state={summary.terminal_state.value} evidence={summary.evidence_item_count} "
            f"artifact_dir={summary.artifact_dir} missing={summary.missing_artifacts}"
        )


if __name__ == "__main__":
    asyncio.run(main())

