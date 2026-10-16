"""Check the judge's answers for the S1 gold labels (D54: the Fable judge labels first and
Aditya verifies).

Usage (Python 3.11 or later, standard library only, no network):
  python3 verify.py DIR            verify the items in DIR (DATA/v2_s1/verify/dev)
  python3 verify.py DIR --pace     median seconds per item

DIR is written by `judge_s1.py verify-export`: one row per queue item with its view and the
judge's form answers and label. For each item the tool shows the view, then the judge's
answers. Enter agrees and saves the judge's label as yours. `o` overrides: you answer the
codebook's four question form (the same questions, skip logic and derived label as
`label.py`) and your label is saved beside the judge's. An item the judge could not label
(a void form) goes straight to the form. Every verification is appended to
`verify_labels.jsonl` and flushed to disk before the next item, so a break loses at most the
item on screen; a restart resumes at the first unverified item; the session stops offering
items after 50 minutes (D45). The tool never opens the key and never shows the model, the
arm or the sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__:
    from . import label as lb
else:  # run as a script: the labelling tool sits beside this file
    import label as lb  # type: ignore[no-redef,import-not-found]

TODO = "verify_todo.jsonl"
DONE = "verify_labels.jsonl"
CHOICE = "Enter agrees with the judge, o answers the form yourself, q stops: "
CONFIRM = "Enter saves, r redoes this item, q stops without saving it: "
_TOOL_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _show(answers: dict[str, Any]) -> str:
    q1 = " ".join(map(str, answers["q1"])) if answers["q1"] else "none"

    def val(v: Any) -> str:
        return "skipped" if v is None else str(v)

    return f"Q1 {q1} | Q2 {val(answers['q2'])} | Q3 {val(answers['q3'])} | Q4 {val(answers['q4'])}"


def _label_text(label: str, first: int | None, reason: str | None, flag_a: bool) -> str:
    return (label + (f" T{first}" if first else "") + (f" ({reason})" if reason else "")
            + (", A" if flag_a else ""))


class Verifier:
    """One verification session over a folder from `judge_s1.py verify-export`."""

    def __init__(self, folder: Path, *, ask: Callable[[str], str] = input,
                 say: Callable[[str], None] = print,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 clock: Callable[[], float] = time.monotonic, clear: bool = False,
                 minutes: int = lb.SESSION_MINUTES) -> None:
        self.folder = Path(folder)
        self.ask, self.say, self.now, self.clock = ask, say, now, clock
        self.clear, self.minutes = clear, minutes
        self.out = self.folder / DONE
        # The form questions come from the labelling tool itself, so both ask the same.
        self.form = lb.Labeller(self.folder, ask=ask, say=say)

    def _prompt(self, text: str) -> str:
        answer = self.ask(text).strip()
        if answer.lower() == "q":
            raise lb._StopError
        return answer

    def _load(self) -> list[dict[str, Any]]:
        if not self.folder.is_dir():
            raise lb.LabelError(f"{self.folder}: not a verification folder")
        if (self.folder / "key.json").exists() or self.folder.name == "sealed":
            raise lb.LabelError(f"{self.folder} holds the key; the key stays sealed elsewhere")
        rows = []
        for n, line in enumerate((self.folder / TODO).read_text(encoding="utf-8")
                                 .splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                rows.append({"item": str(row["item"]), "view": str(row["view"]),
                             "blocks": int(row["blocks"]), "judge": row["judge"]})
            except (ValueError, KeyError, TypeError) as exc:
                raise lb.LabelError(f"{self.folder / TODO} line {n}: not a row ({exc})") from exc
        lb._set_aside_torn_tail(self.out)
        self.done = {str(r["item"]) for r in lb._labels(self.out)}
        self.saved = len(self.done)
        return rows

    def _verify(self, row: dict[str, Any], header: str) -> dict[str, Any]:
        start = self.clock()
        judge = row["judge"]
        item = lb.Item(row["item"], row["view"], row["blocks"], "verify")
        while True:
            self.say((lb._CLEAR if self.clear else "") + header)
            self.say(lb._CONTROL_RE.sub("", row["view"]))
            if judge is None:
                self.say("The judge gave no valid form for this item: answer it yourself.")
                choice = "o"
            else:
                self.say("Judge: " + _show(judge["answers"]) + "  ->  label " + _label_text(
                    judge["label"], judge["first_block"], judge["reason"], judge["flag_a"]))
                choice = ""
                while True:
                    choice = self._prompt(CHOICE).lower()
                    if choice in ("", "o"):
                        break
                    self.say("Press Enter, o or q.")
            if choice == "":
                answers = judge["answers"]
                decision = "agree"
            else:
                answers = self.form._form(item)
                decision = "override"
            label, first, reason, flag_a = lb.derive(answers)
            self.say(f"Saved label: {_label_text(label, first, reason, flag_a)} ({decision}).")
            confirm = ""
            while True:
                confirm = self._prompt(CONFIRM).lower()
                if confirm in ("", "r"):
                    break
                self.say("Press Enter, r or q.")
            if confirm == "":
                break
        return {"item": row["item"], "decision": decision, "label": label, "first_block": first,
                "reason": reason, "flag_a": flag_a, "answers": answers, "judge": judge,
                "agrees_with_judge": judge is not None and label == judge["label"]
                and first == judge["first_block"],
                "seconds": round(self.clock() - start, 3),
                "verified_at": self.now().isoformat(), "session": self.session,
                "tool_sha256": _TOOL_SHA256, "label_tool_sha256": lb._TOOL_SHA256}

    def run(self) -> int:
        """Verify until the time box ends, the folder runs out, or the verifier stops."""
        rows = self._load()
        self.session = self.now().isoformat()
        start = self.clock()
        made = 0
        new = not self.out.exists()
        with self.out.open("a", encoding="utf-8") as out:
            if new:
                lb._sync_dir(self.folder)
            for row in rows:
                if row["item"] in self.done:
                    continue
                if self.clock() - start >= self.minutes * 60:
                    self.say(f"{self.minutes} minutes are up: {made} verified this session."
                             " Take the break.")
                    return made
                left = max(0, int(self.minutes - (self.clock() - start) / 60))
                header = (f"Verified {self.saved} of {len(rows)}. This session {made}."
                          f" About {left} minutes left of {self.minutes}.")
                try:
                    rec = self._verify(row, header)
                except (lb._StopError, EOFError):
                    self.say(f"Stopped: {made} verified this session; the item on screen was"
                             " not saved.")
                    return made
                out.write(json.dumps(rec, sort_keys=True) + "\n")
                out.flush()
                os.fsync(out.fileno())
                self.done.add(row["item"])
                self.saved += 1
                made += 1
        self.say(f"Nothing left to verify: {made} verified this session.")
        return made


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="verify the S1 judge's labels (D54)")
    parser.add_argument("dir", type=Path, help="the folder from judge_s1.py verify-export")
    parser.add_argument("--pace", action="store_true", help="median seconds per item")
    args = parser.parse_args(argv)
    try:
        if args.pace:
            median, n = lb.pace(args.dir / DONE)
            print(f"median {median:.0f} s per item over {n} verifications")
            return 0
        made = Verifier(args.dir, clear=sys.stdout.isatty()).run()
    except lb.LabelError as exc:
        print(f"verify.py: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped: every verification before the item on screen is saved.")
        return 0
    print(f"{made} verified this session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
