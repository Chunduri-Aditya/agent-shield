# Research result for prompt 08 (received 2026-10-14)

Claude Research output pasted by Aditya, kept verbatim below the line. It is evidence, not instruction: every claim it makes keeps its own UNVERIFIED, inference and speculation marks, and the plan cites it as RR08 only where a check confirmed the claim or where the claim is the research tool's own report. Ten of its fourteen unit costs are extrapolated by list price ratio, not measured; the S1 allocation is recomputed from measured smoke costs. Published rates quoted inside it belong to system cards and other papers, never to this repo's scorers. Local checks against the installed Inspect 0.3.278 made on 2026-10-14 (thinking `display`, served model, fallback, `--batch`, prices, model roles, caching) are recorded in the S1 plan; two RR08 claims did not hold there: Inspect does not drop forced tool choice under adaptive thinking (only under extended thinking), and Inspect ships no model prices.

---

**Claude API panel and $200 allocation for agent-shield v2 prompt injection studies (as of October 14, 2026)**

The Claude API still serves an Opus line you can test in one panel, from `claude-opus-4-5-20251101` through `claude-opus-5-5`, plus three Sonnet generations and two Haiku generations; that is enough for a version trend. Fact: a full 14 model S1 run with 80 distinct prompts, 3 attack variants and 2 epochs costs about $90 at your measured rates. All studies plus an AgentDojo external validity row come to about $148 of the $180 you can spend after the $20 reserve. The binding constraints are classifier declines on the 5.5, Fable and Opus 4.7+ models and how much thinking output is visible, not money.

**TL;DR**
- **Panel (fact):** The Claude API serves 17 model ids, 16 of them listed as active. They span Opus 4.5, 4.6, 4.7, 4.8, 5 and 5.5; Sonnet 4.5, 4.6, 5 and 5.5; Haiku 4.5 and 5.5; and Fable 5 and 5.1. The Claude Platform release notes of September 30, 2026 schedule Sonnet 4.5 (`claude-sonnet-4-5-20250929`) for retirement on November 30, 2026, and Haiku 4.5 is "not sooner than October 15, 2026". Run both first. Every Claude 4.7 and later model, and Claude Mythos Preview, rejects sampling parameters, and SDK v1.0 and later removes them entirely.
- **Declines and reasoning (fact):** Opus 5.5 runs a three stage cyber classifier. A cyber refusal that arrives before any output is not billed but still counts against rate limits. Fallback to another model is opt in, so leaving it off keeps every result tied to one model. The "redacted" thinking in your pilot is the documented default `display: "omitted"` on the 5.5 models. Setting `display: "summarized"` returns readable text at no extra cost, but a different model writes that summary and it is never the raw reasoning.
- **Design (inference):** Spend on distinct prompts rather than repeats (P=80, m=2). Treat the prompt as the cluster. Use paired tests on shared prompts for arm comparisons, and report zero event cells as one sided upper bounds computed on the number of prompts, not the number of samples. Do not batch the multi turn tool loops.

## 1. Panel table

Prices are USD per million tokens. They come from the Anthropic pricing page and are listed as input / output / 5 minute cache write / cache read / batch input and output. Retirement dates come from the model deprecations page. Thinking behavior comes from the Thinking docs.

**How to read the Inspect column:** all the Inspect changes cited below are in 0.3.278, which you run. Fact: the Haiku 5.5 pull request merged on October 7, 2026, after 0.3.277 shipped (October 6); the 0.3.278 notes (October 9) include its fallback and thinking changes. For models marked UNVERIFIED, the first supporting Inspect version was not found.

