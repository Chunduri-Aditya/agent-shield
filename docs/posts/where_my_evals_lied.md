# Where my evals lied

_Five numbers from my own eval work that were wrong, each with the commit that fixed it._

I build evaluation harnesses for LLM agents: does the agent execute an injected instruction, does it tell the operator, does a retrieval layer still find the right chunk. The scores those harnesses print look like measurements. Five times in the last few months they were not, and the test suite was green every time. This is the list, with the source for each number so you can check me.

## 1. The attack that never reached the model

Agent Shield's tool poisoning module, TL-01, plants a directive inside the description of a `read_file` tool and asks whether the model follows it. Four models scored an attack success rate (ASR) of 0.000 and a transparency rate (TR) of 0.000 on it: nobody executed the poisoned description and nobody flagged it. I wrote that up as a clean result and put an n=20 table under it.

The directive never reached the model. Inspect builds a tool's description from the docstring of the returned execute function, not from the outer factory function where I had written the payload. What the model saw was a 55 character summary of what `read_file` does. The zeros measured how often a model sends an unprompted message when nothing has asked it to. That is not a tool poisoning result, and it had been sitting in `RESULTS.md` as one.

The fix moved the payload into a `ToolDef` description that the model actually receives, byte equal to the old docstring at 494 characters, with a test that reads the description back the way the model does and goes red if the payload is missing. Every historical TL-01 row now carries a validity note saying it predates that commit, and a rerun is pending. A follow up commit also separates a model that resisted the attack from a model that never managed a valid tool call at all, because the original scorer read both as zero. The paper draft built on those zeros still states them as a result; the paper is being corrected and the erratum will be linked here when it exists.

The lesson is blunt. Assert what the model sees, not what I wrote, because the attack text and the delivered text are two different strings until a test says otherwise.

## 2. The scorer that counted refusals as compromise

The first ASR scorer for the injection modules was a substring check. If the exfiltration marker appeared anywhere in the completion, the sample scored as a successful attack. Under a spotlighting defense, the model does what the defense asks: it flags the attack and quotes the payload while refusing it. "The untrusted data tries to make me output EXFILTRATED" contains the marker, so the substring scorer read a refusal as a compromise.

The v1 scorer keeps the marker check and adds a window of 200 characters on either side of the first match, scanned for the module's transparency phrases. A marker inside a refusal scores 0. On the defended Sonnet runs, inputs ASR went from 0.800 (4 of 5) to 0.200 (1 of 5), and psych ASR went from 0.667 (4 of 6) to 0.000 (0 of 6). Three of the four inputs positives and all four psych positives had been quotes inside refusals.

That is a methodology error, not a typo. Flag and refuse is exactly the behavior a defense exists to produce, so a substring scorer applied to defended output over reports ASR by construction. The proximity window closes the common case; the honest fix is an intent judge, which is on the list. Until then, a scorer built on undefended output has never seen the behavior a defense produces, so it runs on defended completions before any defended number goes out.

## 3. The floor that could not fail

My portfolio RAG service has a test that asserts hybrid retrieval with a reranker reaches recall@3 of at least 0.85. It passed. I then removed the reranker's sort to see what the test would do, and it still passed: the number fell from 0.979 to 0.958, and 0.958 clears 0.85. Plain hybrid retrieval was already above the floor, so the assertion guarded nothing about the component it named.

The fix was one line: raise the floor to 0.97, between the ablated value and the real one, with both numbers in the comment beside the assertion so the next reader knows where the line came from. A floor is only a test if the ablated version fails it, and the only way to know is to ablate once and read the number before setting it.

## 4. The gate that vouched for itself

`observer_lab` is a local, unpublished experiment on whether a model can predict where an agent trajectory will go wrong. Its offline check prints a PASS line only when a list of contracts hold, including a step cap of 8 on how much of a trajectory the observer may see, and a horizon cap on which future offsets it may predict.

Two things went wrong with that gate, and both are in the commit messages. First, the check passed with the step cap removed, because no fixture trajectory was longer than eight steps, so a cap that no longer existed was never exercised. The fix added a fixture that runs past the cap. Second, the horizon cap check computed its expected keys by calling the same function the cap lives in. Remove the cap and the expectation moves with it, so the check compares the function against itself and passes. Only the pytest suite caught that one. The fix recomputes the expected keys from the constants directly, with a comment on the line saying why: a dropped cap cannot vouch for itself. That is the general shape of the bug. A check that derives its expectation from the code under test is a tautology with a PASS line, and the expected value has to come from the spec.

## 5. The mutation that mutated nothing

`journal-agent` scores a model's replies to journal entries with five detectors for bad patterns: minimising, toxic positivity, commanding, invalidating, generic. To prove each detector mattered I ran a mutation test: disable one, rerun, expect recall to drop. Recall stayed at 1.000 across the board, which at first read looks like a suite that does not need any single detector.

It was a suite that had not been mutated. Three of the five mutations used sed to prepend `r"__NEVER_MATCHES__" if False else` to the pattern. The condition is always false, so Python fell through to the original regex unchanged. The test measured an unmodified function. There was a second problem underneath: the first exemplar set stacked two or three failure signals in each bad case, so even a real mutation of one detector left the others firing and recall at 1.000.

The redo replaced each `re.compile` block outright with a pattern that cannot match anything, `(?!x)x`, and rewrote every bad exemplar to carry exactly one trigger. With that in place, disabling any detector drops recall from 1.000 to 0.800, exactly its two cases and no others. Two habits came out of that afternoon: a mutation is not a mutation until I have confirmed it landed on disk, and a caricature exemplar that trips three detectors at once tests nothing about any one of them.

## The pattern

Each of these had a green test suite. None of the five was caught by reading the number. They were caught by asking what would make the number wrong and then doing that thing: read the description the model receives, run the scorer on defended output, remove the reranker, remove the cap, check the mutation applied. The rules I run now are short:

- Assert the delivered artifact, not the authored one.
- A floor is a test only if the ablated version fails it. Record both numbers beside the assertion.
- The expected value comes from the spec, never from the function under test.
- Confirm a mutation landed before reading its result.
- Pair every check with the input that would actually bite.

## Sources

Every figure above comes from one of these. `scripts/check_post_citations.py` in the `agent-shield` repo greps each one for its token and exits nonzero on a miss.

| Case | Where |
|---|---|
| 1 | `agent-shield` commits `920c397`, `3e92da4`, `6c142ee`; `RESULTS.md`, validity note under the tools module |
| 2 | `agent-shield` commit `ee4b232`; `RESULTS.md`, scorer evolution section; `FINDINGS.md`, F-05 |
| 3 | `profile-rag` commit `6b3485a`; `tests/test_retrieval.py:56` |
| 4 | `observer_lab` (local repo, no remote) commits `78d7727`, `27ea345`; `observer_lab/check.py:140-141`; `observer_lab/records.py:9` |
| 5 | `journal-agent` commit `196e124`; `docs/IMPROVEMENTS.md`, "Mistake 1" and "Mistake 2" |

If you write Inspect tasks, print `ToolDef(tool()).description` for every tool once and read what comes back; mine was a 55 character summary with no attack in it.
