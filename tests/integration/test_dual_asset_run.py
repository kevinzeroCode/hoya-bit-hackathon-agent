import pytest
from scripts.verify_s8_s9_s9b import verify

pytestmark = pytest.mark.integration


async def test_one_run_one_cutoff_one_ledger_four_artifacts() -> None:
    await verify()
