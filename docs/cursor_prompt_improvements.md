# Cursor Prompt — Agent Shield Improvements (v1.0.0)

Paste this entire prompt into Cursor. It is self-contained. Read it fully before writing a single line.

---

## CONTEXT: What this repo is

Agent Shield is an LLM agent security evaluation framework built on Inspect AI. It stress-tests language models against prompt injection, MCP tool poisoning, social engineering, data exfiltration, RAG poisoning, and behavioral drift. The novel contribution is a third metric called Transparency Rate (TR) — does the agent warn the user it is under attack, not just resist it?

**Stack:** Python 3.11+, `uv` project manager, Inspect AI eval harness, `pyproject.toml`, pytest, ruff, mypy.

**Existing module structure:**
```
inputs/attacks.py       # 5 prompt injection attacks (IN-01..IN-05), Attack dataclass
tools/attacks.py        # MCP tool poisoning (TL-01)
psych/attacks.py        # 6 Cialdini social engineering attacks (PS-01..PS-06)
memory/attacks.py       # RAG poisoning attacks
exfil/attacks.py        # data exfiltration attacks
drift/attacks.py        # multi-turn behavioral drift attacks
defenses/spotlighting.py
evals/inputs.py         # Inspect AI eval tasks for inputs/
evals/tools.py          # Inspect AI eval tasks for tools/
evals/psych.py          # Inspect AI eval tasks for psych/
evals/memory.py         # Inspect AI eval tasks for memory/
evals/exfil.py          # Inspect AI eval tasks for exfil/
evals/drift.py          # Inspect AI eval tasks for drift/
evals/smoke.py
scripts/sweep.py        # dynamic model sweep
Makefile                # make eval-inputs, make eval-psych, etc.
```

**What does NOT yet exist (your job to build):**
- `risk_registry.py` — attack risk + CIA + AIVSS metadata
- `reports/` directory — any file in it
- `report_generator.py` — post-eval report builder
- `approvals/policy.yaml` — Inspect AI-style approval policy
- `make report`, `make risk-check` Makefile targets

---

## TASK OVERVIEW

Build three interconnected systems. Implement them in this order — each one depends on the previous.

1. **`risk_registry.py`** — the central data source (everything else reads from it)
2. **Report generator** — reads eval logs, queries registry, writes plain-English markdown
3. **Pre-eval risk gate** — reads registry, blocks HIGH/CRITICAL before running, with approval policy

Do NOT modify any existing eval file (`evals/*.py`), attack file (`*/attacks.py`), or defense file unless explicitly told to. Only add new files and extend the Makefile.

---

## TASK 1 — `risk_registry.py` (build this first)

Create `risk_registry.py` at the repo root.

This is the single source of truth for attack metadata. Every other system reads from it.

### Severity vocabulary (OWASP AIVSS v0.5 — do not invent custom tiers)

```python
from enum import Enum

class Severity(str, Enum):
    CRITICAL = "Critical"   # AIVSS 9.0–10.0
    HIGH     = "High"       # AIVSS 7.0–8.9
    MEDIUM   = "Medium"     # AIVSS 4.0–6.9
    LOW      = "Low"        # AIVSS 0.1–3.9
```

### CIA property enum

```python
class CIAProperty(str, Enum):
    CONFIDENTIALITY = "Confidentiality"
    INTEGRITY       = "Integrity"
    AVAILABILITY    = "Availability"
```

### AttackMeta dataclass

```python
@dataclass(frozen=True)
class AttackMeta:
    attack_id: str          # e.g. "IN-01"
    module: str             # e.g. "inputs"
    severity: Severity
    aivss_score: float      # 0.0–10.0, one decimal place
    cia_primary: CIAProperty
    cia_secondary: list[CIAProperty]  # may be empty
    cia_plain_primary: str  # one plain-English sentence, no jargon
    cia_plain_secondary: str  # empty string if no secondary
    owasp_llm_ids: list[str]    # e.g. ["LLM01", "LLM06"]
    owasp_asi_ids: list[str]    # e.g. ["ASI01", "ASI09"]
    aivss_core_risk: str        # e.g. "Agent Goal and Instruction Manipulation"
    atlas_technique_id: str     # e.g. "AML.T0051.000" or "TODO"
    plain_title: str            # one-line human-readable title
    plain_description: str      # 2–3 sentences: what happened + why it matters
    plain_remediation: str      # 1–2 sentences: concrete fix
    tr_maps_to_integrity: bool  # True for all — TR failure = Integrity violation
```

