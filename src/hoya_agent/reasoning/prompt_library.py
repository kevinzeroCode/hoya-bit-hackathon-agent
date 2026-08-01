"""Versioned prompt loading for the bounded reasoning stages.

Prompts live as markdown files under ``prompts/`` with a small YAML-ish
frontmatter block. Only the declared version identifiers reach the execution
log and ``run_config.json`` -- prompt bodies never do.

Standard library only, so this stays importable without the shared contracts.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

_FRONTMATTER_FENCE = "---"

#: Repository-root-relative prompt directory, resolved from this file's location.
DEFAULT_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts"

#: Stage -> prompt file stem. Adding a stage requires adding its prompt file.
PROMPT_FILES: dict[str, str] = {
    "planner": "planner-v1",
    "research_extraction": "research-extraction-v1",
    "arbiter": "arbiter-v1",
}


class PromptError(RuntimeError):
    """A prompt file is missing, malformed, or lacks required metadata."""


@dataclass(frozen=True)
class Prompt:
    """One loaded prompt: metadata for logging, body for the provider call."""

    prompt_id: str
    version: str
    body: str
    metadata: dict[str, str]

    @property
    def version_label(self) -> str:
        """Stable identifier recorded in run configuration, e.g. ``arbiter-v1``."""
        return f"{self.prompt_id}-{self.version}"


def parse_prompt(text: str) -> Prompt:
    """Parse frontmatter + body out of a prompt file's contents."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        raise PromptError("prompt is missing its opening frontmatter fence")

    metadata: dict[str, str] = {}
    body_start: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_FENCE:
            body_start = index + 1
            break
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise PromptError(f"malformed frontmatter line: {line!r}")
        metadata[key.strip()] = value.strip()

    if body_start is None:
        raise PromptError("prompt is missing its closing frontmatter fence")

    for required in ("prompt_id", "version"):
        if not metadata.get(required):
            raise PromptError(f"prompt frontmatter is missing {required!r}")

    body = "\n".join(lines[body_start:]).strip()
    if not body:
        raise PromptError("prompt body is empty")

    return Prompt(
        prompt_id=metadata["prompt_id"],
        version=metadata["version"],
        body=body,
        metadata=metadata,
    )


def load_prompt(stage: str, prompt_dir: Path | None = None) -> Prompt:
    """Load the prompt registered for ``stage``."""
    try:
        stem = PROMPT_FILES[stage]
    except KeyError as exc:
        raise PromptError(f"no prompt registered for stage {stage!r}") from exc

    path = (prompt_dir or DEFAULT_PROMPT_DIR) / f"{stem}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptError(f"prompt file not found: {path}") from exc
    return parse_prompt(text)


@functools.lru_cache(maxsize=None)
def cached_prompt(stage: str) -> Prompt:
    """Load-and-cache a prompt from the default directory."""
    return load_prompt(stage)


def prompt_versions(prompt_dir: Path | None = None) -> dict[str, str]:
    """Every registered stage's version label, for ``run_config.json``."""
    return {
        stage: load_prompt(stage, prompt_dir).version_label
        for stage in sorted(PROMPT_FILES)
    }