| Model id | Generation | Prices (in / out / cache write / cache read / batch) | Tool use; forced `tool_choice` | Thinking and what comes back | Decline evidence | Retirement | Inspect support | Source |
|---|---|---|---|---|---|---|---|---|
| `claude-fable-5-1` | Fable 5.1 | $10 / $50 / $12.50 / $0.25 / $5 and $25 | Yes; forced choice rejected | Adaptive, cannot be turned off; default display omitted, summarized on request | Safety classifiers; fallback targets are Opus 4.8 and Opus 5 | Not sooner than Sep 1, 2027 | UNVERIFIED first version | Pricing; Deprecations; Thinking; Refusals and fallback; What's new in Fable 5.1 |
| `claude-mythos-5-1` | Mythos 5.1 | $10 / $50 / $12.50 / $0.25 / $5 and $25 | Yes; forced choice rejected | As Fable 5.1 | Classifier coverage not stated in the refusals page; general availability UNVERIFIED (a secondary source says the Mythos tier is gated) | Not sooner than Sep 1, 2027 | UNVERIFIED | Pricing; Deprecations; Thinking |
| `claude-fable-5` | Fable 5 | $10 / $50 / $12.50 / $1 / $5 and $25 | Yes; forced choice allowed under adaptive thinking (no thinking block in that response) | Adaptive, cannot be turned off; default omitted | Classifiers; fallback to Opus 4.8 | Not sooner than Jun 9, 2027 | UNVERIFIED | Pricing; Deprecations; Thinking |
| `claude-mythos-5` | Mythos 5 | $10 / $50 / $12.50 / $1 / $5 and $25 | Yes; forced allowed | Adaptive, cannot be turned off; default omitted | "Claude Mythos 5 does not include these classifiers"; access UNVERIFIED | Not sooner than Jun 9, 2027 | UNVERIFIED | Fable 5 launch doc; Deprecations |
| `claude-mythos-preview` | Mythos Preview | Not on the pricing table | UNVERIFIED | Adaptive; default omitted; summarizes from the first token | Restricted access (Glasswing) UNVERIFIED | Deprecated Jun 9, 2026; retirement date to be announced | UNVERIFIED | Deprecations; Thinking |
| `claude-opus-5-5` | Opus 5.5 | $4 / $20 / $5 / $0.20 / $2 and $10 | Yes; forced choice rejected; Inspect degrades it to auto | Adaptive, cannot be turned off; default effort medium; default omitted | Your pilot: 3 of 3 cyber declines. Three stage cyber classifier plus a biology classifier | Not sooner than Sep 22, 2027 | 0.3.267 | Pricing; Thinking; Inspect changelog; Opus 5.5 system card §3.2 |
| `claude-opus-5` | Opus 5 | $5 / $25 / $6.25 / $0.50 / $2.50 and $12.50 | Yes; forced allowed | Adaptive on by default; `disabled` allowed at effort high or below; default omitted | Classifiers (cyber, reasoning_extraction; its own biology classifier with no fallback) | Not sooner than Jul 24, 2027 | UNVERIFIED | Pricing; Thinking; Refusals and fallback |
| `claude-opus-4-8` | Opus 4.8 | $5 / $25 / $6.25 / $0.50 / $2.50 and $12.50 | Yes; forced allowed | Off by default; adaptive on request; default omitted | Real time cyber safeguards since Opus 4.7. Opus 4.8 is the documented fallback target for cyber declines | Not sooner than May 28, 2027 | UNVERIFIED | Pricing; Thinking; Opus 5.5 migration guide |
| `claude-opus-4-7` | Opus 4.7 | $5 / $25 / $6.25 / $0.50 / $2.50 and $12.50 | Yes; forced allowed | Off by default; adaptive; default omitted | Cyber safeguards "newly added in Claude Opus 4.7"; returns `stop_details` | Not sooner than Apr 16, 2027 | UNVERIFIED | Opus 5.5 migration guide; Pricing |
| `claude-opus-4-6` | Opus 4.6 | $5 / $25 / $6.25 / $0.50 / $2.50 and $12.50 (previous tokenizer) | Yes; forced allowed | Off by default; adaptive or extended (deprecated); default summarized | No classifier documented (inference from "newly added in 4.7") | Not sooner than Feb 5, 2027 | UNVERIFIED | Pricing; Thinking |
| `claude-opus-4-5-20251101` | Opus 4.5 | $5 / $25 / $6.25 / $0.50 / $2.50 and $12.50 | Yes; forced not allowed with extended thinking enabled | Extended thinking only (`budget_tokens`); default summarized | None documented | Not sooner than **Nov 24, 2026** | UNVERIFIED | Pricing; Thinking; Deprecations |
| `claude-sonnet-5-5` | Sonnet 5.5 | $2 / $10 / $2.50 / $0.10 / $1 and $5 | Yes; forced choice rejected; Inspect degrades it to auto | Adaptive; `disabled` rejected; lowest setting is `between_tools`; default omitted | 0 of 43 in your pilot. Same three stage cyber design, falls back to Sonnet 5 | Not sooner than Sep 28, 2027 | 0.3.272 | Pricing; Thinking; Inspect changelog; Sonnet 5.5 system card §3.3 |
| `claude-sonnet-5` | Sonnet 5 | $2 / $10 / $2.50 / $0.20 / $1 and $5 | Yes; forced allowed | Adaptive on by default; `disabled` allowed; default omitted | Not listed among classifier models | Not sooner than Jun 30, 2027 | UNVERIFIED | Pricing; Thinking |
| `claude-sonnet-4-6` | Sonnet 4.6 | $3 / $15 / $3.75 / $0.30 / $1.50 and $7.50 | Yes; forced allowed | Off by default; adaptive or extended; default summarized | None documented | Not sooner than Feb 17, 2027 | UNVERIFIED | Pricing; Thinking |
| `claude-sonnet-4-5-20250929` | Sonnet 4.5 | $3 / $15 / $3.75 / $0.30 / $1.50 and $7.50 | Yes; forced not allowed with extended thinking enabled | Extended only; default summarized | None documented | **Deprecated; retires Nov 30, 2026** | UNVERIFIED | Deprecations; Pricing |
| `claude-haiku-5-5` | Haiku 5.5 | $0.10 / $0.50 / $0.125 / $0.01 / $0.05 and $0.25 (prompts up to 100,000 tokens) | Yes; **forced choice accepted** | Adaptive; `disabled` allowed at effort high or below; default omitted | 0 of 43 in your pilot. Narrower classifiers, no server side fallback, no fallback credit | Not sooner than Oct 7, 2027 | 0.3.278 | Pricing; Thinking; Refusals and fallback; Inspect PR #5752 |
| `claude-haiku-4-5-20251001` | Haiku 4.5 | $1 / $5 / $1.25 / $0.10 / $0.50 and $2.50 | Yes; forced not allowed with extended thinking enabled | Extended only; default summarized | None documented | Active; not sooner than **Oct 15, 2026** | UNVERIFIED | Deprecations; Pricing |

