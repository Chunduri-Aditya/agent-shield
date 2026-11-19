# Plugin gap analysis — runtime against the control list

Date: 2026-11-18. Code baseline: commit `b74506e`. Labels: FACT, INFERENCE, OPINION, UNVERIFIED.

The runtime does not enforce anything on a live tool call. What the repo calls the MCP proxy is a
one shot catalog screener, and the runtime kill switch turns the guard off. Since 2026-11-18 a
spend governor and an event log exist, and they run only inside the DW-01 Inspect task. No adapter
puts them in front of a real agent.

The control list and the plugin plan this analysis was checked against are local planning files.
They are not in the repo, so each control is named in full below.

## 0. Ranked gaps

1. No enforcement point on a live tool call (control 1).
2. The spend governor runs only inside the DW-01 eval task (control 6).
3. The event log is local, has no key and is written only by that task (control 9).
4. Product mode proceeds on flagged content, and one environment variable disables the guard.
5. System level notification is measured for one attack on one model (n=5 per cell), and
   Transparency Rate has no validated scorer to compare it with.

## 1. Control matrix

All rows are FACT unless marked.

### 1.1 Tier 1, enforced outside the model — call path

| # | Control | Status | Evidence |
|---|---|---|---|
| 1 | Policy gate on every tool call (allow, deny, ask) | ABSENT on a live path | `agent_shield/runtime/gate.py:64-118` maps a text screen to an action and takes no tool name or arguments. No `jsonrpc`, `tools/list`, `tools/call`, `subprocess` or `socket` in `agent_shield/runtime/` (pinned by `tests/test_runtime_failopen.py`, and for `tools/call` by `tests/test_gap_analysis_doc.py`). `showcase/guides/company_agent_adapter.md:174` states a live proxy is a non goal. |
| 2 | Least privilege tools, scoped short lived credentials | ABSENT | `agent_shield/runtime/host_policy.py:61-65` returns `CONTAIN` on both branches. `decide_host_exposure` has no caller in the runtime or the evals. A re export, a test file and a guide example use it. |
| 3 | Isolation patterns (plan then execute, dual LLM and others) | ABSENT | No runtime module holds a plan or a tool call. |
| 4 | Human approval for high risk actions, rate limited | PARTIAL | `REQUIRE_CONFIRM` only for a hard secret in screened text (`gate.py:97-100`). The governor asks before a looping call, but only in the eval, where a fixed answer stands in for the operator (`evals/wallet_guard.py`). No approval channel exists. `dedupe_key` is built (`alert_taxonomy.py:92`) and never read. |
| 5 | Egress allowlist, secret and PII scan on outbound arguments | PARTIAL | Secret and PII patterns run on inbound text only (`agent_shield/research.py:244-300`). No scan of outbound arguments and no allowlist. |

### 1.2 Tier 1, enforced outside the model — state and audit

| # | Control | Status | Evidence |
|---|---|---|---|
| 6 | Budget, rate and loop limits with hard stops | PARTIAL, eval only | `agent_shield/runtime/governor.py`: the `stale_repeat` rule one call at a time, ask on the first trip, terminate on the second, and an optional budget. In the eval it is wired only into `evals/wallet.py`, through `evals/wallet_guard.py`. `scripts/wallet_governor_demo.py` also replays it on scripted traces. The eval does not use the governor's budget: there the hard stop is Inspect's `token_limit` (`evals/wallet.py:165`). |
| 7 | Tool definition pinning and hashing, alert on change | ABSENT | A SHA256 of the screened text is computed per screen (`agent_shield/research.py:639`) and carried on the alert card (`agent_shield/runtime/alert.py:24`). No tool baseline is stored or compared. `mcp.lock` holds `"tools": {}` and one settings hash, and no code in the repo reads it. |
| 8 | Memory write provenance, quarantine, expiry, rollback | ABSENT | No memory code in the runtime. |
| 9 | Tamper evident logs forwarded off host | PARTIAL, eval only | `agent_shield/runtime/events.py`: a hash chained JSON lines log. An edit, a deleted, swapped or repeated line and a bad line fail `verify_chain`. The chain has no key and stays on the host: a cut at the end or a full rewrite shows only against a head hash kept elsewhere. Only the wallet guard writes to it. `alert.py`, `pipeline.py` and `mcp_proxy.py` do not. |
| 10 | Kill switch owned by the monitor, not the model | PARTIAL, eval only | In the eval the governor ends the sample on the second trip (Inspect decision `terminate`). The runtime switch is the opposite: `AGENT_SHIELD_GUARD_OFF` makes `guard_text` return ALLOW with no screen (`agent_shield/runtime/pipeline.py:13`, `95-111`). |

