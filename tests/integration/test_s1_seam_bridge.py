"""S1 ↔ S2 seam bridge.

S2 (Task 2) shipped before S1's second half (Task 1b, runtime seams) landed, so
its plumbing shapes live in `hoya_agent._provisional_seams`. Every test in this
module **skips** while the real seam is absent and **starts enforcing parity the
moment Task 1b lands**, which is what turns "we wrote a stand-in" into a
mechanical, verifiable swap instead of silent field-name drift.

When these tests start failing, that is the signal to do the swap described in
`docs/ai/S2_CONTRACT_EXPECTATIONS.md`:

1. repoint `application.py` / `reporting/artifacts.py` at `hoya_agent.models`
   and `hoya_agent.ports`;
2. delete `hoya_agent/_provisional_seams.py`;
3. delete this module.

Authority order on any disagreement: `.kiro/steering/evidence-contracts.md` >
`.kiro/specs/hoya-market-agent/design.md` > this module. If Task 1b names a field
differently and the contract permits it, S2 is the side that changes.
"""

from __future__ import annotations

import importlib

import pytest

from hoya_agent import _provisional_seams as provisional

pytestmark = pytest.mark.integration

# Provisional type -> the Task 1b module that will own it.
MODEL_OWNERS = {
    "ExecutionEvent": "hoya_agent.models",
    "RunConfigSnapshot": "hoya_agent.models",
    "RunSummary": "hoya_agent.models",
    "RunContext": "hoya_agent.models",
}

PORT_OWNERS = {
    "Clock": "hoya_agent.ports",
    "ProgressSink": "hoya_agent.ports",
}


def _real(name: str, module_path: str):
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        pytest.skip(f"{module_path} does not exist yet (Task 1b / S1 not merged)")
    real = getattr(module, name, None)
    if real is None:
        pytest.skip(f"{module_path}.{name} does not exist yet (Task 1b / S1 not merged)")
    return real


def _field_names(obj) -> set[str]:
    fields = getattr(obj, "model_fields", None)
    if fields is not None:
        return set(fields)
    annotations = getattr(obj, "__annotations__", {})
    return set(annotations)


@pytest.mark.parametrize("name", sorted(MODEL_OWNERS))
def test_provisional_plumbing_model_matches_the_real_contract(name: str) -> None:
    real = _real(name, MODEL_OWNERS[name])
    stand_in = getattr(provisional, name)

    real_fields = _field_names(real)
    stand_in_fields = _field_names(stand_in)

    missing = stand_in_fields - real_fields
    assert not missing, (
        f"{name}: S2 writes fields the real contract does not define: {sorted(missing)}. "
        "Reconcile against evidence-contracts.md §13/§14, then perform the swap "
        "documented in docs/ai/S2_CONTRACT_EXPECTATIONS.md."
    )


@pytest.mark.parametrize("name", sorted(PORT_OWNERS))
def test_s2_collaborators_satisfy_the_real_port_protocol(name: str) -> None:
    real = _real(name, PORT_OWNERS[name])
    stand_in = getattr(provisional, name)

    real_methods = {m for m in dir(real) if not m.startswith("_")}
    stand_in_methods = {m for m in dir(stand_in) if not m.startswith("_")}

    missing = stand_in_methods - real_methods
    assert not missing, (
        f"{name}: S2 calls methods the real port does not expose: {sorted(missing)}. "
        "Fix S2 (the port wins), then delete the stand-in."
    )


def test_swap_is_still_pending() -> None:
    """Fails once every real seam exists, as a reminder to delete the stand-in."""
    landed = []
    for name, module_path in {**MODEL_OWNERS, **PORT_OWNERS}.items():
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            continue
        if getattr(module, name, None) is not None:
            landed.append(f"{module_path}.{name}")

    if len(landed) == len(MODEL_OWNERS) + len(PORT_OWNERS):
        pytest.fail(
            "Task 1b has landed every runtime seam ("
            + ", ".join(sorted(landed))
            + "). Perform the S2 swap: repoint the imports in application.py and "
            "reporting/artifacts.py, delete hoya_agent/_provisional_seams.py, and "
            "delete this bridge module."
        )