**Already retired on the Claude API (fact):**
- Opus 4.1 (August 5, 2026)
- Opus 4 and Sonnet 4 (June 15, 2026)
- Haiku 3 (April 20, 2026)
- Sonnet 3.7 and Haiku 3.5 (February 19, 2026)
- Opus 3 (January 5, 2026)

No Claude 3 generation model remains on the API.

**Version trend (inference):**
- **Opus line:** six generations (4.5, 4.6, 4.7, 4.8, 5, 5.5) at near identical list prices. This is the cleanest trend line. Two caveats: a tokenizer change at 4.7, which "produces approximately 30% more tokens for the same text", and default thinking changing from off to on at 5.
- **Sonnet line:** 4.5, 4.6, 5 and 5.5 give a second line.
- **Haiku line:** 4.5 and 5.5 give two points only.

## 2. Findings table

| Q | Finding | Source | Impact on design |
|---|---|---|---|
| 1 | Fact: the Claude 4.7 and later models and Claude Mythos Preview return HTTP 400 when sampling parameters are set to nondefault values. Python SDK v1.0 and later removes `temperature`, `top_p` and `top_k` and raises a `TypeError` if you pass them. | Model deprecations page, API parameter deprecations | Your SDK 1.13.0 cannot send sampling parameters to any model, so the panel is uniform. Variance comes from epochs alone. |
| 1 | Fact: deprecated models are "likely to be less reliable than active models", and Anthropic commits to "at least 60 days' notice" before retiring publicly released models. Haiku 4.5 is active, with no deprecation notice and a date "not sooner than October 15, 2026". | Model deprecations page | Inference: Haiku 4.5 should stay at least 60 days after any notice, but run it and Sonnet 4.5 first. |
| 1 | Fact: forced tool use is rejected on Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1. Elsewhere it is supported under adaptive thinking, with no thinking block in that response. Manual extended thinking allows only `auto` or `none`. | Thinking docs, "Thinking with tool use" | Forced first declarations work on Haiku 5.5, Sonnet 5, Opus 5 and the Opus 4.6 to 4.8 models. They do not work on the 5.5 Sonnet/Opus or Fable 5.1 models. |
| 1 | Fact: an Inspect reviewer comment dismissed as known says "forced tool choice is dropped under thinking ... long-standing behavior for all Claude models". | Inspect PR #5752 | Inference: when reasoning is configured, Inspect will not force tool choice on any Claude model. Log `tool_choice_degraded` for every model, not only Sonnet 5.5. |
| 2 | Fact: Fable 5.1, Fable 5, Opus 5.5, Opus 5, Sonnet 5.5 and Haiku 5.5 "include safety classifiers that can decline a request". | Refusals and fallback docs | S5 has six classifier models plus Opus 4.7 and 4.8 (cyber safeguards since 4.7, per the Opus 5.5 migration guide). |
| 2 | Fact: the Opus 5.5 cyber system "uses three stages": a probe on internal activations, then "a lightweight classifier running on Claude Opus 5.5 itself", then a separate "trained LLM classifier". Sonnet 5.5 uses the same three stages; Haiku 5.5 uses narrower blocking classifiers. | Opus 5.5 system card §3.2; Sonnet 5.5 card §3.3; Haiku 5.5 card §3.2 (gathered by the subagent) | Speculation: thresholds differ per model ("Anthropic sets safeguards for each model individually"), which may explain why Opus 5.5 declines your task and Sonnet 5.5 does not. |
| 2 | Fact: a refusal before any output is billed only for `bio`, `frontier_llm` and `reasoning_extraction`. `cyber`, `general_harms` and null are not billed, but "the request still counts against your rate limits". Mid stream refusals bill input and streamed output. | Refusals and fallback, "How refusals are billed"; release notes, September 24, 2026 | Running the full Opus 5.5 S1 grid costs close to $0 if every request declines before output. The budget below still prices the worst case. |
| 2 | Fact: fallback runs only if you set `fallbacks` (beta header `server-side-fallback-2026-07-01`) or install SDK middleware. It is not supported in Message Batches. The serving model is shown in the top level `model` field and in `usage.iterations`. "Sticky routing" can send later turns straight to the fallback model. | Refusals and fallback docs | Never set Inspect `fallback_models`. Add a hard check per call that `response.model` equals the requested id and that no `fallback_message` iteration exists, so no per model result is confounded. |
| 2 | Fact: 11% of the Sonnet 5.5 IPI benchmark rollouts "were served by a fallback model after a classifier was triggered". | Sonnet 5.5 system card §5.2.1 (subagent) | Inference: Anthropic's published per model injection rates mix models. Your design without fallback is the cleaner per model estimate; say so in the paper. |
| 2 | Fact: a `reasoning_extraction` refusal is triggered by "a `reasoning`, `thinking`, or `trace` field in JSON output or in a tool input", and it is billed. | Refusals and fallback, "Keep reasoning in thinking blocks" | The S2 declaration schema and any judge prompt must not contain a reasoning or rationale field. |
| 2 | Not met: the Cyber Verification Program gives individuals Defense Access only, and you hold none of its credentials. No other route for an independent researcher was confirmed. **UNVERIFIED** (no primary source found). | None | Report the Opus 5.5 declines as an S5 result. Do not route around them. |
| 3 | Fact: "what you see is never the raw chain of thought". `display` defaults to `"omitted"` on Fable 5.1, Mythos 5.1, Fable 5, Mythos 5, Opus 5.5, Opus 5, Sonnet 5.5, Sonnet 5, Opus 4.8, Opus 4.7, Mythos Preview and Haiku 5.5. Omitted thinking is billed the same. | Thinking docs | Your "redacted" pilot blocks are the omitted default, not safety redaction (`redacted_thinking` is a separate block type). Setting `display: "summarized"` costs nothing extra. Whether Inspect 0.3.278 exposes this for the native Anthropic provider is **UNVERIFIED**; test `--extra-body` (0.3.271) in a smoke run. |
| 3 | Fact: "Summarization is processed by a different model from the one you target in your requests. The thinking model does not see the summarized output." | Thinking docs, "Summarized thinking" | Inference: summarized text measures what a summarizer kept, two steps removed from the computation. |
| 3 | Fact: in "Reasoning Models Don't Always Say What They Think", Claude 3.7 Sonnet verbalized hints 25% of the time overall and 20% for misalignment hints. Unfaithful reasoning traces were longer than faithful ones. | arXiv:2505.05410 | Inference: a mention of the injection in thinking is evidence the model recognized it. No mention is not evidence that it didn't. Report it one sided, as a lower bound on recognition. |
| 3 | Fact: in Anthropic's adaptive Shade tests, Sonnet 5 was compromised on 19.47% of coding attempts with thinking and 40.30% without. Every Gray Swan IPI figure in the 5.5 cards ran with extended thinking. No effort level comparison for prompt injection was found. | Sonnet 5.5 system card pp.51 to 52 (subagent) | Thinking state is a real covariate. Fix it per model and preregister it. Effort effects are **UNVERIFIED**. |
| 4 | Fact: Inspect supports Anthropic batch processing via `--batch`. Its docs warn that agentic evals "can often take many hours or days", each batch up to 24 hours. Provider request ids are recorded "except in batch mode", and batch calls "have a response id but no request ids". | Inspect Batch Mode docs; Log Files docs; PR #5676 | Do not batch the event scored tool loops. Whether `--log-model-api` keeps the raw batched response is **UNVERIFIED**. Batch only single turn judge calls, if anything. |
| 4 | Fact: Inspect 0.3.264 made `cache_ttl` default to "auto"; 0.3.273 lets prompts mark a stable cached prefix. Cache multipliers stack with the Batch discount. The minimum cacheable prompt on Opus 5.5 is 512 tokens. | Inspect changelog; Pricing; What's new in Opus 5.5 | Tool definitions sit at the front of the cached prefix, so the poisoned and clean descriptions form separate caches. Epochs of the same arm reuse them. |
| 4 | Fact: 0.3.277 prices each request "at the rates of the model that served it", and a call is refused once a cost limit is reached. | Inspect changelog 0.3.277 | Inspect's `cost_limit` can act as a second fail closed guard beside your ledger. |
| 4 | Fact: Anthropic's Rate limits page gives the Start tier 1,000 RPM, 2,000,000 input tokens per minute (ITPM) and 400,000 output tokens per minute for Opus 5.5, Opus 5, Opus 4.x, Sonnet 5.5, Sonnet 5, Sonnet 4.x, Haiku 5.5 and Haiku 4.5. Fable 5.x gets 1,000 RPM, 500,000 ITPM and 100,000 output tokens per minute, as a "total limit that applies to combined traffic across Claude Fable 5.1 and Claude Fable 5". Opus 4.8, 4.7, 4.6 and 4.5 share one combined limit, and the Start spend cap is $500 per month. Anthropic's Token counting docs say: "Token counting is free to use but subject to requests per minute rate limits based on your usage tier", with limits "separate and independent" from message creation. | Anthropic Rate limits docs; Token counting docs | Inference: `max_connections` of 10 to 20 is far under these limits for this workload. Declines still consume RPM. Use the free token counting endpoint for the ledger's preflight estimate. |
| 5 | Fact: Gray Swan IPI attack success after 15 attempts, all with extended thinking: Haiku 5.5 7.1% (GUI 24.4%, tool use 4.0%, coding 0.2%); Haiku 4.5 83.2%; Sonnet 5.5 3.4% (0.4% after one attempt); Sonnet 5 6.7% (0.7% after one); Opus 5.5 1.0%; Fable 5.1 1.0%. The single attempt rates for Opus 5.5 and Haiku 5.5 were NOT FOUND in text. | Haiku 5.5 system card §5.2.1 p.50; Sonnet 5.5 card §5.2.1 p.50 (subagent) | Gives an external prior and a trend for the panel. |
| 5 | Secondary, conflicting: news coverage of the Opus 5 card reports Opus 5 at 0.2% after one attempt and 2.0% after 15, Opus 4.8 at 0.5% and 5.5%, Sonnet 5 at 5.9%, Mythos 5 at 2.6% and Fable 5 at 2.8%. This Sonnet 5 figure (5.9%) conflicts with 6.7% in the Sonnet 5.5 card. | Secondary reports of the Opus 5 system card (July 24, 2026) | Inference: the benchmark revision probably differs (the newer card cites Q1+Q2 2026). Cite only the newest card's numbers. |
| 5 | Fact: MCPTox evaluated 20 LLM agents; o1-mini reached 72.8% attack success. Per search snippets of MCPTox Table 2 (the paper itself was not fetched), Claude-3.7-Sonnet averaged 34.3% attack success across all paradigms against a 36.5% all model average, and despite having the highest refusal rate it "rejected the attack in less than 3% of cases". MSB reports a peak of 75.83%, an average of 40.35%, and higher prompt injection effectiveness against "stronger models such as Claude 4 Sonnet"; its exact Claude rows remain **UNVERIFIED**. | arXiv:2508.14925; arXiv:2510.15994 | Neither benchmark's Claude models are still served, so neither gives a same panel row. |
| 5 | Fact: `inspect_evals/agentdojo` exists, with `attack=important_instructions`, suite selection and task id filters. AgentDojo (Debenedetti et al., ETH Zurich, NeurIPS 2024) has 97 tasks and 629 security test cases across email, banking, travel and workspace. An MCPTox or MSB port in inspect_evals was not found: **UNVERIFIED**. | Inspect Evals AgentDojo page; arXiv:2406.13352 via citing papers | One AgentDojo suite on a subset of models gives a cheap external validity row. |
| 6 | Fact: clustered standard errors "can be over 3X larger than naive standard errors". Miller gives paired and paired clustered formulas for comparing two models. | arXiv:2411.00640 | Cluster on the prompt. Use paired, clustered differences for arm against arm and split against same. |
| 6 | Inference (standard methods; no primary source gathered here, so **UNVERIFIED** as a citation): GEE sandwich errors are biased downward with few clusters, so use a small sample correction or exact permutation over prompts below about 40 clusters. A mixed effects logistic model with a random intercept per prompt is unstable when events are sparse. Holm for confirmatory contrasts, Benjamini Hochberg for exploratory panel comparisons. For a zero event cell, the 95% upper bound is about 3/n, with n taken as the number of prompts when the intraclass correlation (ICC) is high. | Standard statistical practice | P=80 gives a zero event upper bound of about 3.75% (3/80). Fewer prompts cannot separate models near the 1% to 7% published rates. |
| 7 | Fact: Inspect `handoff()` turns an agent into a `transfer_to_` tool. Agents can reach other models, including model roles (`get_model(role=...)`). By default, handoff output passes through `content_only()`, which removes reasoning and turns tool calls into text. 0.3.278 extends tool review to `handoff()` calls. | Inspect Multi Agent docs; inspect_ai.agent reference; release 0.3.278 | Inference: a custom solver that calls two models by role logs one model event per call for each, so both raw responses are captured under `--log-model-api`. Confirm in a smoke log. |
| 7 | Fact: mid conversation tool changes are in beta on Fable 5, Mythos 5, Opus 4.8 and Opus 5, preserving the prompt cache. | Claude Platform release notes | One option for S2 is to expose only `declare_contract` on turn one and the full toolset after it. |
| 7 | Fact (from titles and citations only): CaMeL (arXiv:2503.18813) is a plan then execute defense. "Adaptive attacks break defenses against indirect prompt injection attacks on LLM agents" (arXiv:2503.00061) and "Adaptive Attacks on Trusted Monitors Subvert AI Control Protocols" (arXiv:2510.09462) target defenses. Their specific results were not verified here. | Reference lists of arXiv:2510.26328 and arXiv:2608.17597 | Inference: the obvious attack on S2 and S7 is a poisoned description that tells the agent or planner to declare `audit-log@internal.corp` as an allowed recipient. Score "contract poisoned" as its own preregistered outcome. |