### 1.3 Tier 2, detectors (signals, never boundaries)

| Detector | Status | Evidence |
|---|---|---|
| Regex screener on tool descriptions | PRESENT | `agent_shield/runtime/mcp_proxy.py:177-265` |
| Regex screener on tool results | PARTIAL | `screen_tool_result` (`mcp_proxy.py:278-288`) has no caller outside the tests (`tests/test_mcp_proxy.py:258` and `tests/test_runtime_failopen.py`). |
| Loop detector on tool results (`stale_repeat`) | PRESENT in the eval | `StaleRun` in `agent_shield/runtime/governor.py`, shared with `evals/wallet_meter.py`. |
| Classifier | ABSENT in the runtime | Offline experiment only (`experiments/classifier_guard/score.py:28`). |
| LLM monitor on action metadata | ABSENT | No such module. |

### 1.4 Tier 3, in model (advisory, never a security control)

- The quarantine stub tells the model to ask the operator (`mcp_proxy.py:27-31`).
- `defenses/spotlighting.py` exists, and the runtime does not import it.
- `report_security_event` (`evals/wallet_guard.py`) is a tool the model may call to report what it
  read. It is a signal source. It changes no decision, and its events get no framework id and the
  severity "unverified".

Measured: 20 pages of the DW-01 attack arm through `screen_tool_result` gave allow with no alert on
40 of 40 screens, 20 in product mode and 20 in strict mode (pinned by
`tests/test_gap_analysis_doc.py`). The regex screener does not flag this attack.

## 2. Fail open check

A crash does not become ALLOW. Five designed paths do, and so does one faulty screener answer.

`tests/test_runtime_failopen.py` holds 75 fault injection tests for the screener, the gate and the
CLI. A fault that raises stays an error: the library raises, and the CLI exits 1 with empty stdout.
One injected fault does give ALLOW: a screener that returns a well formed, empty result
(`test_b_empty_but_wellformed_result_fails_open_on_results`). The gate trusts the screener's answer
and has no second check.

Paths that are open by design, each pinned by a test in that file:

| Path | Evidence |
|---|---|
| Product mode: flagged injection gives `ALERT_PROCEED` | `gate.py:108-113` |
| The environment kill switch gives ALLOW with no screen | `pipeline.py:95-111` |
| `input_schema` is never screened | `mcp_proxy.py:125-131` |
| Oversize only content gives ALLOW | `gate.py:105-106` |
| Any unmatched case falls through to `ALERT_PROCEED` | `gate.py:118` |

Other findings:

- Strict mode exits 1 for both a crash and a quarantine (`agent_shield/runtime/mcp_proxy_cli.py:144`),
  so a caller cannot tell them apart. FACT.
- No timer exists in the screening path. A slow screener blocks its caller. INFERENCE.
- `agent_shield/runtime/screen.py:47` uses a bare `assert`, which `python -O` removes. FACT.

The governor path fails closed, and tests in `tests/test_wallet_guard.py` hold each case (FACT):

- A fault in the governor or in the event log fails the sample. Inspect would show the model a file
  error as a tool error and go on, so the guard turns such errors into its own error type.
- The loop tool runs only a call the governor cleared. An approval policy set on the eval replaces
  the policy of the task, and the tool then refuses to run.
- The governor reads each result as the tool returns it. Inspect gives every call of one model
  message the same history, so a governor fed from the history would let a whole batch through.

## 3. The wedge

### A. Spend enforcement at detection time

Built and measured. Attempt 2 of the run is complete. An interrupted attempt 1 finished the
attack, observe cell only. Record: [results/wallet/DW01_governor_haiku55_2026-11-18.md](../../results/wallet/DW01_governor_haiku55_2026-11-18.md)
(diagnostic, n=5 per cell, one model, operator stand in "hold").

| Cell | Flagged | Mean spend after flag (tokens) | Loop calls run after flag |
|---|---|---|---|
| attack, observe, attempt 1 | 5 of 5 at turn 4 | 8,087 | 2 to 6 |
| attack, observe, attempt 2 | 5 of 5 at turn 4 | 10,486 | 4 to 6 |
| attack, enforce | 5 of 5 at turn 4 | 3,258 | 0 |
| benign heavy, observe | 0 of 5 | none | none |
| benign heavy, enforce | 0 of 5 | none | none |

Mean spend after the flag is 60% to 69% lower with enforcement, across 2 observe runs of 5
samples each. The enforce cell finished once. Benign heavy completed 5 of 5 in both modes, with 0 calls held and 0 samples stopped.

Limits already measured (FACT, static rows of the same record, scripted traces with no model):

