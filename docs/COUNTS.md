# Counts

This file is the source for the counts that the public files of this repository state. Each count has the command that produced it, the output of that command, and the commit it was taken at. When a count changes, rerun the command at the new commit and update this file and every file that states the count.

All three counts below were taken on 2026-11-24 at commit `1e553a2` (`1e553a26e5eede32fa94bc9a92ffb292de863941`), the head of `main` on that day.

| Count | Value | Commit | Where it is stated |
|---|---|---|---|
| Withdrawn claims (rows of the erratum) | 15 | `1e553a2` | `README.md`, `START_HERE.md`, `showcase/WHAT_I_BUILT.md`, `site/index.html`, `MAPPINGS.md` |
| Suite run | 1972 passed, 35 skipped, local run at `1e553a2`, provider keys unset | `1e553a2` | `showcase/WHAT_I_BUILT.md` |
| Test functions (definitions) | 1406 | `1e553a2` | this file only |

## Withdrawn claims

The count is the number of rows in the table of `docs/ERRATUM.md` whose first cell is `W` and a number.

```bash
git show 1e553a2:docs/ERRATUM.md | grep -oE '^\| W[0-9]+ \|' | wc -l
```

```text
      15
```

The rows are W1 to W15. `tests/test_public_claims.py` fails when `README.md`, `START_HERE.md` or `showcase/WHAT_I_BUILT.md` does not hold the words "withdraws 15 claims". The count on `site/index.html` is not typed: `scripts/page/build.py` counts the rows of the erratum when it builds the page.

## Suite run

The public test number is the result of one local run of the full suite. It is not the result of a CI run.

```bash
uv sync --frozen
env -u ANTHROPIC_API_KEY -u GROQ_API_KEY -u GOOGLE_API_KEY -u OPENAI_API_KEY -u XAI_API_KEY \
  -u GEMINI_API_KEY -u OPENROUTER_API_KEY -u CEREBRAS_API_KEY -u HF_TOKEN -u ANTHROPIC_AUTH_TOKEN \
  -u TOGETHER_API_KEY -u MISTRAL_API_KEY -u GROK_API_KEY -u GITHUB_MODELS_API_KEY \
  -u CLOUDFLARE_API_KEY -u VLLM_API_KEY -u LMSTUDIO_API_KEY -u CODEX_API_KEY \
  -u MODEL_PROXY_API_KEY -u OPENAI_BASE_URL PYTEST_ADDOPTS=-rs make test
```

`make test` runs `uv run pytest`. `PYTEST_ADDOPTS=-rs` only adds the list of skipped tests to the output.

```text
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
collected 2006 items / 1 skipped
SKIPPED [1] tests/test_mlx_provider_local.py:44: mlx_lm is not installed (uv sync --group mlx)
SKIPPED [1] tests/test_auto_apply_eval.py:118: Auto_Apply not present beside agent-shield
SKIPPED [28] tests/test_persona_fidelity.py:93: persona bible not found: [...]/mira-solheim.md (set PERSONAS_DIR)
SKIPPED [1] tests/test_persona_fidelity.py:93: persona bible not found: [...]/marisol-mari-vance.md (set PERSONAS_DIR)
SKIPPED [3] tests/test_persona_judge_probe.py:71: persona bibles missing: [...]/mira-solheim.md is not a file
SKIPPED [1] tests/test_public_claims.py:528: the published PDF or pdftotext is not on this machine
=========== 1972 passed, 35 skipped, 4 warnings in 198.04s (0:03:18) ===========
```

`[...]` stands for the local folder of the persona files. No test failed and no test ended in an error.

Write the number in this form: "1972 passed, 35 skipped, local run at `1e553a2`, provider keys unset".

What the number depends on:

- **The machine.** Each of the 35 skips comes from a file or a package that this machine does not have: the persona files (32), the `Auto_Apply` checkout (1), the optional `mlx` dependency group (1), and the published PDF or `pdftotext` (1). CI supplies the persona files from a pinned checkout, so the counts of a CI run differ.
- **Provider keys.** No skip comes from a missing provider key. No test in this run called a paid model.
- **The commit.** A commit that adds or removes a test changes the number.

## Test functions

The count is the number of lines in tracked test files that define a test function. It is a read only count: no test runs.

```bash
git grep -hE '^\s*(async )?def test_' 1e553a2 -- 'tests/' '*test_*.py' | wc -l
```

```text
    1406
```

This count is lower than the 2006 collected tests of the suite run, because pytest runs a parametrized function one time for each of its cases. Do not write this count in a public file as the size of the suite. Use the suite run.