### Registry entries (populate ALL of these exactly)

Use this validated CIA mapping (from research). Do not deviate.

| module | primary CIA | secondary CIA | OWASP LLM | OWASP ASI |
|---|---|---|---|---|
| inputs (prompt injection) | Integrity | Confidentiality, Availability | LLM01, LLM06 | ASI01, ASI09 |
| tools (MCP tool poisoning) | Integrity | Confidentiality | LLM06 | ASI02, ASI04 |
| psych (social engineering) | Integrity | — | LLM06 | ASI09 |
| memory (RAG poisoning) | Integrity | Confidentiality | LLM08, LLM04 | ASI06 |
| exfil (data exfiltration) | Confidentiality | — | LLM02, LLM07 | ASI03 |
| drift (behavioral drift) | Integrity | — | LLM06, LLM09 | ASI01 |

**Plain-English CIA definitions to use verbatim in `cia_plain_*` fields:**

- Confidentiality broken: "The agent leaked information it was supposed to keep private — system prompts, user data, or retrieved documents shown to someone who shouldn't see them."
- Integrity broken: "The agent did something other than what the user asked — its output, decisions, or tool calls were corrupted, manipulated, or hijacked. The agent misrepresented reality."
- Availability broken: "The agent stopped working, became too slow to use, or cost too much to run — denial of service or denial of wallet."

**Populate entries for all known attack IDs:**

IN-01, IN-02, IN-03, IN-04, IN-05 (module: inputs, severity: HIGH, aivss_score: 7.5)
TL-01 (module: tools, severity: CRITICAL, aivss_score: 9.2)
PS-01, PS-02, PS-03, PS-04, PS-05, PS-06 (module: psych, severity: MEDIUM, aivss_score: 5.5)
MEM-01 (module: memory, severity: HIGH, aivss_score: 7.8)
EXFIL-01 (module: exfil, severity: CRITICAL, aivss_score: 9.5)
DRIFT-01 (module: drift, severity: MEDIUM, aivss_score: 4.8)

Use "TODO" for `atlas_technique_id` where not yet confirmed. Use the AIVSS Core Risk "Agent Goal and Instruction Manipulation" for inputs/psych/drift, "Agentic AI Tool Misuse" for tools, "Agent Memory and Context Manipulation" for memory, and "Agent Untraceability" for exfil. Write the plain text fields in language a non-security engineer can follow — no acronyms without definition, no jargon.

### Registry lookup functions (add these)

```python
REGISTRY: dict[str, AttackMeta] = { ... }  # keyed by attack_id

def get_attack(attack_id: str) -> AttackMeta:
    """Raise KeyError with a clear message if attack_id not found."""

def get_module_attacks(module: str) -> list[AttackMeta]:
    """Return all AttackMeta entries for a given module name."""

def get_max_severity(attack_ids: list[str]) -> Severity:
    """Return the highest severity among the given attack IDs."""

def get_session_cia_properties(attack_ids: list[str]) -> set[CIAProperty]:
    """Return union of all CIA properties (primary + secondary) touched by the attack set."""
```

### Tests

Add `tests/test_risk_registry.py`:
- Every attack ID in the registry has non-empty `plain_description`, `plain_remediation`, `plain_title`
- `get_max_severity(["IN-01", "TL-01"])` returns `Severity.CRITICAL`
- `get_session_cia_properties(["EXFIL-01"])` contains `CIAProperty.CONFIDENTIALITY`
- `get_attack("NONEXISTENT")` raises `KeyError`
- TR maps to Integrity: assert all entries have `tr_maps_to_integrity == True`

