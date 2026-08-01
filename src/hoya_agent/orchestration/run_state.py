"""Run terminal-state derivation shared by pipelines and artifact delivery."""

from hoya_agent.models import StageState, TerminalState


def derive_terminal_state(states: list[StageState]) -> TerminalState:
    if any(state is StageState.cancelled for state in states):
        return TerminalState.cancelled
    if states and all(state is StageState.failed for state in states):
        return TerminalState.failed
    if any(state in {StageState.failed, StageState.degraded} for state in states):
        return TerminalState.degraded
    return TerminalState.completed


__all__ = ["StageState", "TerminalState", "derive_terminal_state"]
