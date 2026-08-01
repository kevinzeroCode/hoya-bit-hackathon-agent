import pytest
from scripts.verify_s8_s9_s9b import verify

pytestmark = pytest.mark.integration


async def test_planner_fork_join_processor_renderer_and_artifacts() -> None:
    await verify()
