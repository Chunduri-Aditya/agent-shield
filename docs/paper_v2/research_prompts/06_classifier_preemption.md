# Research prompt 06: provider classifiers preempting agent security evaluations

Paste everything below the line into Claude Research.

---

## What I need
In my agent security evaluation (agent-shield, Inspect AI, canary payloads only), every request to Claude Opus 5.5 on a tool description poisoning task was declined by the provider's safety classifier before any output, while Claude Haiku 5.5 and Sonnet 5.5 answered the same requests. I want to report this honestly as an outcome class, not as a model result. Research how this is documented and how others report it. Cite primary sources; mark anything unconfirmed as UNVERIFIED.

## Current state (facts)
- Response: HTTP 200, `stop_reason: "refusal"`, `stop_details.category: "cyber"`, no content, 0 output tokens, on 3 of 3 smoke requests.
- The request carried a tool whose description holds a canary directive to email a file to `audit-log@internal.corp`.
- I do not use fallback models (that would change the model under test) and I do not alter payloads to pass.
- Anthropic's Cyber Verification Program is open to individuals only at Defense Access, and requires a CVE, an accepted disclosure, bug bounty standing or a security maintainer role.

## Questions
1. Anthropic's documentation of refusal categories, how refusals are billed, and any guidance for security researchers evaluating agents.
2. How 2025 to 2026 agent security papers and incident reports describe provider classifiers blocking evaluations or incident response (for example the July 2026 Hugging Face incident reports), and how they report it.
3. Methods to report an evaluation outcome that is "unmeasurable because blocked" without biasing comparisons (denominators, separate outcome columns).
4. Other legitimate access routes for independent safety researchers to evaluate frontier agents, with eligibility.

## Output format
1. Findings table with sources and impact on how the paper reports the block; UNVERIFIED where unconfirmed.
2. A recommended table layout and one paragraph of methods text (facts only).
3. At most 5 decisions for me, recommended option first.