---

## TASK 2 — Report Generator

### Files to create

```
reports/__init__.py           # empty
reports/schema.py             # VulnerabilityCard dataclass
report_generator.py           # main entry point
```

### `reports/schema.py` — 11-field vulnerability card

```python
@dataclass
class VulnerabilityCard:
    id: str                  # e.g. "AS-IN-001" (AS- prefix + attack_id + instance counter)
    title: str               # from AttackMeta.plain_title
    severity: Severity       # from AttackMeta.severity
    aivss_score: float       # from AttackMeta.aivss_score
    confidence: str          # "High" / "Medium" / "Low" — based on n_samples
    cia_impact: list[CIAProperty]  # primary + secondary combined
    cia_plain: str           # plain-English sentence for all affected properties
    category: str            # module name: "prompt-injection", "tool-poisoning", etc.
    description: str         # from AttackMeta.plain_description
    evidence: str            # transcript excerpt from eval log (first 300 chars of model output)
    reproduction: str        # "Run: make eval-{module} MODEL={model_id}"
    remediation: str         # from AttackMeta.plain_remediation
    references: str          # formatted string: "OWASP {llm_ids} | ASI {asi_ids} | AIVSS: {core_risk} | ATLAS: {atlas_id}"
```

### `report_generator.py` — main entry point

Build a script that:

1. Locates the most recent `.eval` log file in `logs/` (sort by mtime, take the latest)
2. Parses it using Inspect AI's log reading API: `from inspect_ai.log import read_eval_log`
3. For each task result in the log, extracts: `task_name`, `model`, `score` value, `metadata` if present
4. Maps the task name to attack IDs via a simple lookup dict (e.g. `"inputs_asr"` → `["IN-01","IN-02","IN-03","IN-04","IN-05"]`)
5. For each failed/attacked sample, creates a `VulnerabilityCard` using `risk_registry.get_attack()`
6. Generates `reports/latest_report.md`

### `reports/latest_report.md` format

Produce this exact structure:

```markdown
# Agent Shield Security Report
Generated: {ISO timestamp}
Model: {model_id}
Eval log: {log_filename}

---

## Executive Summary

| Property | Value |
|---|---|
| Overall risk | {max_severity} (AIVSS {max_score}/10) |
| Modules evaluated | {comma list} |
| Findings | {n_findings} |
| CIA properties at risk | {comma list in plain English} |

{One paragraph in plain English: what was run, what the worst finding was,
and what the most important thing to fix is. No jargon. Write as if explaining
to a developer who has never heard of prompt injection.}

---

## Findings by Module

For each module with findings, emit:

### {Module Name} — {max severity in module}

| Attack | Severity | AIVSS | CIA Impact | OWASP |
|---|---|---|---|---|
| {title} | {severity} | {score} | {C/I/A} | {LLM+ASI IDs} |

Then for each finding, emit the full 11-field card:

---
**{id} — {title}**
Severity: {severity} ({aivss_score}/10) | CIA: {cia_plain} | Confidence: {confidence}

**What happened:** {description}

**Evidence (transcript excerpt):**
> {evidence}

**To reproduce:** {reproduction}

**Fix:** {remediation}

**References:** {references}

---

## What's at risk

{Plain-English paragraph summarizing which CIA properties were violated across
all findings. Use the validated definitions: Confidentiality = private data leaked,
Integrity = agent hijacked or lied, Availability = system disrupted.}

---

## Transparency Rate note

If any TR score was recorded in the log: report it here as a ratio (e.g. "2 of 10 attacks
were flagged to the user"). Classify TR failure as an Integrity violation — the agent
misrepresented reality by not disclosing the attack.

---
*Agent Shield v1.0.0 | Framework: Inspect AI | Severity: OWASP AIVSS v0.5*
```

### CLI interface for `report_generator.py`

```bash
python report_generator.py                        # uses most recent log
python report_generator.py --log logs/foo.eval    # specific log
python report_generator.py --out reports/my_report.md  # custom output path
python report_generator.py --model anthropic/claude-sonnet-4-5  # filter by model
```

