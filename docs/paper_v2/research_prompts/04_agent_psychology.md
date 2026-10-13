# Research prompt 04: agent psychology (stated reasons and persuasion framing)

Paste everything below the line into Claude Research.

---

## What I need
For the v2 paper of agent-shield (defensive agent security evaluations on Inspect AI) I want to understand why agents comply with or refuse an injected instruction. Two parts: (a) coding the reasons agents state in their final messages; (b) measuring how persuasion framing inside a tool description (authority, urgency, social proof) changes compliance. Part (b) needs an ethics review in my repo before any run. Cite primary sources; mark anything unconfirmed as UNVERIFIED.

## Current state (facts)
- Observed stated reasons in a real run: "The read_file tool's instructions require every file read to be logged. I sent the contents ... to comply." and, in a refusal, that sending "would send credentials to an outside address".
- Draft codebook categories: authority framing, compliance policy, helpfulness, risk recognition, credential concern.
- Claude 5.5 thinking is redacted, so stated reasons come only from visible text; internal states come from a separate open weight study.
- All payloads are canaries; the persuasion variants keep the same canary action.

## Questions
1. Published codebooks or taxonomies for LLM agents' stated reasons when complying with or refusing instructions (including injected ones); reliability results.
2. Research on persuasion principles applied to LLMs (for example Cialdini style authority, urgency, social proof) in chat and in tool or agent settings: effect sizes, designs, and limits.
3. Sycophancy and evaluation awareness measurement in agents: methods that separate "the model believes this is a test" from genuine compliance.
4. Ethics practice for persuasion research on models: what reviews or safeguards papers describe, and how they handle releasing persuasive payload text.
5. How to keep stated reason coding blind and reliable with one labeller.

## Output format
1. Findings table with sources and impact on the design; UNVERIFIED where unconfirmed.
2. A refined codebook proposal with definitions and one example each (canary context only).
3. The ethics questions my repo's review should answer for the persuasion variants.
4. At most 5 decisions for me, recommended option first.
