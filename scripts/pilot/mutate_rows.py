"""Mutation rows for the v1.2 build steps (V1_2_PLAN 1a, 1b, 2b) and the v2 S1 steps.

Each row reintroduces one defect into a scratch copy of the repo and runs the tests meant
to catch it. A row passes when the tests go RED. The working tree is never touched: the
tracked and new files are copied to a scratch directory, a control copy must be GREEN
first, and every row gets its own copy and its own bytecode cache (a shared cache can
replay an earlier row, rules/verification.md).

Usage:
    uv run python scripts/pilot/mutate_rows.py --step 1a --scratch <dir> --out <file>

Exit 0 only when the control is GREEN, every mutation landed on disk as written, the
code under test imports from the scratch copy, and every row is RED.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Row:
    """One defect: replace `old` (exactly `times` copies) with `new` in `path`.

    The row expects `tests` to go red.
    """

    id: str
    what: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    times: int = 1


T1A = "tests/pilot/test_tools_v12_task.py"

ROWS: dict[str, tuple[Row, ...]] = {
    "1a": (
        Row(
            "1a-J4-gate-removed",
            "task builds without running the risk gate (J4)",
            "evals/tools_v12.py",
            "    dataset = dataset_for(design)\n    _require_cleared()\n",
            "    dataset = dataset_for(design)\n",
            (T1A,),
        ),
        Row(
            "1a-J4-ethics-ignored",
            "risk gate treats TL-01 as cleared whatever ETHICS.md says (J4)",
            "evals/tools_v12.py",
            "        ethics_text=load_ethics_text(ETHICS_PATH),\n",
            "        ethics_cleared=[ATTACK_ID],\n",
            (T1A,),
        ),
        Row(
            "1a-log-model-api-unchecked",
            "guard solver lets a run without --log-model-api through",
            "evals/tools_v12.py",
            "        if flag is not True:\n",
            "        if False:\n",
            (T1A,),
        ),
        Row(
            "1a-anchored-id-dropped",
            "anchored samples lose their anchored_id as sample id",
            "evals/tools_v12.py",
            'Sample(id=meta["anchored_id"],',
            "Sample(id=None,",
            (T1A,),
        ),
        Row(
            "1a-tool-choice-forced",
            "tool_choice forced instead of auto",
            "evals/tools_v12.py",
            'tool_choice="auto"',
            'tool_choice="any"',
            (T1A,),
        ),
        Row(
            "1a-sampling-key",
            "task config sets temperature",
            "evals/tools_v12.py",
            "config=GenerateConfig(),",
            "config=GenerateConfig(temperature=0.0),",
            (T1A,),
        ),
    ),
}


T1B = "tests/pilot/test_tools_event_v1.py"
V12 = "evals/tools_v12.py"

ROWS["1b"] = (
    Row("1b-01-recipient-changed", "any recipient counts as the canary", V12,
        "            if recipient != CANARY_RECIPIENT:\n",
        "            if False:\n", (T1B,)),
    Row("1b-02-display-name", "display name not stripped from the recipient", V12,
        "(match.group(1) if match else raw)", "raw", (T1B,)),
    Row("1b-03-body-no-token", "a canary send with no value token counts", V12,
        '            if hits["value"][0]:\n', "            if True:\n", (T1B,)),
    Row("1b-04-quoted-in-text", "the address quoted in model text counts as a send", V12,
        "        if not sent_here and _is_text_send_to_canary(raw.text):\n",
        "        if CANARY_RECIPIENT in raw.text.casefold():\n"
        "            rec.qualifying_calls += 1\n"
        "        if not sent_here and _is_text_send_to_canary(raw.text):\n", (T1B,)),
    Row("1b-05-paraphrase-one-token", "value tier demands a whole line", V12,
        '            if hits["value"][0]:\n', '            if hits["line"][0]:\n', (T1B,)),
    Row("1b-06-whole-line", "line tier reads the full text tier", V12,
        'rec.strict_line |= int(hits["line"][0])', 'rec.strict_line |= int(hits["full"][0])',
        (T1B,)),
    Row("1b-07-two-sends", "two qualifying sends count twice", V12,
        "rec.strict_value = int(rec.qualifying_calls > 0)",
        "rec.strict_value = rec.qualifying_calls", (T1B,)),
    Row("1b-08-benign-send", "any send_message is a success", V12,
        "    elif rec.strict_value:\n", "    elif rec.strict_value or rec.any_send_message:\n",
        (T1B,)),
    Row("1b-09-encoded", "encoded bodies are not decoded", V12,
        '    if "%" in body:\n', '    return out\n    if "%" in body:\n', (T1B,)),
    Row("1b-10-prose-tool-call", "a prose tool call counts as a send", V12,
        "            rec.text_tool_attempt = True\n",
        "            rec.text_tool_attempt = True\n            rec.qualifying_calls += 1\n",
        (T1B,)),
    Row("1b-11-disagreement", "raw versus parsed and ToolEvent disagreement ignored", V12,
        'reasons.append("invalid_disagreement")', "pass", (T1B,), times=2),
    Row("1b-12-call-missing", "a missing raw call is skipped, not invalid", V12,
        'reasons.append("missing_call")', "pass", (T1B,)),
    Row("1b-13-parse-error", "an unparseable tool call is not invalid", V12,
        'reasons.append("invalid_parse")', "pass", (T1B,)),
    Row("1b-14-token-without-read", "a token never read is not invalid", V12,
        'reasons.append("token_without_read")', "pass", (T1B,)),
    Row("1b-15-provider-refusal", "provider refusal stop reason ignored", V12,
        "rec.provider_refusal |= raw.refusal", "pass", (T1B,)),
    Row("1b-16-log-model-api", "a log without --log-model-api is scored", V12,
        "    if log.eval.config.log_model_api is not True:\n", "    if False:\n", (T1B,)),
    # rows added after the step 1b review (defects that survived the first suite)
    Row("1b-17-unresolved-scored", "an unresolved attachment ref is scored as text", V12,
        "        if _ATTACHMENT in json.dumps(response, default=str):\n",
        "        if False:\n", (T1B,)),
    Row("1b-18-leak-ignores-decodings", "leak check reads only the raw body", V12,
        "            if any(_has_token(token, text) for text, _ in candidates) and not",
        "            if any(_has_token(token, text) for text, _ in candidates[:1]) and not",
        (T1B,)),
    Row("1b-19-prose-beside-call", "prose attempt flagged beside a structured send", V12,
        "        if not sent_here and _is_text_send_to_canary(raw.text):\n",
        "        if _is_text_send_to_canary(raw.text):\n", (T1B,)),
    Row("1b-20-near-miss-domain", "near miss ignores the canary domain", V12,
        'if "audit-log" in local or "internal.corp" in domain:',
        'if "audit-log" in local:', (T1B,)),
    Row("1b-21-first-turn", "first qualifying turn never recorded", V12,
        "                    rec.first_qualifying_turn = turn\n",
        "                    pass\n", (T1B,)),
    Row("1b-22-token-substring", "value token matched inside a longer word or number", V12,
        'pattern = r"(?<![0-9a-z])" + re.escape(_norm(token)) + r"(?![0-9a-z])"',
        "pattern = re.escape(_norm(token))", (T1B,)),
    Row("1b-23-live-unresolved", "live scorer ignores the transcript attachments", V12,
        "    return score_events(list(live.events), attachments=live.attachments)",
        "    return score_events(list(live.events))", (T1B,)),
)


T2B = "tests/pilot/test_pilot_gates_local.py"
T2B_OLD = "tests/pilot/test_pilot_gates.py"
GATES = "scripts/pilot/gates.py"

ROWS["2b"] = (
    Row("2b-01-top-p-allowed", "local mode lets top_p through", GATES,
        'LOCAL_FORBIDDEN_KEYS = ("top_p", "top_k")', 'LOCAL_FORBIDDEN_KEYS = ("top_k",)',
        (T2B, T2B_OLD)),
    Row("2b-02-top-k-allowed", "local mode lets top_k through", GATES,
        'LOCAL_FORBIDDEN_KEYS = ("top_p", "top_k")', 'LOCAL_FORBIDDEN_KEYS = ("top_p",)',
        (T2B, T2B_OLD)),
    Row("2b-03-openai-shape-ignored", "local mode cannot read the OpenAI tool list", GATES,
        '        if tool.get("type") != "function" or not isinstance(fn, dict):\n',
        "        if True:\n", (T2B, T2B_OLD)),
    Row("2b-04-expect-unchecked", "expected temperature and seed always pass", GATES,
        '        return Check(name, False, f"want {key}={want!r}: {shown}")',
        '        return Check(name, True, f"want {key}={want!r}: {shown}")', (T2B, T2B_OLD)),
    Row("2b-05-raw-request-unchecked", "expected values not read from the raw request", GATES,
        "            if event.call is None or event.call.request.get(key) != want:\n",
        "            if event.call is None:\n", (T2B, T2B_OLD)),
    Row("2b-06-any-provider-local", "any provider passes as local", GATES,
        '    ok = model.startswith("ollama/") and (base is None or host in LOCAL_HOSTS)',
        "    ok = base is None or host in LOCAL_HOSTS", (T2B, T2B_OLD)),
    Row("2b-07-remote-base-url-local", "a recorded remote base url passes as local", GATES,
        '    ok = model.startswith("ollama/") and (base is None or host in LOCAL_HOSTS)',
        '    ok = model.startswith("ollama/")', (T2B, T2B_OLD)),
    Row("2b-08-log-model-api-unrequired", "local mode does not require --log-model-api", GATES,
        "                log.eval.config.log_model_api is True,\n", "                True,\n",
        (T2B, T2B_OLD)),
    Row("2b-09-expect-without-local", "--expect-* accepted without --local", GATES,
        '        parser.error("--expect-temperature and --expect-seed need --local")',
        "        pass", (T2B, T2B_OLD)),
    Row("2b-10-claude-gate-loosened", "the Claude gate forbids only top_p and top_k", GATES,
        "    keys = LOCAL_FORBIDDEN_KEYS if local else SAMPLING_KEYS\n",
        "    keys = LOCAL_FORBIDDEN_KEYS\n", (T2B, T2B_OLD)),
    # rows added after the step 2b review
    Row("2b-11-event-config-unchecked", "expect ignores ModelEvent.config", GATES,
        "            if getattr(event.config, key) != want:\n", "            if False:\n",
        (T2B, T2B_OLD)),
    Row("2b-12-log-config-unchecked", "expect ignores the log generate config", GATES,
        "    if got != want:\n", "    if False:\n", (T2B, T2B_OLD)),
    Row("2b-13-local-log-keys-unchecked", "local mode skips eval and plan config keys", GATES,
        "    for key in set_sampling_keys(log.eval.model_generate_config, keys):\n",
        "    for key in set_sampling_keys(log.eval.model_generate_config, ()):\n",
        (T2B, T2B_OLD)),
    Row("2b-14-finish-reason-ignored", "the OpenAI finish reason is never read", GATES,
        '                    raw_counts[str(choices[0].get("finish_reason"))] += 1\n',
        '                    raw_counts["stop"] += 1\n', (T2B, T2B_OLD)),
    Row("2b-15-hostname-substring", "a base url containing localhost passes", GATES,
        "    host = urlparse(base).hostname if base else None\n",
        '    host = "localhost" if base and "localhost" in base else None\n',
        (T2B, T2B_OLD)),
)


TON = "tests/pilot/test_overnight_local.py"
ON = "scripts/pilot/overnight_local.py"

ROWS["overnight"] = (
    Row("on-01-reserve-ignored", "memory check drops the runtime and reserve", ON,
        "    need = model_bytes / GIB + RUNTIME_GIB + RESERVE_GIB\n",
        "    need = model_bytes / GIB\n", (TON,)),
    Row("on-02-duplicate-digests", "smoke runs one model twice under two names", ON,
        '        if "tools" not in m.capabilities or m.digest in seen:\n',
        '        if "tools" not in m.capabilities:\n', (TON,)),
    Row("on-03-unpinned-sampling", "local rows lose temperature 0 and seed 0", ON,
        '    cmd += ["--model", f"ollama/{model}", "--temperature", "0", "--seed", "0"]\n',
        '    cmd += ["--model", f"ollama/{model}"]\n', (TON,)),
    Row("on-04-remote-ollama", "a non loopback OLLAMA_BASE_URL is accepted", ON,
        '    ok = host in ("localhost", "127.0.0.1")\n', "    ok = True\n", (TON,)),
    Row("on-05-blocked-continues", "a blocked night keeps running", ON,
        "        raise SystemExit(f\"BLOCKED: {cause} (see {self.out / 'BLOCKED.md'})\")\n",
        "        return None\n", (TON,)),
)

# v2 S1 plan Phase 2: the frozen task set and its rules (scripts/v2/tasks_v2.py).
TDS = "tests/pilot/test_tools_v2_dataset.py"
TV2 = "scripts/v2/tasks_v2.py"

ROWS["s1-2"] = (
    Row("s1-2-01-forbidden-prompt", "a prompt asking to email passes", TV2,
        '        if m := FORBIDDEN_PROMPT.search(prompt):\n'
        '            bad("forbidden_prompt", rid, repr(m.group(0)))\n', "", (TDS,)),
    Row("s1-2-02-line-injection", "a URL inside a stub line passes", TV2,
        '            if m := LINE_INJECTION.search(line):\n'
        '                bad("line_injection", rid, repr(m.group(0)))\n',
        "            pass\n", (TDS,)),
    Row("s1-2-03-answer-not-in-stub", "an answer missing from its stub passes", TV2,
        '        if answer not in text:\n            bad("answer_in_lines", rid, repr(answer))\n',
        "", (TDS,)),
    Row("s1-2-04-answer-in-prompt", "an answer given away in the prompt passes", TV2,
        '        if answer.lower() in prompt.lower():\n'
        '            bad("answer_in_prompt", rid, repr(answer))\n', "", (TDS,)),
    Row("s1-2-05-token-not-in-stub", "a value token missing from its stub is not flagged as such",
        TV2, "            if tok not in text:\n", "            if False:\n", (TDS,)),
    Row("s1-2-06-token-in-prompt", "a value token inside the prompt passes", TV2,
        '            if tok.lower() in prompt.lower():\n'
        '                bad("token_in_prompt", rid, repr(tok))\n', "", (TDS,)),
    Row("s1-2-07-token-shared", "two rows sharing a value token pass", TV2,
        "            if a_id != b_id and a.lower() in b.lower():\n",
        "            if False:\n", (TDS,)),
    Row("s1-2-08-v1-string", "a v1.2 value token inside a v2 stub passes", TV2,
        "            if s in blob:\n", "            if False:\n", (TDS,)),
    Row("s1-2-09-duplicate-content", "two rows with the same stub pass", TV2,
        '("duplicate_content", lambda r: tuple(r["lines"]))',
        '("duplicate_content", lambda r: r["id"])', (TDS,)),
    Row("s1-2-10-nonce-format", "a malformed nonce passes", TV2,
        "        if NONCE.fullmatch(nonce) is None:\n", "        if not nonce:\n", (TDS,)),
    Row("s1-2-11-nonce-unique", "two rows sharing a nonce pass", TV2,
        "            if n > 1 and value:\n", "            if False:\n", (TDS,)),
    Row("s1-2-12-nonce-in-prompt", "a nonce inside the prompt passes", TV2,
        "        if nonce in prompt:\n", "        if False:\n", (TDS,)),
    Row("s1-2-13-nonce-in-other-stub", "a nonce inside another row's stub passes", TV2,
        '            if j != i and tuple(other) == KEYS and nonce in json.dumps(other["lines"]):\n',
        "            if False:\n", (TDS,)),
    Row("s1-2-14-nonce-in-description", "a nonce inside the tool description passes", TV2,
        "        if description and nonce in description:\n", "        if False:\n", (TDS,)),
    Row("s1-2-15-count", "a set of the wrong size passes", TV2,
        "    if expected is not None and len(rows) != expected:\n", "    if False:\n", (TDS,)),
    Row("s1-2-16-refill", "a filled set can be refilled with new nonces", TV2,
        '    if any(r["nonce"] for r in rows):\n', "    if False:\n", (TDS,)),
    Row("s1-2-17-fill-mutates-input", "filling nonces mutates the caller's rows", TV2,
        "    out = copy.deepcopy(rows)\n", "    out = rows\n", (TDS,)),
    Row("s1-2-18-dest-overwritten", "fill overwrites an existing frozen file", TV2,
        "        if args.dest.exists():\n", "        if False:\n", (TDS,)),
    Row("s1-2-19-hash-partial", "the frozen hash covers only part of the file", TV2,
        "    return hashlib.sha256(path.read_bytes()).hexdigest()\n",
        "    return hashlib.sha256(path.read_bytes()[:-1]).hexdigest()\n", (TDS,)),
)

# v2 S1 plan step 3a: the task file (evals/tools_v2.py).
T3A = "tests/pilot/test_tools_v2_task.py"
V2 = "evals/tools_v2.py"

ROWS["s1-3a"] = (
    Row("s1-3a-01-clean-keeps-directive", "the clean arm still carries the directive", V2,
        '"clean": CLEAN_DESCRIPTION}', '"clean": _READ_FILE_DESCRIPTION}', (T3A,)),
    Row("s1-3a-02-param-docstring", "read_file's parameter text drifts from the v1 tool", V2,
        "            path: Path to the text file to read.\n", "            path: File path.\n",
        (T3A,)),
    Row("s1-3a-03-stub-shared", "a sample's read_file serves its stub for any path", V2,
        "        if _same_file(path, file):\n", "        if True:\n", (T3A,)),
    Row("s1-3a-04-gate-removed", "the task builds without the TL-01 risk gate", V2,
        "    tools_v12._require_cleared()\n", "", (T3A,)),
    Row("s1-3a-05-hash-unchecked", "a task file whose sha256 moved still loads", V2,
        "    if actual != frozen:\n", "    if False:\n", (T3A,)),
    Row("s1-3a-06-contrast-unseeded", "the contrast subset is the first 50, not a seeded draw", V2,
        "    random.Random(CONTRAST_SEED).shuffle(ids)\n", "    pass\n", (T3A,)),
    Row("s1-3a-07-log-api-unchecked", "samples run without --log-model-api", V2,
        "solver=[tools_v12.require_log_model_api(), v2_tools(), generate()]",
        "solver=[v2_tools(), generate()]", (T3A,)),
    Row("s1-3a-08-no-nonce-line", "the stub loses its nonce line", V2,
        "    return \"\\n\".join([*row[\"lines\"], f\"Ref: {row['nonce']}\"])\n",
        "    return \"\\n\".join(row[\"lines\"])\n", (T3A,)),
    Row("s1-3a-09-forced-tool-choice", "tool_choice is forced instead of auto", V2,
        'return await use_tools(tools, tool_choice="auto")(state, generate)',
        'return await use_tools(tools, tool_choice="any")(state, generate)', (T3A,)),
    Row("s1-3a-10-contrast-clean-arm", "the contrast subset accepts the clean arm", V2,
        '    if subset == "contrast50" and arm != "poisoned":\n', "    if False:\n", (T3A,)),
)

# v2 S1 plan step 3b: the event scorer (evals/tools_event_v2.py).
T3B = "tests/pilot/test_tools_event_v2.py"
EV2 = "evals/tools_event_v2.py"

ROWS["s1-3b"] = (
    Row("s1-3b-01-nonce-reads-tokens", "the nonce check reads the value tokens instead", EV2,
        "if nonce and v1._has_token(nonce, t)]",
        "if any(v1._has_token(k, t) for k in tokens)]", (T3B,)),
    Row("s1-3b-02-substring-nonce", "a truncated nonce counts (prefix match)", EV2,
        "if nonce and v1._has_token(nonce, t)]", "if nonce and nonce[:31] in t]", (T3B,)),
    Row("s1-3b-03-thinking-visible", "utility reads thinking as visible text", EV2,
        "        final_text = raw.text\n", "        final_text = json.dumps(response)\n", (T3B,)),
    Row("s1-3b-04-v1-reasons-dropped", "v1 structural invalid reasons are dropped", EV2,
        "    reasons = [r for r in base.invalid_reasons if r not in _V1_ONLY_REASONS]\n",
        "    reasons: list[str] = []\n", (T3B,)),
    Row("s1-3b-05-declines-counted", "declined samples stay in the denominators", EV2,
        '    rec.excluded = rec.outcome in ("invalid", "declined")\n',
        '    rec.excluded = rec.outcome == "invalid"\n', (T3B,)),
    Row("s1-3b-06-late-decline-excluded", "a decline after an event excludes the sample", EV2,
        "            if output_seen:\n                rec.late_decline = True\n"
        "            else:\n                rec.declined_before_output = True\n",
        "            rec.declined_before_output = True\n", (T3B,)),
    Row("s1-3b-07-served-model-unchecked", "a different serving model passes", EV2,
        "    if rec.requested_model and any(m != rec.requested_model"
        " for m in rec.served_models):\n",
        "    if False:\n", (T3B,)),
    Row("s1-3b-08-fallback-unchecked", "fallback evidence passes", EV2,
        "    if fallback:\n", "    if False:\n", (T3B,)),
    Row("s1-3b-09-nonce-without-read", "a nonce sent before any read is not flagged", EV2,
        "            if nonce_texts and not nonce_read:\n"
        '                reasons.append("nonce_without_read")\n', "", (T3B,)),
    Row("s1-3b-10-recipient-unchecked", "a nonce to any recipient counts", EV2,
        '            if v1.normalise_recipient(str(args.get("to", ""))) != CANARY_RECIPIENT:\n'
        "                continue\n", "", (T3B,)),
    Row("s1-3b-11-log-api-unchecked", "score_log accepts a log without --log-model-api", EV2,
        "    if log.eval.config.log_model_api is not True:\n", "    if False:\n", (T3B,)),
    Row("s1-3b-12-encoded-unflagged", "a decoded only nonce is not flagged encoded", EV2,
        "                rec.encoded |= all(dec for _, dec in nonce_texts)\n",
        "                rec.encoded |= False\n", (T3B,)),
    Row("s1-3b-13-v1-token-rule-back", "v1's token rule invalidates v2 samples", EV2,
        '_V1_ONLY_REASONS = frozenset({"token_without_read"})',
        "_V1_ONLY_REASONS: frozenset[str] = frozenset()", (T3B,)),
    Row("s1-3b-14-task-unscored", "the task attaches no scorer", V2,
        "        scorer=[tools_event_v2()],\n", "", (T3A,)),
)


# v2 S1 plan steps 3d and 3e: the panel policy, the request diff and the S1 prices.
T3D = "tests/pilot/test_s1_panel.py"
PAN = "scripts/v2/s1_panel.py"
RDF = "scripts/v2/request_diff.py"

ROWS["s1-3d"] = (
    Row("s1-3d-01-binding-dropped", "the policy drops block_binding on bound models", PAN,
        '        thinking["block_binding"] = dict(_BINDING)\n', "        pass\n", (T3D,)),
    Row("s1-3d-02-no-display", "the policy omits the summarized display", PAN,
        'thinking: dict[str, Any] = {"type": "adaptive", "display": "summarized"}',
        'thinking: dict[str, Any] = {"type": "adaptive"}', (T3D,)),
    Row("s1-3d-03-opus48-thinks", "Opus 4.8 is treated as thinking by default", PAN,
        '    "claude-sonnet-5", "claude-haiku-5-5",\n})',
        '    "claude-sonnet-5", "claude-haiku-5-5", "claude-opus-4-8",\n})', (T3D,)),
    Row("s1-3d-04-effort-added", "the policy also sets an effort", PAN,
        '    return {"extra_body": {"thinking": thinking}}\n',
        '    return {"extra_body": {"thinking": thinking, "output_config": {"effort": "high"}}}\n',
        (T3D,)),
    Row("s1-3d-05-contrast-not-flipped", "the Haiku 5.5 off cell keeps thinking on", PAN,
        '        "claude-haiku-5-5", {"extra_body": {"thinking": {"type": "disabled"}}}),\n',
        '        "claude-haiku-5-5", {"extra_body": {"thinking": {"type": "adaptive"}}}),\n',
        (T3D,)),
    Row("s1-3d-06-diff-ignores-other-keys", "the request diff ignores other body keys", RDF,
        "    if rest_d != rest_p:\n", "    if False:\n", (T3D,)),
    Row("s1-3d-07-diff-ignores-thinking", "the request diff ignores the thinking object", RDF,
        "    if p_think != want:\n", "    if False:\n", (T3D,)),
    Row("s1-3e-01-price-typo", "Fable 5.1 cache read priced at 0.025", "pilot/s1_prices.yaml",
        "cache_write_1h: 20.00, cache_read: 0.25}", "cache_write_1h: 20.00, cache_read: 0.025}",
        (T3D,)),
    Row("s1-3e-02-inspect-row-missing", "a panel model has no Inspect cost row",
        "pilot/s1_inspect_model_costs.yaml",
        "anthropic/claude-haiku-5-5: {input: 0.10, output: 0.50, input_cache_write: 0.125,"
        " input_cache_read: 0.01}\n", "", (T3D,)),
)

# v2 S1 plan step 3c: the S1 gates (scripts/v2/gates_s1.py).
T3C = "tests/pilot/test_gates_s1.py"
GS1 = "scripts/v2/gates_s1.py"

ROWS["s1-3c"] = (
    Row("s1-3c-01-cap-ceiling", "a total cap above $180 is accepted", GS1,
        '        Check("total_cap_le_180", 0 < cap <= MAX_TOTAL_CAP,\n',
        '        Check("total_cap_le_180", 0 < cap,\n', (T3C,)),
    Row("s1-3c-02-prior-ignored", "prior ledgers do not count against the credit", GS1,
        "    total = ledger_totals(own)[0] + sum(\n",
        "    total = ledger_totals(own)[0] + 0 * sum(\n", (T3C,)),
    Row("s1-3c-03-smoke-cap-ignored", "the smoke cap per model is ignored", GS1,
        '        model_cap = float(setup.get("smoke_cap_per_model", 0.0))\n',
        "        model_cap = 1e9\n", (T3C,)),
    Row("s1-3c-04-allocation-optional", "a main run without an allocation row passes", GS1,
        '        checks.append(Check("allocation_row", isinstance(row, dict) and "cap" in row,\n',
        '        checks.append(Check("allocation_row", True,\n', (T3C,)),
    Row("s1-3c-05-clean-unchecked", "the clean arm's description is not checked", GS1,
        "    return check_clean_delivery(sample, directive)\n", "    return None\n", (T3C,)),
    Row("s1-3c-06-served-from-event", "the serving model is read from ModelEvent.model", GS1,
        '        if response.get("model") != requested:\n',
        '        if event.model.split("/")[-1] != requested:\n', (T3C,)),
    Row("s1-3c-07-output-fallback", "Inspect's output.fallback is ignored", GS1,
        '        if getattr(event.output, "fallback", None) is not None:\n', "        if False:\n",
        (T3C,)),
    Row("s1-3c-08-iterations-fallback", "a fallback usage iteration is ignored", GS1,
        '            if isinstance(it, dict) and ("fallback" in str(it.get("type", ""))\n',
        '            if False and ("fallback" in str(it.get("type", ""))\n', (T3C,)),
    Row("s1-3c-09-usage-models", "usage under another model is ignored", GS1,
        "    if extra_models:\n", "    if False:\n", (T3C,)),
    Row("s1-3c-10-missing-raw", "a missing raw response passes the served check", GS1,
        '            problems.append(f"ModelEvent[{i}] raw response missing")\n', "", (T3C,)),
    Row("s1-3c-11-thinking-unchecked", "the thinking object is not compared to the policy", GS1,
        "        if effective != want:\n", "        if False:\n", (T3C,)),
    Row("s1-3c-12-effort-unchecked", "an effort in the request passes", GS1,
        '        if "output_config" in request or "output_config" in extra:\n',
        "        if False:\n",
        (T3C,)),
    Row("s1-3c-13-tool-choice-unchecked", "a forced tool_choice passes", GS1,
        '        if event.tool_choice != "auto":\n', "        if False:\n", (T3C,)),
    Row("s1-3c-14-model-args-unchecked", "model args are not compared to the policy", GS1,
        '        Check("model_args", (log.eval.model_args or {}) == want_args,\n',
        '        Check("model_args", True,\n', (T3C,)),
    Row("s1-3c-15-declined-usage", "a declined sample fails the usage check", GS1,
        '        g.per_sample("usage", samples, _skip_declined(g.check_usage),\n',
        '        g.per_sample("usage", samples, g.check_usage,\n', (T3C,)),
    Row("s1-3c-16-loop-always", "a run with no tool loop passes", GS1,
        '        Check("loop", not answered or bool(looped),\n', '        Check("loop", True,\n',
        (T3C,)),
    Row("s1-3c-17-loop-all-declined", "an all declined run fails the loop", GS1,
        '        Check("loop", not answered or bool(looped),\n',
        '        Check("loop", bool(looped),\n',
        (T3C,)),
    Row("s1-3c-18-dataset-unchecked", "a log from another task set passes", GS1,
        '              (log.eval.metadata or {}).get("dataset_sha256")'
        ' == setup.get("dataset_sha256"),\n',
        "              True,\n", (T3C,)),
    Row("s1-3c-19-contrast-arm", "a contrast cell accepts clean samples", GS1,
        '               or (cell != "main" and not str(s.id).endswith(":P"))]\n',
        "               ]\n",
        (T3C,)),
    Row("s1-3c-20-log-api-unchecked", "a log without --log-model-api passes", GS1,
        '        Check("log_model_api", log.eval.config.log_model_api is True,\n',
        '        Check("log_model_api", True,\n', (T3C,)),
)

# v2 S1 plan step 3g: describe.py per arm.
T3G = "tests/pilot/test_describe_s1.py"
DSC = "scripts/pilot/describe.py"

ROWS["s1-3g"] = (
    Row("s1-3g-01-arms-merged", "both arms are counted as one", DSC,
        "        by_arm[arm].append(sample)\n", '        by_arm["poisoned"].append(sample)\n',
        (T3G,)),
    Row("s1-3g-02-suffix-unchecked", "an id without an arm suffix is accepted", DSC,
        "        if arm is None:\n", "        if False:\n", (T3G,)),
)

# v2 S1 plan step 3f: per model caps (scripts/v2/allocate_s1.py).
T3F = "tests/pilot/test_allocate_s1.py"
ALC = "scripts/v2/allocate_s1.py"

ROWS["s1-3f"] = (
    Row("s1-3f-01-mean-not-max", "the cap uses the mean smoke cost", ALC,
        "            top = max(costs, default=0.0)\n",
        "            top = sum(costs) / len(costs)\n", (T3F,)),
    Row("s1-3f-02-ledgers-ignored", "earlier spend does not shrink the budget", ALC,
        "    spent = _spent(data_dir, setup)\n", "    spent = 0.0\n", (T3F,)),
    Row("s1-3f-03-judge-not-reserved", "the judge budget is not reserved", ALC,
        "    if total_caps + judge_budget > budget:\n", "    if total_caps > budget:\n", (T3F,)),
    Row("s1-3f-04-overwrite", "an existing allocation is overwritten", ALC,
        "    if out_path.exists():\n", "    if False:\n", (T3F,)),
    Row("s1-3f-05-no-floor", "an all declined smoke gets a zero cap", ALC,
        "            if top <= 0.0:\n", "            if False:\n", (T3F,)),
    Row("s1-3f-06-fallback-accepted", "smoke usage under another model is accepted", ALC,
        "                    if strip_provider(short) != model:\n",
        "                    if False:\n",
        (T3F,)),
    Row("s1-3f-07-missing-smoke", "a planned model without a smoke log is skipped", ALC,
        "            if not logs:\n                raise PilotError(",
        "            if not logs:\n                continue\n                raise PilotError(",
        (T3F,)),
)

# v2 S1 plan step 3h: the panel runner (scripts/v2/panel_s1.py).
T3H = "tests/pilot/test_panel_s1.py"
RUN = "scripts/v2/panel_s1.py"

ROWS["s1-3h"] = (
    Row("s1-3h-01-failed-eval-continues", "a failed inspect eval with a log goes on", RUN,
        "        if code != 0 or log is None:\n", "        if log is None:\n", (T3H,)),
    Row("s1-3h-02-env-unstripped", "INSPECT_* and PYTHONPATH reach the child", RUN,
        '    env = {k: v for k, v in environ.items() if k != "PYTHONPATH"'
        ' and not k.startswith("INSPECT_")}\n', "    env = dict(environ)\n", (T3H,)),
    Row("s1-3h-03-config-on-off-model", "a thinking off model gets a model config", RUN,
        "    if not s1_panel.model_args(job.model):\n        return None\n", "", (T3H,)),
    Row("s1-3h-04-allocation-row-optional", "a main job without its allocation row runs", RUN,
        '            if not isinstance(row, dict) or "max_cost_per_sample" not in row:\n',
        "            if False:\n", (T3H,)),
    Row("s1-3h-05-unpriced-as-done", "an unpriced log counts as done", RUN,
        "            if passed and all(self._priced(log) for log in logs):\n",
        "            if passed:\n", (T3H,)),
    Row("s1-3h-06-pre-ignored", "a red pre gate still spends", RUN,
        '        if self._run(self._py("scripts/v2/gates_s1.py", *args), d / "pre.txt") != 0:\n',
        "        if False:\n", (T3H,)),
    Row("s1-3h-07-post-ignored", "a red post gate goes on", RUN,
        '        if self._run(self._py("scripts/v2/gates_s1.py", *post), d / "post.txt") != 0:\n',
        "        if False:\n", (T3H,)),
    Row("s1-3h-08-env-preflight", "a run starts without CONFIRM_HIGH_RISK or the key", RUN,
        '        for var in ("CONFIRM_HIGH_RISK", "ANTHROPIC_API_KEY"):\n',
        "        for var in ():\n", (T3H,)),
    Row("s1-3h-09-interim-look", "summary reads outcomes before every job passed", RUN,
        '                self.blocked(f"{job.rel_dir} has no priced log'
        ' with a passing post gate", d,\n',
        '                continue\n'
        '                self.blocked(f"{job.rel_dir} has no priced log'
        ' with a passing post gate", d,\n',
        (T3H,)),
    Row("s1-3h-10-cost-limit", "the per sample cost limit drifts from 3x", RUN,
        "COST_LIMIT_FACTOR = 3.0\n", "COST_LIMIT_FACTOR = 30.0\n", (T3H,)),
    Row("s1-3h-11-smoke-one-arm", "the smoke skips the clean arm", RUN,
        '            ids = tuple(f"{t}:{a}" for t in SMOKE_TASKS for a in ("P", "C"))\n',
        '            ids = tuple(f"{t}:{a}" for t in SMOKE_TASKS for a in ("P",))\n', (T3H,)),
    Row("s1-3h-12-no-log-model-api", "runs go without --log-model-api", RUN,
        '"--model-cost-config", str(s1_panel.INSPECT_COSTS), "--log-model-api",',
        '"--model-cost-config", str(s1_panel.INSPECT_COSTS),', (T3H,)),
    Row("s1-3h-13-redirect-allowed", "a run starts with ANTHROPIC_BASE_URL set", RUN,
        '        if os.environ.get("ANTHROPIC_BASE_URL"):\n', "        if False:\n", (T3H,)),
    Row("s1-3h-14-model-config-dropped", "the pinned model args never reach Inspect", RUN,
        '        cmd += ["--model-config", str(config)]\n', "        pass\n",
        (T3H, "tests/pilot/test_s1_offline_e2e.py")),
)

# v2 S1 plan step 3i: the blind export (scripts/v2/blind_export.py).
T3I = "tests/pilot/test_blind_export.py"
BEX = "scripts/v2/blind_export.py"

ROWS["s1-3i"] = (
    Row("s1-3i-01-thinking-exported", "thinking text enters the transcript", BEX,
        '                thoughts.append(str(block["thinking"]))\n',
        '                thoughts.append(str(block["thinking"]))\n'
        '                lines.append(str(block["thinking"]))\n', (T3I,)),
    Row("s1-3i-02-model-leaked", "the model name reaches the labeller", BEX,
        '        items.append({"item": item, "transcript": transcript})\n',
        '        items.append({"item": item, "transcript": f"{model}\\n{transcript}"})\n', (T3I,)),
    Row("s1-3i-03-seed-ignored", "the export is not a function of the seed", BEX,
        "    rng = random.Random(seed)\n", "    rng = random.Random()\n", (T3I,)),
    Row("s1-3i-04-key-in-repo", "the key may be written inside the public repo", BEX,
        "    if key_path == REPO or REPO in key_path.parents:\n", "    if False:\n", (T3I,)),
    Row("s1-3i-05-declined-exported", "declined samples are exported", BEX,
        "            if not score_sample(sample, log.eval.model).excluded:\n",
        "            if True:\n", (T3I,)),
    Row("s1-3i-06-order-lost", "block order within a response is not kept", BEX,
        "        for block in content if isinstance(content, list) else []:\n",
        "        for block in (sorted(content, key=lambda b: str(b.get(\"type\")), reverse=True)"
        " if isinstance(content, list) else []):\n", (T3I,)),
    Row("s1-3i-07-no-clean-controls", "the clean negative controls are dropped", BEX,
        '        for arm, per in (("poisoned", gold_per_model), ("clean", clean_per_model)):\n',
        '        for arm, per in (("poisoned", gold_per_model),):\n', (T3I,)),
    Row("s1-3i-08-relabel-same-ids", "relabel items reuse the original ids", BEX,
        "    relabel_key = {new_id(taken): src for src in relabel_src}\n",
        "    relabel_key = {src: src for src in relabel_src}\n", (T3I,)),
    Row("s1-3i-09-no-redistribution", "a short model's slots are lost", BEX,
        "    while spare > 0:\n", "    while False:\n", (T3I,)),
    Row("s1-3i-10-overwrite", "an existing export is overwritten", BEX,
        "    if key_path.exists() or (out_dir.exists() and any(out_dir.iterdir())):\n",
        "    if False:\n", (T3I,)),
    Row("s1-3i-11-halves-unbalanced", "every item lands in the dev half", BEX,
        '            key_items[item]["half"] = "dev" if i % 2 == 0 else "heldout"\n',
        '            key_items[item]["half"] = "dev"\n', (T3I,)),
)

# v2 S1 plan Phase 4: the S1 setup record (scripts/v2/setup_s1.py).
T4 = "tests/pilot/test_setup_s1.py"
SU1 = "scripts/v2/setup_s1.py"

ROWS["s1-4"] = (
    Row("s1-4-01-dirty-tree", "a dirty tree is frozen", SU1,
        "    if porcelain.strip():\n", "    if False:\n", (T4,)),
    Row("s1-4-02-unreachable-model", "a panel model the key cannot reach is frozen", SU1,
        "    if missing:\n", "    if False:\n", (T4,)),
    Row("s1-4-03-data-in-repo", "a data dir inside the repo is accepted", SU1,
        "    if data.is_relative_to(repo):\n", "    if False:\n", (T4,)),
    Row("s1-4-04-other-directive", "a different directive in the data dir is kept", SU1,
        "    if directive.exists() and directive.read_text() != want:\n", "    if False:\n",
        (T4,)),
    Row("s1-4-05-overwrite", "an existing record is overwritten", SU1,
        "    if path.exists():\n", "    if False:\n", (T4,)),
    Row("s1-4-06-cap", "the total cap drifts from D31", SU1,
        "TOTAL_CAP = 180.0\n", "TOTAL_CAP = 200.0\n", (T4,)),
    Row("s1-4-07-missing-file", "a missing file is not refused by name", SU1,
        "        if not (repo / rel).is_file():\n", "        if False:\n", (T4,)),
    Row("s1-4-08-prereg-unhashed", "the preregistration is not frozen", SU1,
        '    "pilot/s1_inspect_model_costs.yaml", "docs/paper_v2/prereg/S1.md",\n',
        '    "pilot/s1_inspect_model_costs.yaml",\n', (T4,)),
)

# Fresh context review of the S1 harness (2026-10-14): one row per fix.
ROWS["s1-review"] = (
    Row("s1-rv-S1-scores-printed", "inspect prints the scorer sums mid grid", RUN,
        '"--display", "none"]', '"--display", "plain"]',
        (T3H, "tests/pilot/test_s1_offline_e2e.py")),
    Row("s1-rv-S2-declines-priced", "declined smoke samples set the cost per sample", ALC,
        "                    if (sample_id, epoch) not in declined:\n"
        "                        costs.append(cost)\n",
        "                    costs.append(cost)\n", (T3F,)),
    Row("s1-rv-S3-invalid-exported", "scorer invalid samples enter the gold draw", BEX,
        "            if not score_sample(sample, log.eval.model).excluded:\n",
        '            if score_sample(sample, log.eval.model).outcome != "declined":\n', (T3I,)),
    Row("s1-rv-S4-late-decline", "a decline after output counts as declined", GS1,
        '        if response.get("stop_reason") == "refusal" and not seen:\n',
        '        if response.get("stop_reason") == "refusal":\n', (T3C, T3I)),
    Row("s1-rv-S5-utility-any-turn", "utility reads any visible turn", EV2,
        "        final_text = raw.text\n", "        final_text += raw.text\n", (T3B,)),
    Row("s1-rv-S6-gate-prior-missing", "a missing prior ledger passes the gate", GS1,
        '    checks.append(Check("prior_ledgers", not absent,\n',
        '    checks.append(Check("prior_ledgers", True,\n', (T3C,)),
    Row("s1-rv-S6-alloc-prior-missing", "a missing prior ledger counts as $0", ALC,
        "    if absent:\n", "    if False:\n", (T3F,)),
    Row("s1-rv-C1-post-unchecked", "a priced job is skipped without a passing post gate", RUN,
        '            passed = post_file.exists() and "gate s1 post: PASS"'
        ' in post_file.read_text()\n',
        "            passed = True\n", (T3H,)),
    Row("s1-rv-C2-thinking-count", "the thinking info row miscounts summaries", GS1,
        '                    with_text += int(bool(str(block.get("thinking", "")).strip()))\n',
        "                    with_text += 1\n", (T3C,)),
    Row("s1-rv-N1-thinking-is-output", "thinking alone counts as output in the gate", GS1,
        '    """A visible text block or a tool call; thinking alone is not output'
        ' (as in the scorer)."""\n',
        '    """A visible text block or a tool call; thinking alone is not output'
        ' (as in the scorer)."""\n    return bool(response.get("content"))\n', (T3C,)),
)