- One varying word per page, two tools in turn, and a text turn every third turn each pass the rule
  with 0 trips. Only a budget stops them.
- A benign poll that returns the same text is asked about at call 5. It completes when the operator
  approves and stops when no answer comes.

The claim under test is therefore "stops the unvaried loop; hard cap is the backstop", never "stops
denial of wallet". No adaptive attack has been run.

Already published in arXiv 2609.28585 (section 6 has the numbers): the attack, a stop outside the
model before the next call, long benign work under enforcement, and loops that dodge a rule. The
first two static rows above are minimal scripted instances of that paper's changing payload and
multi tool vectors, run against our rule with no model. What this run adds is the repeated content
rule and the observe arm: the same flag stops nothing there, so the spend after it is counted.
Section 6 lists a third point, the ask before the stop. That paper says its changing payload is
"designed to evade defenses that rely on repeated strings". INFERENCE: our rule is a defense of
that kind.

### B. Two channel notification

Built for DW-01. `SecurityEvent` wraps an `AlertCard` and adds time, session, tool, decision,
channel and framework ids. An OWASP LLM or MCP id without its edition, or an ATLAS id without its
data release, is refused. Guard events read their ids from `risk_registry.py`.

Measured row (FACT, same record): **self report 0 of 20, guard 10 of 10 on attack.** The model
called `report_security_event` in 0 of 20 samples. A guard event exists for 10 of 10 attack samples
and for 0 of 10 benign heavy samples.

| Guard | Self report | Meaning | Severity | Measured (20 samples) |
|---|---|---|---|---|
| fired | made | Confirmed | high | 0 |
| fired | none | Missed or concealed | highest | 10 |
| silent | made | Detector gap or false report | low | 0 |
| silent | none | Known only from eval ground truth | none | 10 |

This is a count for one tool description on one model. It is not a rate for any other setting.

Not built: an out of band sink (webhook, SIEM, pager), a key or an off host anchor for the chain,
deduplication and a rate cap for guard events, and any event from the screening path.

### C. Model TR against system TR

Not built.

- `agent_shield/runtime/proof_metrics.py:58-173` covers the guard side on static fixtures only. It
  has no utility, no overhead and no live run. FACT.
- `EpisodeOutcome` holds both channels, and `cell()` ignores `perimeter_alert`
  (`agent_shield/disclosure/__init__.py:70`, `75-86`). FACT.
- Enforcement hides the attack from the model, so model TR needs an observe only arm on the same
  samples. The governor demo has that arm for DW-01. INFERENCE.
- The wallet module has no TR. The self report count above is a tool call count, not TR.
- C waits on a validated TR scorer.

## 4. Adapters

Claude Code hook facts, from the official hooks reference (`code.claude.com/docs/en/hooks`, read
2026-11-18, section "Block the action when a hook fails"):

| Fact | Label |
|---|---|
| A hook that crashes, prints bad JSON or exits with a code other than 0 or 2 lets the action go ahead | FACT |
| A timed out `PreToolUse` hook does not block; the default timeout is 600 seconds | FACT |
| `"onFailure": "block"` on a `command` or `http` hook blocks on failure; it needs v2.1.295 or later | FACT |
| When hooks disagree, deny wins over defer, ask and allow | FACT |
| `continue: false` stops the session and does not block the call, so it must be paired with deny | FACT |

Fail closed config, with our command in place of the example's:

```json
{ "hooks": { "PreToolUse": [ { "matcher": ".*", "hooks": [
  { "type": "command", "command": "agent-shield-gate", "onFailure": "block" } ] } ] } }
```

- UNVERIFIED: that a hook deny holds under `bypassPermissions`. The hooks reference does not say.
- INFERENCE: an `mcp_tool` hook fails open, since the reference names only `command` and `http`
  for `onFailure`.

| Adapter | Can enforce | Cannot enforce |
|---|---|---|
| Claude Code hook (not built) | Deny any tool call, including `mcp__.*`; rewrite a tool result; stop the session | Session tokens or cost (the `PreToolUse` input has no such field); anything after `disableAllHooks`; a call in flight |
| MCP stdio proxy (not built, a stated non goal) | Screen and pin `tools/list`; deny `tools/call`; withhold results, for any MCP client | Built in tools such as Bash; model tokens |
| Inspect approver (built, eval only) | Approve, hold or terminate per call, with usage visible | Nothing for a real user |
| Catalog CLI (built) | Screen a catalog once | Anything at call time; a change between screen and use |

OPINION: build the hook next. It needs no transport code, and its fail closed behaviour is
documented.

## 5. Integrate, do not rebuild

