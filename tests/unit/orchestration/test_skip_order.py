"""S4 fixed optional-work skip order.

The approved order is `H3 -> optional context adapter -> counter-signal second
search` (competition-rules.md). It is the order in which work is *given up*, so
the counter-signal search is the last optional thing surrendered — finding an
opposing signal matters more to report honesty than extra context does.

H3 stays in the vocabulary even though it is permanently disabled: dropping it
would let a later reader think the order begins with optional context.
"""

from __future__ import annotations

import pytest

from hoya_agent.orchestration.deadline import (
    SKIP_ORDER,
    OptionalWork,
    plan_optional_work,
    skip_note,
)

ALL_OPTIONAL = (OptionalWork.optional_context, OptionalWork.counter_signal_second_search)


def test_the_skip_order_is_exactly_the_approved_order() -> None:
    assert SKIP_ORDER == (
        OptionalWork.conditional_debate,
        OptionalWork.optional_context,
        OptionalWork.counter_signal_second_search,
    )


def test_nothing_is_skipped_when_the_window_can_afford_everything() -> None:
    plan = plan_optional_work(
        ALL_OPTIONAL, remaining_seconds=270.0, default_cost_seconds=45.0
    )

    assert plan.keep == ALL_OPTIONAL
    assert plan.skipped == ()
    assert plan.reasons == ()


def test_optional_context_is_surrendered_before_the_counter_signal_search() -> None:
    # 60 s left, 45 s per call: only one of the two fits.
    plan = plan_optional_work(
        ALL_OPTIONAL, remaining_seconds=60.0, default_cost_seconds=45.0
    )

    assert plan.skipped == (OptionalWork.optional_context,)
    assert plan.keep == (OptionalWork.counter_signal_second_search,)


def test_a_tighter_window_surrenders_both_in_order() -> None:
    plan = plan_optional_work(
        ALL_OPTIONAL, remaining_seconds=20.0, default_cost_seconds=45.0
    )

    assert plan.skipped == ALL_OPTIONAL
    assert plan.keep == ()


def test_an_exhausted_window_surrenders_everything() -> None:
    for remaining in (0.0, -5.0):
        plan = plan_optional_work(
            ALL_OPTIONAL, remaining_seconds=remaining, default_cost_seconds=45.0
        )
        assert plan.keep == ()
        assert plan.skipped == ALL_OPTIONAL


def test_h3_is_surrendered_first_when_a_caller_ever_schedules_it() -> None:
    plan = plan_optional_work(
        (OptionalWork.counter_signal_second_search, OptionalWork.conditional_debate),
        remaining_seconds=45.0,
        default_cost_seconds=45.0,
    )

    assert plan.skipped == (OptionalWork.conditional_debate,)
    assert plan.keep == (OptionalWork.counter_signal_second_search,)


def test_per_item_costs_override_the_default() -> None:
    plan = plan_optional_work(
        ALL_OPTIONAL,
        remaining_seconds=50.0,
        default_cost_seconds=45.0,
        cost_seconds={
            OptionalWork.optional_context: 10.0,
            OptionalWork.counter_signal_second_search: 30.0,
        },
    )

    assert plan.skipped == ()
    assert plan.keep == ALL_OPTIONAL


def test_the_kept_set_always_follows_the_skip_order_not_the_input_order() -> None:
    plan = plan_optional_work(
        (OptionalWork.counter_signal_second_search, OptionalWork.optional_context),
        remaining_seconds=270.0,
        default_cost_seconds=45.0,
    )

    assert plan.keep == ALL_OPTIONAL


def test_duplicate_input_is_collapsed() -> None:
    plan = plan_optional_work(
        (OptionalWork.optional_context, OptionalWork.optional_context),
        remaining_seconds=270.0,
        default_cost_seconds=45.0,
    )

    assert plan.keep == (OptionalWork.optional_context,)


def test_an_empty_pending_set_is_a_no_op() -> None:
    plan = plan_optional_work((), remaining_seconds=0.0, default_cost_seconds=45.0)

    assert plan.keep == () and plan.skipped == () and plan.reasons == ()


def test_unknown_optional_work_is_rejected_rather_than_ordered_by_guess() -> None:
    with pytest.raises(ValueError, match="optional work"):
        plan_optional_work(
            ("counter_signal_maybe",),  # type: ignore[arg-type]
            remaining_seconds=270.0,
            default_cost_seconds=45.0,
        )


def test_every_skip_carries_a_disclosure_reason() -> None:
    plan = plan_optional_work(
        ALL_OPTIONAL, remaining_seconds=0.0, default_cost_seconds=45.0
    )

    assert len(plan.reasons) == len(plan.skipped)
    for work in SKIP_ORDER:
        note = skip_note(work)
        assert note.strip() and "時間不足" in note


def test_the_decision_is_deterministic() -> None:
    first = plan_optional_work(
        ALL_OPTIONAL, remaining_seconds=60.0, default_cost_seconds=45.0
    )
    second = plan_optional_work(
        ALL_OPTIONAL, remaining_seconds=60.0, default_cost_seconds=45.0
    )

    assert first == second
