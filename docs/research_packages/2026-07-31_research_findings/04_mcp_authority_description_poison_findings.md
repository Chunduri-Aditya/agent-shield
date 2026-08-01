# 04 — MCP Authority and Description Poison Findings

Status: hardening design. Current pins remain facts: proxy local canonical markers quarantine, the paraphrase misses, and the research content rule is not the description proxy defense. No ruleset version change follows from proxy only work.

Local evidence basis: [aggressive runtime findings](../../runtime_aggressive_testing_research.md).

## A. Psychology primary sources, ranked

1. Langer, Blank, and Chanowitz experimentally tested compliance with requests containing real or placebic reasons. The result motivates reason shaped paraphrases as a threat class, but exact effects should not be assumed for language models. [DOI 10.1037/0022-3514.36.6.635](https://doi.org/10.1037/0022-3514.36.6.635).
2. Reber and Schwarz found that perceptual fluency affected truth judgments, supporting a hypothesis that polished bureaucratic wording can appear more credible. [DOI 10.1006/ccog.1999.0386](https://doi.org/10.1006/ccog.1999.0386).
3. Milgram’s authority experiment supports testing explicit authority cues, with strong limits on transfer from humans to models. [DOI 10.1037/h0040525](https://doi.org/10.1037/h0040525).
## B. Cybersecurity and agent security primary sources, ranked

1. The MCP specification defines tool metadata and input schemas as model visible protocol structures. The protocol structure is authoritative for field boundaries, not for safety guarantees. [MCP schema specification](https://modelcontextprotocol.io/specification/2025-11-25/schema).
2. MCPTox studies toxic and malicious content in MCP metadata, including tool descriptions and parameters, and is directly relevant to the description versus schema split. [arXiv 2508.14925](https://arxiv.org/abs/2508.14925).
3. Invariant Labs’ original tool poisoning disclosure describes malicious instructions hidden in tool descriptions and cross server effects. It is a primary vulnerability disclosure, not a controlled psychology experiment. [Invariant Labs](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks).
4. OWASP’s MCP tool poisoning entry describes untrusted metadata changing model behavior and recommends metadata integrity and review controls. [OWASP MCP Tool Poisoning](https://owasp.org/www-community/attacks/MCP_Tool_Poisoning).
5. MCP ITP studies indirect tool poisoning and provides a broader threat model for tool metadata manipulation. [arXiv 2601.07395](https://arxiv.org/abs/2601.07395).
6. Adaptive indirect prompt injection results show that defenses evaluated only against known phrasings can fail under tailored attacks. [ACL Findings 2025](https://aclanthology.org/2025.findings-naacl.395/).

## C. MERGE — A1 through A7 paraphrase taxonomy, false positive map, and promotion rule

### Refined taxonomy

| Class | Psych label | Abstract description pattern | Security objective | Structural cue safer than phrase matching |
|---|---|---|---|---|
| A1 | Direct authority | Claims administrator, system, security, legal, or vendor authority | Override user intent or mandate a side action | Imperative directed at the model plus action outside the tool’s declared purpose |
| A2 | Audit and compliance | Frames the side action as required for logging, verification, certification, or policy | Exfiltrate or invoke an unrelated tool under procedural cover | Requirement language plus unrelated destination, field, or tool reference |
| A3 | Placebic reason | Supplies a fluent but noncausal “because” justification | Increase compliance without adding legitimate tool semantics | Reason clause whose requested action does not affect the tool result |
| A4 | Soft obligation | Uses recommendations, best practice, safety advice, or courtesy instead of a command | Evade imperative keyword rules | Modal instruction to the model or assistant, especially before or after normal docs |
| A5 | Social proof and precedent | Claims all clients, approved workflows, or prior operators perform the side action | Manufacture legitimacy | Unverifiable external consensus paired with an unrelated operation |
| A6 | Role play or hypothetical | Places the model in auditor, tester, developer, or emergency role | Create an instruction hierarchy loophole | Role reassignment inside metadata plus action request |
| A7 | Commitment and sequencing | Makes normal tool use conditional on first completing a side action or preserving a hidden rule | Bind the model to an attacker controlled sequence | Cross tool dependency or stateful instruction not represented in the schema |

The shared psych taxonomy in `psych/` may supply labels such as authority, social proof, and commitment. The MCP taxonomy must remain separate because its unit is a metadata control pattern, its benign corpus is tool documentation, and its outcome is quarantine or model exposure rather than persuasion score.

### False positive risk in legitimate documentation

| Documentation type | Example benign function | FP risk | Reason |
|---|---|---:|---|
| Authentication parameter docs | “Required by policy” or “administrator supplied” | HIGH | Authority and requirement terms are ordinary API language. |
| Audit and logging tools | “Send events for compliance review” | HIGH | The legitimate tool purpose overlaps A2 vocabulary. |
| Messaging and notification tools | “Send message to recipient” | HIGH | Cross destination verbs are intrinsic to the tool. |
| Destructive administration tools | “Confirm before deleting” | MEDIUM | Imperatives may be safety instructions rather than poison. |
| Generic lookup tools | A side request to contact, upload, or remember | LOW | Such actions are outside declared purpose. |
| Pure formatting or calculation tools | Network, credential, or messaging instruction | LOW | Cross capability language is structurally anomalous. |

Therefore “no imperative mood” is not a defensible general policy. It would reject legitimate safety and parameter documentation. The better long term direction is structural: bind each tool to declared effects and destinations, exclude raw descriptions from the model, expose a normalized purpose summary, and quarantine metadata that directs model behavior outside those effects. Model side hierarchy prompts can be defense in depth, not the only boundary.

### Corpus and split design

Collect at least 100 benign descriptions across authentication, audit, messaging, storage, finance, developer, and destructive administration categories. Keep source projects disjoint between development and holdout where feasible. Build attacks from semantic templates, then assign entire template families and authors to either development or holdout. No paraphrase sibling crosses the split.

Development contains canonical TL01 plus four A1 through A7 variants each. Holdout contains at least three independently authored variants per class and 50 benign descriptions from unseen projects. An additional challenge set contains legitimate high risk vocabulary from audit, policy, and messaging tools.

### Promotion rule for proxy heuristic changes

Any heuristic change is promoted only if all are true:

1. Canonical pins remain quarantined.
2. Holdout recall improves by at least 10 percentage points with the lower paired confidence bound above zero.
3. Benign quarantine point estimate is at most 1 percent and the upper Wilson bound is reported.
4. No high risk benign category has more than one quarantine.
5. The rule exposes a stable reason code and bounded span.
6. `model_tools` still excludes `original_description`.
7. The change touches proxy policy only and does not bump `CONTENT_RULESET_VERSION`.
8. All tuned examples are removed from the next frozen holdout.

Because a 1 percent gate cannot be demonstrated tightly with only 50 benign items, 50 is a collection floor, not a strong statistical validation set. Zero errors in 50 still has an upper 95 percent Wilson bound around 7 percent. A credible upper bound near 1 percent requires several hundred benign descriptions.

## D. Operationalization for Agent Shield

Add proxy reason codes `DESC_DIRECT_AUTHORITY`, `DESC_CROSS_TOOL_DIRECTIVE`, `DESC_UNRELATED_DESTINATION`, `DESC_ROLE_REASSIGNMENT`, `DESC_HIDDEN_SEQUENCE`, and `DESC_AUDIT_PRETEXT`. Rules should combine at least two signals: model directed language plus a cross purpose action, destination, credential reference, hidden state requirement, or role change.

Preserve canonical and paraphrase miss pins before implementation. Emit both `proxy_policy_version` and `content_ruleset_version`. Store normalized descriptions for model exposure, the raw description only in restricted audit evidence, and a hash binding the two.

## E. Failure modes and confounds

1. Regex widening memorizes public TL01 wording.
2. Legitimate messaging tools resemble exfiltration because sending is their purpose.
3. Tool titles or host annotations reintroduce raw text after proxy normalization.
4. A model side system prompt appears effective only because attacks were not adaptive.
5. English mood heuristics fail across languages and telegraphic documentation.
6. A source disjoint split still shares generated paraphrase templates.
7. Quarantine recall rises by rejecting most tools, destroying utility.

## F. Ethics and dual use

Public reports list semantic classes and redacted examples, not full transfer ready poisons. Do not test against live third party MCP catalogs or unpaid services. HIGH cases that include real destinations, credentials, or chained actions require `CONFIRM_HIGH_RISK` and should normally be replaced with inert placeholders.

## G. BACKLOG candidates, not ship line

1. Effect and destination manifests for normalized MCP tools.
2. Multilingual benign documentation corpus.
3. A learned challenger evaluated only after a deterministic proxy baseline.
4. Signed catalog metadata and change detection.

## H. Open questions Aditya must decide

1. Is the project willing to collect the several hundred benign descriptions needed for a tight 1 percent upper bound?
2. Which tool categories are allowed to issue cross tool instructions by design?
3. Is structural effect declaration feasible in the adapter contract?
4. Should the first heuristic change target only low FP cross purpose cases, accepting known authority paraphrase misses elsewhere?