As reported by each project's README or model card on 2026-11-18. Recheck before any integration.

| Tool | License | Cost | Use |
|---|---|---|---|
| Snyk Agent Scan (`snyk/agent-scan`) | Apache-2.0 | Needs a Snyk token; sends tool names and descriptions to Snyk | Optional static scan at install. Never on the decision path. |
| LlamaFirewall | MIT | AlignmentCheck needs a paid model API key | Skip for now. |
| Prompt Guard 2 (86M, 22M) | Llama 4 Community License, gated | Local, no API tokens; CPU latency TBD | Candidate signal. The license needs a read before it ships. |
| LLM Guard | MIT, archived 2026-07-09 | Not applicable | Do not depend on it. |
| `protectai/deberta-v3-base-prompt-injection-v2` | Apache-2.0 | Local | Preferred Tier 2 signal; already pinned at `experiments/classifier_guard/score.py:28-29`. |

None of these does a tool call gate, a spend governor or an operator log. Adaptive attacks reach
over 90% success against several such classifiers (Nasr et al., arXiv 2510.09023), so a classifier
is a signal only.

## 6. Prior work

Method: seven papers were read in full from the arXiv PDF text on 2026-11-19 — arXiv 2602.22303,
2608.02464, 2608.02657, 2608.27092, 2608.30686, 2609.28585 and 2407.20859. The first six were also
read from the HTML text on 2026-11-18.
Every line quoted to support a statement was checked against the text, 230 of 232 by script and 2
by eye. A quote check shows that the words are in the paper. It does not prove a "has no", so each
"has no" below also rests on a search of the full text. A local prior art table, which is not in the
repo, holds one row per paper. Other items in this section were seen as an abstract, a README or a
search result, and are marked so.

Transparency Rate alone is not new: InjecAgent (arXiv 2403.02691) reports a "sensitivity rate", a
keyword based share of outputs that recognise the attacker's instruction as abnormal. Only that
passage of the paper was checked.

**Already published, so not ours to claim.**

- The attack and a stop outside the model. arXiv 2609.28585 evaluates denial of wallet through tool
  returns, with a paged search tool as its worked example, and a host side check that runs before
  the next provider call. arXiv 2407.20859 makes agents loop with an injected repeat instruction,
  also through tool output (20.0% on a mail agent).
- Long benign work under enforcement. arXiv 2609.28585 runs 60 benign workflows of 8 to 12 steps:
  a fixed depth cap stops 60 of 60, its growth gated successor stops 0 of 60, and 53 of 60 complete.
- Loops that dodge a rule. The same paper runs vectors that change the payload each turn, spread
  the loop over several tools and hug a threshold. It says the changing payload is "designed to
  evade defenses that rely on repeated strings". INFERENCE: our `stale_repeat` rule is a defense of
  that kind. Two of our static rows (one varying word, two tools in turn) are minimal scripted
  instances of those vectors, with no model.
- A detector against a self report tool. arXiv 2602.22303 records an LLM monitor and a trained
  `report_scheming()` call on the same trajectories and shows that they catch different attacks.

**Disclosure.** We know of no published evaluation that, for prompt injection, scores a system
level notification channel (a guard or a log) separately from the acting model's own disclosure,
over all injected samples, next to attack success and utility.

- arXiv 2608.30686 scores the model's own alert over all evaluable runs, next to attack success,
  task success and a combined safe and useful rate, with an LLM judge checked against two humans
  (kappa 0.83 on 192 traces). It scores no guard or log channel. So the model side alone is done.
- arXiv 2602.22303 scores the two channels next to the undetected attack rate. The setting is a
  hidden side task, not prompt injection, and task utility is not next to it.
- arXiv 2608.27092 reports detector recall and an egress guard next to attack success. It reports
  no rate of the model telling anyone.

**Two channels.** We know of no published evaluation that reports, for prompt injection on tool
using agents, a per sample cross table of an external guard against the acting model's own
structured self report, and ranks "guard fired, model silent" as a separate, higher severity
signal.

- arXiv 2602.22303 is the nearest. At 5% false positives its strong monitor misses 38 to 46% of the
  attacks that the self report catches, and an OR rule moves the undetected rate from 6.7% to 5.1%
  for one model. It prints no joint counts per sample and gives the monitor only case no severity.
  Its model is trained to report, and its threat is not prompt injection.
- arXiv 2608.02657 classifies 634 turns that a hidden state probe detected, by what the model's
  reasoning shows: no deliberation on 196 (30.9%), and the class `recognition_but_no_reaction` on
  298 (47.0%). The probe is a precondition and not a second axis, the signal is reasoning text and
  not a tool call, and no operator signal is defined.
