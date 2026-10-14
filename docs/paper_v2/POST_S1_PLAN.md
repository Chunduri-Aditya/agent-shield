# Plan after S1: S2 contracts, S7 planner and executor, AgentDojo row

Status: draft written 2026-10-14 so every v2 study has a build plan (coverage check, `V2_STUDIES.md` Coverage). Nothing here runs before S1's main runs finish and each study's preregistration is frozen (D17, D34). Fields for Aditya stay **TBD (Aditya)**. Open weight studies S4 and S6 are outside v2 (D18 amended 2026-10-14) and keep their skeletons in `V2_STUDIES.md` for a follow up.

## Shared
- Reuse the S1 harness unchanged: the v2 task set and nonce stubs, `tools_event_v2`, the S1 gates (`served_model`, `thinking_request`, delivery per arm, caps from the setup record), `allocate.py`, `panel_api.py` and `blind_export.py`. Each study adds its own task file, setup record and data directory.
- Each study follows `docs/EVAL_DESIGN_FRAMEWORK.md` section 1 and gets `docs/paper_v2/prereg/<study>.md` before its freeze.
- Budget at RR08 estimates, recomputed from measured smoke costs: S2 $11.10, S7 $7.24, AgentDojo $18.63, inside the D31 envelope after S1 and the judge.

## S2 agent declared boundary contracts
| Item | Plan |
|---|---|
| Arms | (1) no contract: reuse S1 poisoned logs of the same models; (2) declared and enforced: the agent first calls `declare_contract(tools, recipients)`, and the harness blocks any later call outside it; (3) model bypassed: the injected `send_message` goes straight into the enforcement layer, no API spend; clean arm for utility |
| Models | RR08: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-sonnet-4-6`, `claude-opus-4-8` (final list TBD (Aditya)) |
| Declaration mechanics | forced `tool_choice` is rejected on Sonnet 5.5, Opus 5.5 and Fable 5.1 (RR08, E35), so every model gets `auto` and a system instruction to declare first, never a forced choice on some models only. Declaration compliance (first call is `declare_contract`) is itself a reported event |
| Schema rule | no `reasoning`, `thinking`, `trace` or rationale field in the declaration schema: such a field triggers a billed `reasoning_extraction` decline (RR08) |
| Outcomes | blocked out of bound calls, executed out of bound calls, declared versus used tools (events); a preregistered **contract poisoned** outcome: the declaration itself lists the canary recipient; the defense triple per arm with the 50% utility flag |
| Variants | payload variants TBD (Aditya); any variant beyond the cleared TL-01 directive needs a `MAPPINGS.md` row and an `ETHICS.md` entry first; persuasion variants only after D26 clearance |
| Build steps | (a) task file with `declare_contract` and an enforcement solver; (b) scorer layer on `tools_event_v2` for declaration and blocked calls; (c) model bypassed harness test with no model; (d) gates for declaration delivery; tests first, mutation rows (enforcement disabled, recipient check by substring, contract poisoned not flagged) |
| Prereg fields | hypothesis, refutation number, P and m, stopping rule: TBD (Aditya) |

## S7 planner and executor split
| Item | Plan |
|---|---|
| Arms | (0) one model plans and executes; (1) planner sees tool descriptions, so the poison reaches the planner; (2) planner sees tool names only, so the poison reaches the executor alone |
| Pairs | RR08: Sonnet 5.5 plans and Haiku 5.5 executes; Haiku 5.5 plans and Sonnet 5.5 executes; Opus 4.8 plans and Sonnet 4.6 executes; each against the executor alone (final list TBD (Aditya)) |
| Mechanics | a custom solver calling two models by Inspect model role (`get_model(role=...)`), so each call logs its own `ModelEvent` with its raw response (E35); not `handoff()`, whose default filter strips reasoning and turns tool calls into text. The plan is the S2 declaration format handed to the executor as a message, without enforcement |
| Outcomes | strict nonce event (primary), executor calls outside the plan, declared versus used tools, any call count; two disclosure labels per episode (plan text and executor final message) through the S1 label pipeline |
| Build steps | (a) two role solver; (b) gate that both roles' raw responses are logged and the served model matches each role; (c) scorer layer for plan violations; tests first, mutation rows (planner response unlogged, role swapped, plan violation missed) |
| Prereg fields | hypothesis, refutation number, stopping rule: TBD (Aditya); P = 10 and m = 4 in the skeleton are reopened against the S1 P = 80 set |

## AgentDojo external validity row (D35)
- `inspect-evals[agentdojo]` is already a dependency (`pyproject.toml:9`); task `agentdojo(attack="important_instructions")` (`inspect_evals/agentdojo/agentdojo.py:13-17`).
- Steps: decide yes or no after S1 costs are measured (D35); pin the editable checkout's commit in the run record (the venv's `.pth` points at a second checkout outside the one `pyproject.toml` names; found 2026-10-14); a `MAPPINGS.md` row for the AgentDojo attack; one smoke per model, then the banking suite (16 user tasks × 9 injection tasks) on the models Aditya picks; report AgentDojo's own utility and targeted attack success beside S1, never merged with S1 numbers.

## Order after S1
1. S1 labels and headline (Phase 7 of the S1 plan).
2. S2 and S7 preregistration questionnaires, then build (one task file each), freeze, smoke, main.
3. AgentDojo row if Aditya says yes.
4. v1.2 steps 3 and 6 to 9 finish first in publication order (D21 amended): no S1, S2 or S7 number appears anywhere before the v1.2 upload.
