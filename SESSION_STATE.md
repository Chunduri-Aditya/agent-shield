# Agent Shield — session state (parallel work)

**Purpose.** This file is the **repo-visible** handoff layer for anyone touching the
project at the same time (multiple Cursor chats, another machine, a future
collaborator). It is **not** a replacement for [`AGENT_SHIELD_TODO.md`](AGENT_SHIELD_TODO.md)
(what must ship) or for [`CONTEXT.md`](CONTEXT.md) (local only, gitignored: private
notes, keys, full narrative). **Combine the two:** put durable private detail in
`CONTEXT.md`, put **coordination facts** here so parallel sessions stay aligned.

**Update before you end a session** if you changed code, own a file, or would
confuse the next person. Stale rows are worse than empty rows.

---

## Last updated

- **Date:** 2026-05-05
- **By:** local session — eval scorer tests added

---

## Active workstreams

Use short labels (A, B, …) or branch names. One row per parallel track.

| Workstream | Focus / task | Branch or WIP | Contact / note |
|------------|----------------|---------------|----------------|
| A | Eval script pytest coverage | (current branch) | `tests/test_eval_scorers.py` added; focused run passed |
| B | — | — | (open slot for parallel session) |

---

## Touching / do not conflict

Files or areas **currently being edited**; others should **wait** or **coordinate**
before changing the same paths.

| Path or area | Owner workstream | Note |
|--------------|------------------|------|
| `tests/test_eval_scorers.py` | A | New focused scorer and dataset wiring tests |
| `AGENT_SHIELD_TODO.md` | A | Sections 5/6 now include first seeded Anthropic result checkpoints |
| `RESULTS.md` | A | Ollama `llama3.1:8b` rows added for `inputs`, `psych`, and `tools` |
| `WEEKLY.md` | A | Week 1 retrospective populated; next retro should be Week 2 |
| `Makefile`, `.env.example`, `docs/free_agent_resources.md`, `scripts/free_agent_status.py` | A | Free backend setup in flight |

---

## Blockers (shared)

| Blocker | Affects | Since |
|---------|---------|-------|
| Hosted provider keys missing | Second free backend sweep | 2026-05-05 |

---

## Next handoff (for the next session)

- [ ] Pick next module to scaffold per `AGENT_SHIELD_TODO.md` (`memory/` and `exfil/` are the lightest scaffolds)
- [ ] Pick whether Week 2 retro should be backfilled before new module scaffolding
- [ ] Add one hosted free provider key to `.env`, or start LM Studio / vLLM
- [ ] Run a second free backend sweep and paste rows into `RESULTS.md`
- [ ] `THREAT_MODEL.md` v2 after the first real cross-model numbers land

---

## Session log (newest first)

Keep entries to one line when possible. Trim old entries when this section gets long.

| When (date) | What changed |
|---------------|--------------|
| 2026-05-05 | Added `tests/test_eval_scorers.py`; `uv run pytest tests/test_eval_scorers.py -q` passed with 10 tests |
| 2026-05-05 | Added strict agent operating rules: resource approval before access, `docs/agent_resource_log.md`, HTTPS only, safe test workflow, no GUI auto-open, and `docs/session_handoff.md` |
| 2026-05-05 | Ran Ollama `llama3.1:8b` across `inputs`, `psych`, and `tools`; rows added to `RESULTS.md` |
| 2026-05-05 | Free backend status checks now load `.env` and detect Ollama, LM Studio, and vLLM local servers |
| 2026-05-05 | Added free agent backend scaffold: provider resource doc, env placeholders, status script, Make targets |
| 2026-05-05 | Populated Week 1 retrospective in `WEEKLY.md` |
| 2026-05-05 | Seeded `make eval-tools` and `make eval-psych`; populated `RESULTS.md`; Makefile now passes `SEED` to Inspect |
| 2026-05-04 | Markdown audit: stripped Day/Phase anchors from BACKLOG, THREAT_MODEL, MAPPINGS, reading_notes; refreshed README current status; populated this file |
| 2026-05-03 | `psych/` scaffold (PS-01..PS-06) + `evals/psych.py` + Makefile targets; RESULTS.md skeleton for psych; tools RESULTS marked pending |
| 2026-05-03 | Governance: `CLAUDE.md` + `.cursor/rules/agent-shield.mdc` pre-read order (CONTEXT → SESSION_STATE → TODO → CLAUDE); TIMELINES.md reduced to a pointer |
| (older) | Template created |