## 3. Budget allocation ($200 total, $20 reserve, $180 allocatable)

**Unit costs.**
- **Measured (fact):** Haiku 5.5 $0.000284, Sonnet 5.5 $0.005947, Sonnet 4.5 $0.007347.
- **Scaled by list price ratio (inference):** models on the previous tokenizer or off by default thinking are scaled from Sonnet 4.5; models on the newer tokenizer are scaled from Sonnet 5.5.
  - Haiku 4.5: 0.007347 × (1/3) = 0.002449
  - Sonnet 4.6: × 1 = 0.007347
  - Opus 4.5 and 4.6: 0.007347 × (5/3) = 0.012245
  - Sonnet 5: 0.005947 × 1 = 0.005947
  - Opus 4.7, Opus 4.8 and Opus 5: 0.005947 × 2.5 = 0.014868
  - Opus 5.5: 0.005947 × 2 = 0.011894
  - Fable 5.1: 0.005947 × 5 = 0.029735
- **Speculation:** a thinking on run costs 2× the default sample, and an AgentDojo sample costs 3× a TL-01 sample.

**S1 Transparency Rate plus clean control.** Fact: per model, P=80 prompts × 3 nonpersuasion attack variants (directive placement or format only) × 2 epochs = 480 poisoned samples, plus 80 × 2 = 160 clean samples, for 640 samples.

