"""Practice round for the S1 labelling form, built only from the codebook's edge cases.

Usage (Python 3.11 or later, standard library only, no network):
  python3 scripts/v2/practice.py

It shows the 9 worked cases of `docs/paper_v2/prereg/S1_CODEBOOK.md` ("Edge cases") as views,
asks the same four question form as `label.py` (it reuses that form), and after each item
shows the label your answers derive next to the codebook's label and its reason. It reads
only `practice_items.json` beside it, writes no file, and never touches a labelling queue.
Answer `q` at any prompt to stop.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

if __package__:
    from . import label
else:  # run as a script: the labelling tool sits beside this file
    import label  # type: ignore[no-redef,import-not-found]

ITEMS = Path(__file__).with_name("practice_items.json")
NEXT = "Enter shows the next example, q stops: "


def load_items(path: Path = ITEMS) -> list[dict[str, Any]]:
    """The practice items, in codebook order."""
    items: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return items


def _shown(label_: str, first: int | None, reason: str | None, flag_a: bool) -> str:
    return (label_ + (f" T{first}" if first else "") + (f" ({reason})" if reason else "")
            + (", A" if flag_a else ""))


def run(items: list[dict[str, Any]], ask: Callable[[str], str] = input,
        say: Callable[[str], None] = print) -> int:
    """Ask the form on every item and show feedback; return how many matched the codebook."""
    form = label.Labeller(Path("."), ask=ask, say=say)
    matched = done = 0
    try:
        for n, item in enumerate(items, 1):
            say(f"\nExample {n} of {len(items)}.")
            say(item["view"])
            mine = label.derive(form._form(label.Item(item["id"], item["view"],
                                                      int(item["blocks"]), "practice")))
            want = item["codebook"]
            book = (want["label"], want["first_block"], want["reason"], want["flag_a"])
            same = mine == book
            matched += same
            done += 1
            say(f"Your answers give: {_shown(*mine)}.")
            say(f"Codebook: {_shown(*book)}. {item['why']}")
            say("Match." if same else "Different. Reread the disclosure test in the codebook.")
            if n < len(items):
                while (choice := form._prompt(NEXT).lower()) != "":
                    say(f"Press Enter or q, not {choice!r}.")
    except (label._StopError, EOFError):
        say("Stopped.")
    say(f"Practice done: {matched} of {done} matched the codebook. Nothing was saved.")
    return matched


def main() -> int:
    """Run the practice round on the terminal."""
    try:
        run(load_items())
    except KeyboardInterrupt:
        print("\nStopped. Nothing was saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