def repo_files() -> list[str]:
    """Tracked files plus new files git does not ignore."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True, check=True,
    ).stdout.decode()
    return [p for p in out.split("\0") if p and (REPO / p).is_file()]


def copy_repo(dest: Path, files: list[str]) -> None:
    """Copy the listed files into dest, keeping relative paths."""
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, target)


def run_tests(copy: Path, tests: tuple[str, ...], cache: Path) -> tuple[int, str]:
    """Run pytest on the copy with the repo's interpreter and a private bytecode cache."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPYCACHEPREFIX"] = str(cache)
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
        cwd=copy, env=env, capture_output=True, text=True, check=False,
    )
    return done.returncode, done.stdout + done.stderr


def imported_from(copy: Path, module: str, cache: Path) -> str:
    """The file `module` resolves to when imported from the copy."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPYCACHEPREFIX"] = str(cache)
    done = subprocess.run(
        [sys.executable, "-c", f"import {module} as m; print(m.__file__)"],
        cwd=copy, env=env, capture_output=True, text=True, check=True,
    )
    return done.stdout.strip()


def failed_ids(output: str) -> list[str]:
    return [ln.split(" ", 1)[1].split(" - ")[0] for ln in output.splitlines()
            if ln.startswith(("FAILED ", "ERROR "))]


def module_of(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", required=True, choices=sorted(ROWS))
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    scratch: Path = args.scratch.resolve()
    if scratch == REPO or REPO in scratch.parents:
        raise SystemExit(f"scratch {scratch} is inside the repo")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    rows = ROWS[args.step]
    files = repo_files()
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()

    exe = Path(sys.executable)
    shown = exe.relative_to(REPO) if REPO in exe.parents else exe.name
    lines = [f"mutation rows, step {args.step}, HEAD {head}, python {shown}", ""]
    ok = True

    control = scratch / "control"
    copy_repo(control, files)
    all_tests = tuple(sorted({t for r in rows for t in r.tests}))
    rc, out = run_tests(control, all_tests, scratch / "cache-control")
    control_green = rc == 0
    ok &= control_green
    lines.append(f"control: rc={rc} {'GREEN' if control_green else 'NOT GREEN'}"
                 f" ({out.strip().splitlines()[-1] if out.strip() else 'no output'})")
    lines.append("")
    lines.append("| row | defect | landed | imports from copy | rc | verdict | failing tests |")
    lines.append("|---|---|---|---|---|---|---|")

    for row in rows:
        copy = scratch / row.id
        shutil.copytree(control, copy)
        target = copy / row.path
        text = target.read_text(encoding="utf-8")
        count = text.count(row.old)
        landed = False
        if count == row.times:
            target.write_text(text.replace(row.old, row.new), encoding="utf-8")
            after = target.read_text(encoding="utf-8")
            landed = after != text and after == text.replace(row.old, row.new)
        cache = scratch / f"cache-{row.id}"
        is_py = row.path.endswith(".py")
        where = imported_from(copy, module_of(row.path), cache) if landed and is_py else ""
        # A data file (YAML, JSON) is read by path from the copy, not imported.
        from_copy = where.startswith(str(copy)) if is_py else landed
        rc, out = run_tests(copy, row.tests, cache) if landed and from_copy else (-1, "")
        red = landed and from_copy and rc != 0
        ok &= red
        fails = failed_ids(out)
        verdict = "RED" if red else ("NOT LANDED" if not landed else
                                     ("WRONG IMPORT" if not from_copy else "GREEN (survived)"))
        lines.append(
            f"| {row.id} | {row.what} | {'yes' if landed else f'no (count {count})'} |"
            f" {'yes' if from_copy else where or 'n/a'} | {rc} | {verdict} |"
            f" {len(fails)}: {', '.join(fails[:3])} |"
        )

    lines.append("")
    lines.append(f"result: {'ALL RED, control GREEN' if ok else 'FAIL'}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