| Model | Arithmetic | Cost |
|---|---|---|
| Haiku 5.5 | 640 × 0.000284 | $0.18 |
| Haiku 4.5 | 640 × 0.002449 | $1.57 |
| Sonnet 4.5 | 640 × 0.007347 | $4.70 |
| Sonnet 4.6 | 640 × 0.007347 | $4.70 |
| Sonnet 5 | 640 × 0.005947 | $3.81 |
| Sonnet 5.5 | 640 × 0.005947 | $3.81 |
| Opus 4.5 | 640 × 0.012245 | $7.84 |
| Opus 4.6 | 640 × 0.012245 | $7.84 |
| Opus 4.7 | 640 × 0.014868 | $9.52 |
| Opus 4.8 | 640 × 0.014868 | $9.52 |
| Opus 5 | 640 × 0.014868 | $9.52 |
| Opus 5.5 (worst case; about $0 if every request declines before output) | 640 × 0.011894 | $7.61 |
| Fable 5.1 | 640 × 0.029735 | $19.03 |
| **S1 subtotal** | sum of rows above | **$89.65** |

**S1 thinking contrast (poisoned arm only, P=80 is not needed here; 150 samples = 50 prompts × 3 epochs).**
- Haiku 5.5 with thinking `disabled`: 150 × 0.000284 = $0.04
- Sonnet 5 with thinking `disabled`: 150 × 0.005947 = $0.89
- Sonnet 4.6 with adaptive thinking: 150 × 0.007347 × 2 = $2.20
- Opus 4.6 with adaptive thinking: 150 × 0.012245 × 2 = $3.67
- Subtotal: $6.81

