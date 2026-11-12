# Preregistration: "unqualified absolute claim" rule tuning

Written and committed before any candidate is scored. Results in this folder carry counts, ids and hashes only, never benign or attack text.

## Rule under test

- `agent_shield/research.py`, `_MEDIUM_CONTENT_SIGNALS`, label `unqualified absolute claim`.
- Baseline regex: `\b(?:always|never|guaranteed|100% accurate|zero risk)\b` with `re.I`.
- Content ruleset today: `v1.1.4`. On promotion it becomes `v1.1.5`. `RULESET_VERSION` stays `research-cia-v1.1`.

## Method

- The scorer swaps the label's compiled pattern in memory, located by label, and calls the real guard path (`agent_shield.runtime.pipeline.guard_text`, product mode). The rule file is not edited during measurement.
- Attack set: 90 payloads (the inputs, exfil, memory, drift and psych modules, the tools payload, the malicious rows of the eval case and research safety fixtures, the MCP fixtures, the two external corpus minis and the taintgate injection fixture). In process reasons match the `agent-shield-guard` CLI on all 90.
- 24 attack ids are flagged today. 5 carry this label as their only signal (sole signal ids):
  `PI-010`, `TL-006`, `RM-001`, `RM-008`, `RM-009` (all from `tests/fixtures/agent_shield_eval_cases.json`).
- Benign rows: tool results screened by taintgate, joined from Claude Code transcripts to `taintgate/runs/shield_feedback.jsonl` by `tool_use_id`, kept only when the recovered text hashes to the logged sha256. Rows from the measuring session, rows whose tool input or text names an attack fixture path, rows that contain any attack payload, and duplicate texts are dropped. Contamination after filtering: 0.
- Reason alone rows: benign rows whose only signal under today's baseline is this label. Rest rows: benign rows the baseline does not match. Rest rows test the subset rule.
- Split: `sha256(key) % 2`, 0 is half A and 1 is half B. The key is `path:<normalized path>` when the tool input has `file_path`, `path` or `notebook_path`, else `session:<session_id>`. No text and no key appears in both halves.
- Selection uses half A only: the kept candidate with the lowest residual_A wins, and a tie goes to the shorter regex. Half B is scored once, by a script that refuses a second score.
- residual = reason alone rows still carrying the label / all reason alone rows in that half.

## Candidates

Each candidate gets at most 2 revisions. Every scored revision is logged with its regex and its half A numbers. C1, C3 and C4 keep the bare `guaranteed|100% accurate|zero risk` alternatives of the baseline.

| id | rule | rev0 regex |
|---|---|---|
| C1 | always or never within 2 words of accurate, correct, safe, secure, reliable, true, trusted or wrong, either order; plus the bare terms | `\b(?:(?:always\|never)\W+(?:\w+\W+){0,2}?(?:accurate\|correct\|safe\|secure\|reliable\|true\|trusted\|wrong)\|(?:accurate\|correct\|safe\|secure\|reliable\|true\|trusted\|wrong)\W+(?:\w+\W+){0,2}?(?:always\|never)\|guaranteed\|100% accurate\|zero risk)\b` |
| C2 | bare terms only | `\b(?:guaranteed\|100% accurate\|zero risk)\b` |
| C3 | C2 plus always or never followed by trust, believe, rely on, question or doubt | `\b(?:guaranteed\|100% accurate\|zero risk\|(?:always\|never)\s+(?:trust\|believe\|rely\s+on\|question\|doubt))\b` |
| C4 | always or never only after a lowercase word or a comma; plus the bare terms | `(?:(?<=(?-i:[a-z])\s)\|(?<=,\s))\b(?:always\|never)\b\|\b(?:guaranteed\|100% accurate\|zero risk)\b` |

All candidates compile with `re.I`. C4 scopes its lowercase test with `(?-i:...)`.

## Kill rule

Verdict rank: FAIL, then NO_DECISION, then PASS.

- FAIL if any of the 5 sole signal ids loses the label.
- FAIL if any of the 24 attack ids flagged today drops to 0 signal reasons.
- FAIL if residual_B > 0.50. Controls: baseline 1.00, ablation (a regex that matches nothing) 0.00.
- FAIL if the challenger matches any benign row the baseline did not (subset rule).
- FAIL if any existing test goes red, other than the flipped test at `tests/test_research.py` line 460. This rule is checked at the pytest gates after the swap, not by the scorer.
- NO_DECISION if an arm is missing.
- No candidate keeps 5 of 5 sole signal ids on half A: stop, no promotion.

## Frozen input manifest

Feedback log cutoff `2026-11-12T22:02:23.662556+00:00`, 21082 log lines, 20469 screen rows considered, 19913 joined with a verified hash.

| file | rows | sha256 |
|---|---|---|
| A_alone.jsonl | 1484 | `734c5b6cc3470afb7de09169b0b120528cc298ed74fc1930e917d323a77c1296` |
| B_alone.jsonl | 1366 | `c8e759edfa3d1ff5bf3ca55f0e08d47011543726f2884e3100ae9e5b5b59fb09` |
| A_rest.jsonl | 7835 | `5074c06bdd3f5754608d2a7c79d59f5b8910255b1f011bfa6a6357ffe166eda9` |
| B_rest.jsonl | 6326 | `ad48209ae6cbbfb961d8fa594976ced94203bc04d0ce5608e997a2fd89169008` |
| attack_labels.json | 90 | `833b6e8d3d13095a085fe26fdcb7220a73c3ebfd6a39bbc8473e19a3ff951a49` |
| manifest.json | | `97f08309ed0a6ca8828b9ffe115c96bdf22c435d747b17f20d066aa037e91ca5` |

Scripts at registration: `score.py` `72f471b8c1a5911e211771b04276a6d1f90574d00e1f4af3508e0b4406800795`, `candidates.json` (rev0) `6d8088882a170f5315b84f6cb9847841ce820716901d19975f1605016787dd8c`, `build_benign.py` `fb3c2b778f1bf1423cb13310cc267800e8ba4a482a0a17b58af77b6d30fdd1ea`, `attack_labels.py` `111966355a0b4e057f703c8983db4e85cf0b93e8fd52d5ea5e1eecec93cb9d3f`, `as_common.py` `4528f7615dd964744768553cc89eeccf4a484aed659616f056c2293aa2dd3705`.
