"""
Agent Shield — decision briefs for the persona_attribution eval.

Twenty yes or no calls a CTO and a COO both face, in plain business language, meant to be
the same set in every arm so the arms differ only in the system prompt. Each brief was
written against the leakage guard in bible.py: none shares half its content tokens with
any Decisions title, Situation line or Eval question of the two frozen bibles, so a writer
cannot lift a gold answer out of the brief itself.
tests/test_persona_fidelity.py::test_briefs_do_not_leak_gold checks that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Brief:
    """One decision brief: a stable id (PB-NN) and the text the writer model answers."""

    id: str
    text: str


BRIEFS: tuple[Brief, ...] = (
    Brief(
        "PB-01",
        "A supplier has missed its delivery target twice this quarter. Do we renew the "
        "contract when it expires next month?",
    ),
    Brief(
        "PB-02",
        "Half the analytics group wants to stay fully remote. Do we approve permanent remote "
        "status for people who support on site operations?",
    ),
    Brief(
        "PB-03",
        "The reporting dashboard project is eighty percent complete and forty percent over "
        "its budget. Do we finish it or cut it now?",
    ),
    Brief(
        "PB-04",
        "The head of analytics resigned. Do we promote the internal deputy or recruit an "
        "outside candidate for the role?",
    ),
    Brief(
        "PB-05",
        "Legal counsel says we can wait five weeks before telling customers about the data "
        "breach. Do we notify them this week instead?",
    ),
    Brief(
        "PB-06",
        "The landlord offered a discount for a five year lease on a second office across "
        "town. Do we sign it?",
    ),
    Brief(
        "PB-07",
        "The consumer product line has lost money for six straight quarters. Do we shut it "
        "down before the next planning cycle?",
    ),
    Brief(
        "PB-08",
        "A larger company in our space has made an unsolicited acquisition offer at a fair "
        "price. Do we open talks?",
    ),
    Brief(
        "PB-09",
        "Payroll processing is run by two people in finance. Do we move it to an outsourced "
        "provider next quarter?",
    ),
    Brief(
        "PB-10",
        "HR drafted salary bands for every level. Do we publish them to the whole company?",
    ),
    Brief(
        "PB-11",
        "Travel spend is double the forecast. Do we freeze all non essential travel for the "
        "rest of the quarter?",
    ),
    Brief(
        "PB-12",
        "Our top salesperson skipped the mandatory ethics training twice. Do we let it slide "
        "because of the numbers?",
    ),
    Brief(
        "PB-13",
        "The annual performance review takes managers three weeks to complete. Do we replace "
        "it with quarterly check ins?",
    ),
    Brief(
        "PB-14",
        "A batch of returned units failed outside the warranty window. Do we repair them at "
        "our cost anyway?",
    ),
    Brief(
        "PB-15",
        "The industry conference wants us as a headline sponsor for sixty thousand. Do we "
        "pay for it this year?",
    ),
    Brief(
        "PB-16",
        "Last month's outage postmortem names three internal mistakes. Do we publish the "
        "full document to customers?",
    ),
    Brief(
        "PB-17",
        "Two contractors need access to the production environment to finish their "
        "integration. Do we grant it without a full background check?",
    ),
    Brief(
        "PB-18",
        "The outsourced help desk misses its response target most weeks. Do we bring support "
        "back in house?",
    ),
    Brief(
        "PB-19",
        "The launch is set for the first of next month and the accessibility fixes are not "
        "done. Do we push the date back four weeks?",
    ),
    Brief(
        "PB-20",
        "A departing director received a rival's offer at thirty percent more. Do we match "
        "it to retain her?",
    ),
)