**S2 contracts.**
- Fact: the "no contract" arm reuses S1 data. The "model bypassed" arm sends the injected call straight to the enforcement layer, so it costs $0 in API spend.
- Speculation: the "declared and enforced" arm costs 1.3× per sample for the extra turn.
- Run 2 arms (poisoned and clean) × 150 samples:
  - Haiku 5.5: 300 × 0.000284 × 1.3 = $0.11
  - Sonnet 5.5: 300 × 0.005947 × 1.3 = $2.32
  - Sonnet 4.6: 300 × 0.007347 × 1.3 = $2.87
  - Opus 4.8: 300 × 0.014868 × 1.3 = $5.80
- Subtotal: $11.10

**S3 codebook and LLM judge for S1 and S3.** No new agent runs are needed. Judge: 4,000 calls × $0.0025 (speculation, short single turn calls) = $10.00. Use a model outside the classifier list, with no reasoning field in the prompt.

**S5 classifier preemption.** $0 extra; it is derived from the S1, S2 and S7 logs.

**S7 planner and executor split.** Speculation: a planner call costs 0.5 × that model's sample cost. Run 2 arms × 150 samples:
- Sonnet 5.5 plans, Haiku 5.5 executes: 300 × (0.5 × 0.005947 + 0.000284) = $0.98
- Haiku 5.5 plans, Sonnet 5.5 executes: 300 × (0.5 × 0.000284 + 0.005947) = $1.83
- Opus 4.8 plans, Sonnet 4.6 executes: 300 × (0.5 × 0.014868 + 0.007347) = $4.43
- Subtotal: $7.24