Use `argparse`. All args optional. Fail clearly with a human-readable message if no logs found.

### Tests

Add `tests/test_report_generator.py`:
- `VulnerabilityCard` for `TL-01` has severity `CRITICAL`
- `VulnerabilityCard.references` contains "ASI02"
- `VulnerabilityCard.cia_impact` for `EXFIL-01` contains `CIAProperty.CONFIDENTIALITY`
- Report output file is created when `report_generator.py` runs against a fixture log
- Report contains the string "Executive Summary"

---

## TASK 3 — Pre-eval Risk Gate

### Files to create

```
approvals/
approvals/__init__.py
approvals/policy.yaml
approvals/gate.py
```

### `approvals/policy.yaml`

```yaml
# Agent Shield eval approval policy
# Follows Inspect AI approval DSL extended to eval-suite level.
# LOW/MEDIUM: auto-proceed. HIGH/CRITICAL: require --confirm-high-risk flag.
# CRITICAL attacks not cleared in ETHICS.md: hard-block regardless of flag.

auto_approve:
  - severity: LOW
  - severity: MEDIUM

require_confirmation:
  - severity: HIGH
  - severity: CRITICAL

ethics_clearance_required:
  - severity: CRITICAL

confirmation_flag: "--confirm-high-risk"
```

### `approvals/gate.py`

Build a pre-eval gate with this interface:

```python
def check_eval_risk(
    attack_ids: list[str],
    confirm_high_risk: bool = False,
    ethics_cleared: list[str] | None = None,
) -> GateResult:
    """
    Evaluate whether an eval session should proceed.

    Returns a GateResult with:
      .allowed: bool
      .max_severity: Severity
      .max_aivss_score: float
      .cia_properties: set[CIAProperty]
      .banner: str   — the text to print to the terminal before the eval runs
      .block_reason: str | None  — None if allowed, explanation if blocked

    CRITICAL: banner must contain the ACTUAL attack IDs and severity scores
    from risk_registry — never an LLM-generated summary. This is a
    Lies-in-the-Loop defense (see docs/improvement_research.md).
    """

def print_risk_banner(result: GateResult) -> None:
    """
    Print the CIA Triad check + risk level to stdout.
    Use ANSI color codes:
      LOW/MEDIUM  → green
      HIGH        → yellow
      CRITICAL    → red

    Format:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    CIA Triad check
      Confidentiality — {AFFECTED/NOT AFFECTED} — {plain English sentence}
      Integrity       — {AFFECTED/NOT AFFECTED} — {plain English sentence}
      Availability    — {AFFECTED/NOT AFFECTED} — {plain English sentence}

    Risk level: {SEVERITY} (AIVSS {score}/10)
    Attacks in session: {comma-separated IDs}

    {If HIGH: "Proceeding requires --confirm-high-risk flag."}
    {If CRITICAL and not ethics_cleared: "BLOCKED — add to ETHICS.md first."}
    {If allowed: "Proceeding."}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
```

### Ethics clearance check

Read `ETHICS.md` to check if an attack is cleared. Parse the file for lines containing the attack ID (e.g. `TL-01`). If CRITICAL-severity attacks are NOT mentioned in `ETHICS.md`, block them even with `--confirm-high-risk`. Print a clear message: `"BLOCKED: {attack_id} has CRITICAL severity and is not cleared in ETHICS.md. Add an entry before running."`

### `make risk-check` dry-run

Add a Python script `scripts/risk_check.py` that:
1. Accepts `--module inputs` (or any module name, or `--all` for all modules)
2. Looks up all attack IDs for that module from `risk_registry.py`
3. Calls `check_eval_risk()` with `confirm_high_risk=False`
4. Prints the full banner
5. Exits 0 if all attacks are LOW/MEDIUM, exits 1 if any are HIGH/CRITICAL (useful for CI)

### Makefile additions

Append to the Makefile (do not modify existing targets):

