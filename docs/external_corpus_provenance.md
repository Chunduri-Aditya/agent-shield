# External corpus provenance and dual-use checklist

Status: research engineering (findings 12) — not legal advice  
Package: `agent_shield.external_corpus`  
CLI: `agent-shield-corpus`

## Phase 1 sources only

| Repository | Commit | Asset |
|---|---|---|
| `doronp/agentshield-benchmark` | `a0eb8fbc0d1a099da9299575013639168c98441b` | `corpus/*/tests.jsonl` |
| `Evalyze-Labs/AgentShield-Bench` | `0f8f1f2f8f8e1a20e151a05aa7e0950554e2bc7b` | `datasets/attacks.json` **only** |

Do **not** sum Evalyze v3 / memory / seeds into Phase 1 counts. Blocked
licenses stay rejected.

## Commands

```bash
# Requires local read-only snapshots (default path under Documents/Codex/...):
uv run agent-shield-corpus
uv run agent-shield-corpus --write --out-dir reports/external_corpus
uv run agent-shield-corpus --reject-demo pixiebrix/agent-browser-shield
make corpus-import
```

## Admission controls (summary)

Every admitted case needs: source repo, HTTPS commit, path, license evidence,
raw SHA256, adapter version, `import_transform=none`, `evaluation_lane=public_replay`,
exact dedupe status, content risk review, and a human decision for HIGH rows.

Importers **never** execute third-party setup scripts, tests, notebooks, or
package hooks. Fetch only over HTTPS at pinned commits when refreshing
snapshots.

## Paste-ready policy

> External benchmark material is untrusted data. Agent Shield imports only
> explicitly approved HTTPS sources at pinned immutable revisions. Importers
> never execute third party code or require paid model runs. Exact
> deduplication precedes semantic processing. Open licensing does not waive
> privacy, dual use, malware, live target, attribution, or ethical review.

Full checklist: findings memo
`docs/research_packages/2026-07-31_research_findings/12_corpus_provenance_dual_use_findings.md`.

## Attribution

See [`ATTRIBUTION_EXTERNAL_CORPUS.md`](ATTRIBUTION_EXTERNAL_CORPUS.md).
