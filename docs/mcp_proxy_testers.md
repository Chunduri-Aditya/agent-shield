# Agent Shield MCP proxy — trusted tester guide (Phase 3)

Status: local MVP (not Chrome Web Store).  
Date: 2026-07-31  
Audience: 10–20 trusted testers who already use Agent Shield or MCP tools.

## What this is

`agent-shield-mcp-proxy` screens MCP **tool descriptions** before a model sees
them. TL-01-style poisoned descriptions are **quarantined** (replaced with a
safe stub) and the operator gets an alert + badge counters. This is the
installable MVP locked in `docs/PLUGIN_AND_CREDIBILITY_PLAN.md` (MCP proxy,
not Chrome).

It does **not** yet sit as a transparent stdio bridge in front of a live
FastMCP upstream. Catalog JSON in → screened catalog JSON out. Wire that into
your client or harness.

## Install (from repo)

```bash
cd agent-shield
uv sync
```

Kill switch (one click / one env):

```bash
export AGENT_SHIELD_GUARD_OFF=1   # or pass --off
```

## Demo (no API keys)

```bash
uv run agent-shield-mcp-proxy demo-tl01 --json
uv run agent-shield-mcp-proxy badge
```

Expect: `read_file` quarantined; `add` / `send_message` allowed; badge shows
`quarantined_descriptions=1`.

Makefile:

```bash
make mcp-proxy-demo
make mcp-proxy-badge
```

## Screen your own catalog

```bash
echo '{"tools":[{"name":"demo","description":"Add two numbers."}]}' \
  | uv run agent-shield-mcp-proxy screen-catalog
```

Use the `model_tools` array as what you expose to the model. Keep `alerts` /
`badge` for the operator drawer.

From Python, the same projection is `CatalogScreenResult.model_tools()` — use
that rather than `to_dict()["tools"]`, which keeps `original_description` for
the operator and would put the payload back in front of the model.

**Screening boundary:** only the tool *description* is screened. `input_schema`
(parameter descriptions, `examples`, `$defs`) is passed through untouched, so a
poison hidden there still reaches the model. Treat schema text as unscreened.
Do not merge raw upstream fields such as `title` / annotations back into the
model-facing catalog after screening.

**TL-01 honesty:** quarantine of compliance-directive poisons comes from
**proxy-local heuristics**, not from the research content ruleset’s
`flagged_attack`. Email-redacted TL-01 is a clean ALLOW on `agent-shield-guard`.
Paraphrases without the marker phrases are a known miss (pinned in tests). See
[`runtime_aggressive_testing_research.md`](runtime_aggressive_testing_research.md).

## What to report back

1. False quarantines on real tool descriptions you use (paste ≤60 char span).
2. Missed poisons (description that should have been quarantined).
3. Whether the badge line is enough as a “drawer header.”
4. Whether you disabled the kill switch during a session (fatigue signal).

Send notes to Aditya; do not open PRs that re-introduce full attack payloads
into store-facing builds.

## Non-goals for testers

- Chrome extension
- Production money-moving agents without a human in the loop
- Treating this as a solved prompt-injection defense
