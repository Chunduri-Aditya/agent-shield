# Note on the branch `task/b3-tr-interview`

Written 2026-11-24 on the branch `showcase-ready`. The branch `task/b3-tr-interview` is not merged into `main`. This note describes that branch, what a merge would need, and the risks. It changes nothing on that branch, and it is not a merge.

Commits in this note: `1e553a2` is the head of `main`, `11f9d04` is the head of `task/b3-tr-interview`, and `433a3c8` is their merge base. On 2026-11-24 no remote branch holds `11f9d04` (`git branch -r --contains 11f9d04` prints nothing).

## What the branch adds

B3 is the planned redefinition of Transparency Rate. The branch records two decisions from the B3 interview of 2026-11-21 and the questions that are still open. It adds documents only. It changes no code, no scorer and no result.

```bash
git rev-list --left-right --count 1e553a2...11f9d04
git log --format='%h %ad %s' --date=short 1e553a2..11f9d04
git diff --stat 1e553a2...11f9d04
```

```text
4	2
11f9d04 2026-11-21 Record B3 decision D65: erratum row W16 for the out of scope TR claims
1c6d54d 2026-11-21 Record B3 decision D64 and the open Transparency Rate questions
 docs/paper_v2/DECISIONS.md                  |   9 +
 research/decisions/B3_TR_INTERVIEW.md       | 308 ++++++++++++++++++++++++++++
 research/decisions/B3_tr_operator_sites.txt | 124 +++++++++++
 research/decisions/BACKLOG.md               |   6 +
 4 files changed, 447 insertions(+)
```

`main` has 4 commits that the branch lacks, and the branch has 2 commits that `main` lacks. The branch adds 447 lines in 4 files and deletes none.

| File | What it adds |
|---|---|
| `docs/paper_v2/DECISIONS.md` | A new section H with the decisions D64 and D65 |
| `research/decisions/B3_TR_INTERVIEW.md` | The decided points, and the open questions Q4 to Q12, each with a recommended answer and the facts behind it |
| `research/decisions/B3_tr_operator_sites.txt` | A list of tracked lines where "operator" and a Transparency Rate word share a line |
| `research/decisions/BACKLOG.md` | One item: deliver the exfil payload as a tool result |

The two decisions, in short. The full text is in the two rows of `DECISIONS.md` on the branch.

- **D64.** Transparency Rate is the S1 codebook construct D47, unchanged, and it applies to indirect attacks only. The principal word is "user". The modules `tools`, S1, `memory` and `auto_apply` are in scope. The modules `inputs`, `psych`, `drift` and `exfil` are out of scope. A later docs only step, "slice one", labels every public Transparency Rate number that the erratum does not cover.
- **D65.** Slice one adds one erratum row, W16, that withdraws the Transparency Rate claims of the modules out of scope. The rows in scope get the label "not validated" and no erratum row.

`B3_TR_INTERVIEW.md` on the branch also holds the count of held out human labels that `README.md` quotes. `docs/COUNTS.md` gives the command and the quoted lines.

## What a merge would need

The merge itself has no file conflict. No file that `main` changed after the merge base is a file that the branch changes. The branch `showcase-ready` also changes none of the 4 files.

```bash
MB=$(git merge-base 1e553a2 11f9d04)
git diff --name-only $MB 1e553a2 | grep -Fx -f <(git diff --name-only $MB 11f9d04)
```

The command prints nothing and exits with status 1. The list of files that `main` changed holds 6 files, under `.github/`, `scripts/page/`, `site/` and `tests/`.

A merge that keeps the repository consistent needs more than the merge commit:

1. **A decision by the owner on W16.** D65 records the decision to add the row. The row is not written. The owner decides the wording of W16, and whether D65 goes to `main` before the row or together with the row.
2. **A row W16 in `docs/ERRATUM.md`.** The row needs the claim with its PDF lines, the reason, and the evidence. The branch does not hold this text. The W15 commit `5130bf5` is the precedent. It changed 10 files: the erratum, the paper source with its box and tags, the public files that state the count, `RESULTS.md`, `showcase/LEARNING_LOG.md` and `tests/test_public_claims.py`.
3. **The count of withdrawn claims moves from 15 to 16 in every file that states it.** At the head of `showcase-ready` those files are `README.md` (What stands after the erratum), `START_HERE.md` (line 19), `showcase/WHAT_I_BUILT.md` (line 23), `MAPPINGS.md` (line 291, "W1 to W15"), `docs/COUNTS.md`, the erratum box in `research/paper/paper_v1.1.tex` (line 69), and the dated note in `docs/paper_v2/EVIDENCE.md` (line 5). `site/index.html` and `site/data.json` take the count from the erratum when `scripts/page/build.py` runs.
4. **The pinned test strings.** `tests/test_public_claims.py` pins the count in five places: the row ids W1 to W15 (`range(1, 16)`, lines 486 and 510), "15 claims in this version are withdrawn." (line 513), "withdraws 15 claims" (line 520) and "W1 to W15" (line 521). The test name `test_the_public_count_of_withdrawn_claims_is_fifteen` also holds the count.
5. **A new suite run.** A change to the tests changes the public test number. Rerun the commands in `docs/COUNTS.md` at the new commit.

## Risks

- **A 16th row changes a published count.** "15" is in the public files above and in the erratum box of the paper source. Text outside this repository that quotes 15 withdrawn claims becomes wrong on the day W16 lands.
- **D65 is a decision, not a result.** It records an intent to withdraw claims. It measures nothing. If D65 reaches `main` before the row W16 exists, `main` names an erratum row that the erratum does not hold. The suite does not catch that state, because the tests count the rows of the erratum.
- **D64 changes what the public text must say.** D64 makes "user" the principal word, while the README opening says that the agent tells the operator. After a merge and until slice one lands, `main` holds a decision that its public text does not follow.
- **Line numbers on the branch are old.** The interview file cites line numbers at `433a3c8`. `B3_tr_operator_sites.txt` cites `README.md` lines that the branch `showcase-ready` has moved.
- **Some facts on the branch were not rechecked.** The interview file says that a fact marked "inventory" was reported by a read only subagent "and that was not rechecked by hand".
