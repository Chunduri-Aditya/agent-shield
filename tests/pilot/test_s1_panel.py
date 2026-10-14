"""S1 plan steps 3d and 3e: the panel, its thinking policy, prices and the request diff.

Expected values come from the sources, not from the module under test: the thinking
defaults from the Anthropic table (thinking-troubleshooting, retrieved 2026-10-14), the
served ids from E33, the prices from E34. The request diff runs Inspect's real Anthropic
provider against an offline transport, so no request leaves the machine.
"""

from __future__ import annotations

import yaml  # type: ignore[import-untyped]

from scripts.pilot._common import load_prices
from scripts.v2 import request_diff, s1_panel

# E33 served ids minus claude-fable-5 (not in the D31 panel).
E33_PANEL = {
    "claude-opus-4-5-20251101", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-opus-5", "claude-opus-5-5", "claude-sonnet-4-5-20250929", "claude-sonnet-4-6",
    "claude-sonnet-5", "claude-sonnet-5-5", "claude-haiku-4-5-20251001", "claude-haiku-5-5",
    "claude-fable-5-1",
}
# Anthropic table "Thinking support, defaults": Always on or On.
DOCS_THINKING_ON = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
                    "claude-sonnet-5", "claude-haiku-5-5"}
# E34 (input, output, 5m write, 1h write, cache read), USD per million tokens.
E34 = {
    "claude-fable-5-1": (10, 50, 12.50, 20, 0.25), "claude-opus-5-5": (4, 20, 5, 8, 0.20),
    "claude-opus-5": (5, 25, 6.25, 10, 0.50), "claude-opus-4-8": (5, 25, 6.25, 10, 0.50),
    "claude-opus-4-7": (5, 25, 6.25, 10, 0.50), "claude-opus-4-6": (5, 25, 6.25, 10, 0.50),
    "claude-opus-4-5-20251101": (5, 25, 6.25, 10, 0.50),
    "claude-sonnet-5-5": (2, 10, 2.50, 4, 0.10), "claude-sonnet-5": (2, 10, 2.50, 4, 0.20),
    "claude-sonnet-4-6": (3, 15, 3.75, 6, 0.30),
    "claude-sonnet-4-5-20250929": (3, 15, 3.75, 6, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.20, 0.01),
    "claude-haiku-4-5-20251001": (1, 5, 1.25, 2, 0.10),
}


def test_panel_is_the_13_served_ids_retiring_first() -> None:
    assert set(s1_panel.PANEL) == E33_PANEL
    assert len(s1_panel.PANEL) == 13
    assert set(s1_panel.PANEL[:3]) == {"claude-opus-4-5-20251101", "claude-sonnet-4-5-20250929",
                                       "claude-haiku-4-5-20251001"}


def test_thinking_on_set_matches_the_docs_table() -> None:
    assert set(s1_panel.THINKING_ON_DEFAULT) == DOCS_THINKING_ON


def test_model_args_add_only_the_summarized_display() -> None:
    for mid in s1_panel.PANEL:
        args = s1_panel.model_args(mid)
        if mid not in DOCS_THINKING_ON:
            assert args == {}, mid
            continue
        thinking = args["extra_body"]["thinking"]
        assert thinking["type"] == "adaptive" and thinking["display"] == "summarized", mid
        assert ("block_binding" in thinking) is (mid in s1_panel.BOUND), mid
        assert set(args) == {"extra_body"} and set(args["extra_body"]) == {"thinking"}, mid


def test_pinned_model_arg_files_match_the_policy() -> None:
    files = {p.stem: p for p in s1_panel.MODEL_ARGS_DIR.glob("*.yaml")}
    assert set(files) == DOCS_THINKING_ON
    for mid, path in files.items():
        assert yaml.safe_load(path.read_text()) == s1_panel.model_args(mid), mid


def test_contrast_cells_flip_thinking_against_the_default() -> None:
    cells = s1_panel.CONTRAST_CELLS
    assert {c.model for c in cells.values()} == {"claude-haiku-5-5", "claude-sonnet-5",
                                                  "claude-sonnet-4-6", "claude-opus-4-6"}
    for cell in cells.values():
        thinking = cell.model_args["extra_body"]["thinking"]
        if cell.model in DOCS_THINKING_ON:
            assert thinking == {"type": "disabled"}, cell
        else:
            assert thinking == {"type": "adaptive", "display": "summarized"}, cell


def test_prices_match_e34_in_both_files() -> None:
    ours = load_prices(s1_panel.PRICES)
    inspect_costs = yaml.safe_load(s1_panel.INSPECT_COSTS.read_text())
    assert set(ours) == E34.keys()
    assert {k.removeprefix("anthropic/") for k in inspect_costs} == E34.keys()
    for mid, (inp, out, w5, w1, rd) in E34.items():
        assert ours[mid] == {"input": inp, "output": out, "cache_write_5m": w5,
                             "cache_write_1h": w1, "cache_read": rd}, mid
        row = inspect_costs[f"anthropic/{mid}"]
        assert row == {"input": inp, "output": out, "input_cache_write": w5,
                       "input_cache_read": rd}, mid


def test_request_diff_changes_only_the_thinking_display_offline() -> None:
    rows = request_diff.diff_all()
    assert {r.model for r in rows if r.cell == "main"} == E33_PANEL
    bad = [r for r in rows if not r.ok]
    assert bad == [], bad
    main = {r.model: r for r in rows if r.cell == "main"}
    assert main["claude-opus-4-8"].policy_thinking is None
    assert main["claude-sonnet-5-5"].policy_thinking == {
        "type": "adaptive", "display": "summarized",
        "block_binding": {"prefix_mismatch_behavior": "drop_block"}}
    assert main["claude-opus-5"].default_thinking is None
    assert main["claude-opus-5"].policy_thinking == {"type": "adaptive", "display": "summarized"}


def test_request_diff_flags_thinking_turned_on_for_a_default_off_model() -> None:
    row = request_diff.diff_one("main", "claude-opus-4-8",
                                {"extra_body": {"thinking": {"type": "adaptive"}}})
    assert not row.ok and "thinking" in row.reason


def test_request_diff_flags_any_other_body_change() -> None:
    args = s1_panel.model_args("claude-sonnet-5-5")
    args["extra_body"]["metadata"] = {"user_id": "s1"}
    row = request_diff.diff_one("main", "claude-sonnet-5-5", args)
    assert not row.ok and "other keys differ" in row.reason
