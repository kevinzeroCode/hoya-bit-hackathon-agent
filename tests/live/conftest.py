"""Opt-in guards for the live suite.

Two independent conditions, both required: the `live` marker and
`RUN_LIVE_TESTS=1`. A default `python -m pytest` must never reach the network, so
missing either condition skips rather than fails.
"""

from __future__ import annotations

import os

import pytest

RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"

pytestmark = pytest.mark.live


def pytest_collection_modifyitems(config, items) -> None:  # noqa: ARG001
    if RUN_LIVE:
        return
    skip = pytest.mark.skip(reason="live tests require RUN_LIVE_TESTS=1")
    for item in items:
        item.add_marker(skip)
