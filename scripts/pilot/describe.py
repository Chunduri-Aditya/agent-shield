"""Describe what a pilot log holds without looking at any grading: epochs, distinct completions,
effective sample size bounds, tool call counts and stop reasons.

Usage:
  describe.py --data D --log PATH

A completion key is the sha256 of the final assistant message text plus the ordered list of
(tool call function, json.dumps(arguments, sort_keys=True)) across the sample, so repeated
epochs that behaved identically collapse to one key.

Bounds: P is the number of distinct sample ids, so n_eff is at least P (epochs of one id are
correlated draws of the same prompt) and at most the summed count of distinct completions.

Field names verified against the installed inspect_ai 0.3.278 source:
  EvalSample.id :439, .epoch :442, .messages :466, .output :469  (inspect_ai/log/_log.py)
  ChatMessageAssistant.tool_calls :173, .text property :90  (inspect_ai/core/_chat_message.py)
  ToolCall.function :43, .arguments :46  (inspect_ai/core/_tool_call.py)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inspect_ai.log import EvalSample
from inspect_ai.model import ChatMessageAssistant

from scripts.pilot._common import PilotError, read_log, require_dir


@dataclass
class Description:
    samples: int
    P: int  # the spec's own symbol
    m_min: int
    m_max: int
    n_eff_lower: int
    n_eff_upper: int
    per_id: dict[str, tuple[int, int]]  # id -> (epochs run, distinct completions)
    tool_calls: dict[int, int]  # calls per sample -> samples
    stop_reason: dict[str, int]


def completion_key(sample: EvalSample) -> tuple[str, int]:
    """Return (sha256 completion key, number of tool calls) for one sample."""
    assistants = [m for m in sample.messages if isinstance(m, ChatMessageAssistant)]
    final_text = assistants[-1].text if assistants else ""
    calls: list[list[str]] = []
    for message in assistants:
        for call in message.tool_calls or []:
            calls.append([call.function, json.dumps(call.arguments, sort_keys=True)])
    payload = json.dumps([final_text, calls], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), len(calls)


def describe(log_path: Path) -> Description:
    """Compute the description as data so tests can read it without parsing text."""
    log = read_log(log_path)
    samples = list(log.samples or [])
    if not samples:
        raise PilotError(f"{log_path}: log holds no samples")
    epochs: dict[str, set[int]] = defaultdict(set)
    keys: dict[str, set[str]] = defaultdict(set)
    calls_per_sample: Counter[int] = Counter()
    stops: Counter[str] = Counter()
    for sample in samples:
        sid = str(sample.id)
        epochs[sid].add(sample.epoch)
        key, n_calls = completion_key(sample)
        keys[sid].add(key)
        calls_per_sample[n_calls] += 1
        stops["(no choices)" if sample.output.empty else sample.output.stop_reason] += 1
    per_id = {sid: (len(epochs[sid]), len(keys[sid])) for sid in sorted(epochs)}
    m_values = [m for m, _ in per_id.values()]
    return Description(
        samples=len(samples),
        P=len(per_id),
        m_min=min(m_values),
        m_max=max(m_values),
        n_eff_lower=len(per_id),
        n_eff_upper=sum(d for _, d in per_id.values()),
        per_id=per_id,
        tool_calls=dict(sorted(calls_per_sample.items())),
        stop_reason=dict(sorted(stops.items())),
    )


def print_description(log_path: Path, info: Description) -> None:
    print(f"{log_path}  ({info.samples} sample rows)")
    print(f"\n{'sample id':<24} {'epochs':>6} {'distinct':>8}")
    for sid, (m, d) in info.per_id.items():
        print(f"{sid:<24} {m:>6} {d:>8}")
    print(f"\nP = {info.P}   m = {info.m_min}..{info.m_max}")
    print(f"n_eff lower bound = {info.n_eff_lower}   upper bound = {info.n_eff_upper}")
    print(f"\n{'tool calls per sample':<22} {'samples':>7}")
    for n, count in info.tool_calls.items():
        print(f"{n:<22} {count:>7}")
    print(f"\n{'stop_reason':<22} {'samples':>7}")
    for reason, count in info.stop_reason.items():
        print(f"{reason:<22} {count:>7}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Describe a pilot log")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        require_dir(args.data)
        log_path = Path(args.log).resolve()
        print_description(log_path, describe(log_path))
    except (PilotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