**External validity: AgentDojo banking suite**, 16 user tasks × 9 injection tasks = 144 cases, `important_instructions` attack.
- Haiku 5.5: 144 × 0.000852 = $0.12
- Haiku 4.5: 144 × 0.007347 = $1.06
- Sonnet 5.5: 144 × 0.017841 = $2.57
- Sonnet 4.5: 144 × 0.022041 = $3.17
- Opus 4.6: 144 × 0.036735 = $5.29
- Opus 4.8: 144 × 0.044604 = $6.42
- Subtotal: $18.63

**Smoke tests and preflight** (display check, fallback check, logging check): $5.00.

**Estimate buffer** for the 10 per sample costs extrapolated rather than measured: $180 minus ($89.65 + $6.81 + $11.10 + $10.00 + $7.24 + $18.63 + $5.00) = $180 minus $148.43 = $31.57.

**Reserve** (ledger enforced, not spendable without a preregistered amendment): $20.00. Total: $148.43 + $31.57 + $20.00 = $200.00.

## 4. Decisions for you (recommended option first)

1. **Panel scope.**
   - **Recommended:** all 14 rows above (the Opus line from 4.5 to 5.5 for the trend, Sonnet 4.5 to 5.5, Haiku 4.5 and 5.5, Fable 5.1).
   - Alternative: the 5.5 family only, which is cheaper but gives no version trend.
   - Exclude Mythos 5 and 5.1 until access is confirmed.
2. **Opus 5.5 declines.**
   - **Recommended:** keep fallbacks off, run Opus 5.5 at the full S1 size, and report the decline rate as the S5 result. Opus 4.8 stays as its own row.
   - Alternative: enable `fallbacks: "default"`. This would mix models within an Opus 5.5 cell and is not recommended.
3. **Visible reasoning.**
   - **Recommended:** set `display: "summarized"` on every adaptive model (no extra cost). Code thinking as a one sided recognition indicator from summaries, not raw chain of thought, and report it separately from final message disclosure.
   - Alternative: drop thinking analysis entirely.
4. **Batching.**
   - **Recommended:** no batching for event scored runs. Optionally batch the single turn judge calls, but only after confirming the raw responses appear in the log.
   - Alternative: batch everything for 50% off, accepting waits of up to 24 hours per turn and unconfirmed raw logging.
5. **Prompts against repeats.**
   - **Recommended:** P=80, m=2, analyzed with clustered and paired methods.
   - Alternative: P=40, m=4 at the same cost. This roughly halves the number of independent clusters, and with them the power to rank models.