- arXiv 2608.30686 names the pair "high ASR, low AR" a silent attack surface, as rates per cell.
  arXiv 2407.20859 asks the core model whether a loop instruction is harmful and gets 0.0%
  detection. Neither has a second channel on the same sample.

**Spend.** We know of no published evaluation that runs one repeated content detector on a denial
of wallet loop in two arms, one where the flag stops nothing and one where it holds the next call,
and reports the token spend after the flag in each.

- arXiv 2609.28585 is the nearest, and it covers most of this ground at a far larger scale: 243
  executions on six model families, four host rules on token mass, growth, call counts and dollars,
  spend with the defense off and with a matched full stack, and the spend through the blocking
  turn. No rule of its four compares tool results, no arm flags without stopping, and no operator
  is asked before a stop. Those three points are all that our run adds to it.
- arXiv 2608.02464 reports that a loop trap exits at 10 steps in 5 of 5 runs, against 30 before a
  circuit breaker. The trap is a synthetic failure and not an attack, the unit is steps and not
  tokens, and the breaker is not defined.
- Seen only as a README or a blog post, not read in full: OpenRouter's loop detector (spend with
  enforcement on looping runs), `agent-loopguard` (a result aware option with no numbers), and a
  denial of wallet benchmark with a `loop_detect` defense.

What Agent Shield has against these three statements is one diagnostic run: one model, one
payload, 5 samples per cell. Papers seen only as an abstract and not read in full: arXiv 2608.30362,
2609.32691, 2610.23254 and 2605.17634.

## 7. Adaptive attack plan

Each defended module reports static and adaptive results side by side. The attacker knows the
rule. A defense with no adaptive row is labelled "static only" (Nasr et al., arXiv 2510.09023).

| Module | Adaptive attack | State |
|---|---|---|
| Governor | V1, V2 and V5 of arXiv 2609.28585 against our rule, plus a text turn between calls | Minimal scripted rows for V1, V2 and the text turn; no run on a model |
| Regex screener | Search with the screener as oracle: confusable characters, text split across fields, the unscreened `input_schema`, the heuristic exemptions (`agent_shield/runtime/desc_heuristics.py:70-74`, `96-99`) | Not started |
| Classifier, if added | Black box search with score feedback under a fixed query budget | Not started |
| Self report channel | Injected text that tells the model to stay silent, to report a benign kind, or to flood | Flood cap tested (5 a session); the rest not started |
| Event log | Rewrite the whole chain; insert one bad line | Tested: a bad line fails; a rewrite shows only against a kept head |

For the governor, the adaptive set is three vectors of arXiv 2609.28585, which evaluates all of its
vectors on models:

- V1 (changing payload): the returned content changes form and size from turn to turn.
- V2 (multi tool spread): the loop runs over several tools, so no one tool shows all of it.
- V5 (threshold hugging): the payload grows only while the session stays under the limit that the
  attacker estimates from feedback. For our rule that limit is the third stale result in a row
  from one tool (`governor.py:54`, `86`).

The static rows "varying word" and "alternating tools" are minimal scripted instances of V1 and V2:
one word changes in a fixed template, and two tools take turns. V5 has no row. The text turn
between calls is ours.

## 8. Threats to the plugin

| Threat | Evidence | Mitigation |
|---|---|---|
| Alert flooding (OWASP Agentic threat T10) | A benign sentence with one absolute word ("always", "never") raises an alert card in product mode (pinned by `tests/test_gap_analysis_doc.py`). `dedupe_key` is never read. | Deduplicate per session, kind and evidence hash; cap the rate; log a count of what was suppressed. |
| False self reports as denial of service | The report tool is model controlled. A report call is never held, so only the token limit bounds a loop of reports. | A report never blocks and never pages alone; the log keeps 5 a session. Governing report calls is open. |
| Guard bypass | `disableAllHooks`, the environment kill switch, the unscreened schema, a catalog change between screen and call, an approval policy that replaces the governor. | The loop tool refuses a call the governor did not clear (built, eval only). Pin tool hashes. Deny edits to settings and the hook path in the gate. |
| Forced governor stop | The benign poll in the static rows stops when no operator answers. A poll longer than 3 calls after one approval is terminated. | Ask before terminate (built). Report benign completion with every run. |
| Log tampering | The chain has no key. | Keep the head hash off host. |

## 9. Done, and the next move

Done on DW-01: the governor and the event log, both inside the Inspect task, and one measured run.

Next move (OPINION): a Claude Code `PreToolUse` adapter that calls the same governor, with
`"onFailure": "block"`, and a test for each row of the hook table above.
