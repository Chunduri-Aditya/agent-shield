"""The S1 Claude API panel and its request policy (D31, D33, D37, D39; prereg S1).

One place for what every S1 script needs about the models: the ids (served to the project
key, E33), their run order (retiring models first), which ones think by default, the model
args that add a summarized thinking display without changing anything else, the thinking
contrast cells, and the price files.

Thinking defaults come from Anthropic's "Thinking support, defaults" table (retrieved
2026-10-14): Fable 5.1 and Opus 5.5 always think; Opus 5, Sonnet 5, Sonnet 5.5 and Haiku 5.5
think by default; every other panel model does not. Inspect's provider comment that Opus
4.7 and 4.8 think by default disagrees with that table; the table wins, and the offline
request diff (`scripts/v2/request_diff.py`) shows Inspect sends no thinking field for them.

A caller supplied `extra_body.thinking` replaces the thinking object Inspect builds,
including the `block_binding` it adds on Fable 5.1, Opus 5.5, Sonnet 5.5 and Haiku 5.5, so
the policy carries that binding itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PRICES = REPO / "pilot" / "s1_prices.yaml"
INSPECT_COSTS = REPO / "pilot" / "s1_inspect_model_costs.yaml"
MODEL_ARGS_DIR = REPO / "pilot" / "s1_model_args"

# Run order: the three retiring models first (E27, RR08), then by generation.
PANEL: tuple[str, ...] = (
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
)
THINKING_ON_DEFAULT: frozenset[str] = frozenset({
    "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
    "claude-sonnet-5", "claude-haiku-5-5",
})
# Models whose thinking blocks are bound to the request prefix (Inspect adds block_binding).
BOUND: frozenset[str] = frozenset({
    "claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5",
})
_BINDING = {"prefix_mismatch_behavior": "drop_block"}


def model_args(model: str) -> dict[str, Any]:
    """Inspect model args for one panel model in the S1 main grid; {} means API defaults."""
    if model not in PANEL:
        raise ValueError(f"{model!r} is not in the S1 panel")
    if model not in THINKING_ON_DEFAULT:
        return {}
    thinking: dict[str, Any] = {"type": "adaptive", "display": "summarized"}
    if model in BOUND:
        thinking["block_binding"] = dict(_BINDING)
    return {"extra_body": {"thinking": thinking}}


@dataclass(frozen=True)
class ContrastCell:
    """One thinking contrast cell (D39): a panel model with its thinking flipped."""

    model: str
    model_args: dict[str, Any] = field(hash=False)


CONTRAST_CELLS: dict[str, ContrastCell] = {
    "haiku55_off": ContrastCell(
        "claude-haiku-5-5", {"extra_body": {"thinking": {"type": "disabled"}}}),
    "sonnet5_off": ContrastCell(
        "claude-sonnet-5", {"extra_body": {"thinking": {"type": "disabled"}}}),
    "sonnet46_on": ContrastCell(
        "claude-sonnet-4-6",
        {"extra_body": {"thinking": {"type": "adaptive", "display": "summarized"}}}),
    "opus46_on": ContrastCell(
        "claude-opus-4-6",
        {"extra_body": {"thinking": {"type": "adaptive", "display": "summarized"}}}),
}