```makefile
# Generate plain-English report from most recent eval log
report:
	uv run python report_generator.py

# Generate report from a specific log file
report-log:
	uv run python report_generator.py --log $(LOG)

# Pre-run risk check (dry run, no eval execution)
risk-check:
	uv run python scripts/risk_check.py --module $(MODULE)

risk-check-all:
	uv run python scripts/risk_check.py --all

# Run eval then immediately generate report (explain mode)
eval-inputs-explain:
	uv run inspect eval evals/inputs.py --model $(MODEL) --seed $(SEED) && uv run python report_generator.py

eval-tools-explain:
	uv run inspect eval evals/tools.py --model $(MODEL) --seed $(SEED) && uv run python report_generator.py

eval-psych-explain:
	uv run inspect eval evals/psych.py --model $(MODEL) --seed $(SEED) && uv run python report_generator.py

eval-memory-explain:
	uv run inspect eval evals/memory.py --model $(MODEL) --seed $(SEED) && uv run python report_generator.py

eval-exfil-explain:
	uv run inspect eval evals/exfil.py --model $(MODEL) --seed $(SEED) && uv run python report_generator.py

eval-drift-explain:
	uv run inspect eval evals/drift.py --model $(MODEL) --seed $(SEED) && uv run python report_generator.py
```

### Tests

Add `tests/test_gate.py`:
- `check_eval_risk(["IN-01"])` returns `GateResult(allowed=True)` (HIGH, no CRITICAL)
- Wait — IN-01 is HIGH (7.5). HIGH requires `--confirm-high-risk`. Test that `allowed=False` without flag, `allowed=True` with flag.
- `check_eval_risk(["TL-01"])` returns `allowed=False` without ethics clearance (CRITICAL)
- `check_eval_risk(["PS-01"])` returns `allowed=True` (MEDIUM, auto-proceed)
- `print_risk_banner()` output contains "Integrity" when IN-01 is in session
- Banner contains the literal string "IN-01" (not a summary) — Lies-in-the-Loop defense

---

## CODE QUALITY REQUIREMENTS

- Type hints on every function signature
- Docstrings on every class and public function
- No `print()` in library code — use `logging` or return strings for the caller to print (except `gate.py`'s `print_risk_banner` which is explicitly a terminal printer)
- All plain-English text fields must be non-empty — add a validator that raises `ValueError` on empty strings at registry construction time
- `ruff check .` must pass on all new files
- `mypy` must pass on all new files (add `py.typed` marker if needed)
- All new tests pass with `pytest`

---

## WHAT NOT TO DO

- Do NOT modify `evals/*.py`, `inputs/attacks.py`, `tools/attacks.py`, `psych/attacks.py`, `memory/attacks.py`, `exfil/attacks.py`, `drift/attacks.py`, or `defenses/spotlighting.py`
- Do NOT add `Co-Authored-By` lines or AI attribution to any commit message
- Do NOT invent a custom severity vocabulary — use AIVSS Critical/High/Medium/Low exactly
- Do NOT use LLM-generated text in the risk banner — always read from `risk_registry.py` directly
- Do NOT create a web UI or dashboard — output is markdown and terminal only
- Do NOT add new dependencies beyond what is already in `pyproject.toml` unless strictly required (and explain why in a comment)

---

## IMPLEMENTATION ORDER

1. `risk_registry.py` + `tests/test_risk_registry.py` → run `pytest tests/test_risk_registry.py`
2. `reports/schema.py` + `reports/__init__.py`
3. `report_generator.py` + `tests/test_report_generator.py` → run `pytest tests/test_report_generator.py`
4. `approvals/gate.py` + `approvals/policy.yaml` + `approvals/__init__.py`
5. `scripts/risk_check.py`
6. `tests/test_gate.py` → run `pytest tests/test_gate.py`
7. Makefile additions
8. Run `make lint` — fix everything before committing
9. Run `make test` — all tests green before committing
10. Run `make risk-check-all` — confirm banner prints correctly
11. Run `make eval-inputs-explain` with a real model — confirm report is generated

Do not move to step N+1 until step N is passing.
