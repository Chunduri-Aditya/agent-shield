# 05 — Schema Channel Screening Findings

Status: phased design, not an implementation. Current pinned behavior remains valid: `input_schema` and its examples are not screened. The proposed flag is off by default until its corpus and false positive gates pass.

Local evidence basis: [aggressive runtime findings](../../runtime_aggressive_testing_research.md).

## A. Psychology primary sources, ranked

1. Mack and Rock’s inattentional blindness experiments show that visible stimuli can go unnoticed when attention is occupied elsewhere. This supports treating nested schema text as a low salience channel, with the limit that a model is not a human observer. *Inattentional Blindness*, ISBN 9780262133395, [MIT Press](https://mitpress.mit.edu/9780262133395/inattentional-blindness/).
2. Simons and Chabris experimentally demonstrated sustained inattentional blindness during a demanding visual task. The relevant transfer hypothesis is that task focused processing can miss unexpected instructions in peripheral structure. [DOI 10.1068/p281059](https://doi.org/10.1068/p281059).
3. Sweller’s cognitive load work supports the hypothesis that large schemas create competing processing demands, though it does not establish model specific attention limits. [DOI 10.1207/s15516709cog1202_4](https://doi.org/10.1207/s15516709cog1202_4).
4. Lee and See’s trust calibration framework supports testing whether familiar documentation structure creates unwarranted reliance. [DOI 10.1518/hfes.46.1.50.30392](https://doi.org/10.1518/hfes.46.1.50.30392).

## B. Cybersecurity and agent security primary sources, ranked

1. The MCP schema specification establishes that tools can carry `inputSchema` structures and metadata. It is the authority for field locations, not for the trustworthiness of their content. [MCP schema specification](https://modelcontextprotocol.io/specification/2025-11-25/schema).
2. JSON Schema 2020 12 defines schemas and their vocabularies, allowing nested annotations and applicators that make naive string scraping incomplete or context blind. [JSON Schema Core](https://json-schema.org/draft/2020-12/json-schema-core).
3. JSON Schema documents annotations such as `title`, `description`, `default`, `examples`, `readOnly`, and `writeOnly`. These are documentation surfaces with different benign semantics. [JSON Schema annotations](https://json-schema.org/understanding-json-schema/reference/annotations).
4. MCPTox directly studies malicious MCP metadata across descriptions and parameter related fields. [arXiv 2508.14925](https://arxiv.org/abs/2508.14925).
5. MCP Security Bench evaluates MCP attacks and defenses across realistic server interactions, supporting measurement by channel rather than assuming description findings transfer to schema. [OpenReview 7XYjeL46co](https://openreview.net/pdf?id=7XYjeL46co).
6. OWASP’s MCP tool poisoning guidance describes metadata as an instruction injection surface and recommends review and integrity controls. [OWASP MCP Tool Poisoning](https://owasp.org/www-community/attacks/MCP_Tool_Poisoning).

## C. MERGE — phased schema screening plan

### Threat model and unit of analysis

The attacker controls one or more model visible schema annotation strings. The host or proxy parses the schema, may merge annotations from multiple sources, and finally presents a tool schema to the model. The defensive unit is therefore a tuple: `tool_id`, JSON Pointer, annotation kind, normalized value, raw value hash, merge source, and presentation order.

Screening every string leaf is not the first phase. Enum values, property names, formats, regex patterns, and examples have legitimate executable or domain semantics. Treating them as prose would produce unclear false positives and could mutate tool behavior.

### Locus priority

| Order | Locus | Attacker value | Expected benign FP risk | Initial action |
|---:|---|---:|---:|---|
| 1 | Property and `$defs` `description` | HIGH | MEDIUM | Shadow scan, then gated quarantine for cross purpose directives |
| 2 | Root schema `description` | HIGH | MEDIUM | Same policy as tool description but distinct reason code |
| 3 | String entries in `examples` | HIGH | HIGH | Observe and label only; examples often contain URLs, commands, or realistic messages |
| 4 | Host merged annotations and vendor extension descriptions | HIGH | HIGH | Record provenance first; reject untracked post screen merge |
| 5 | `title` | MEDIUM | MEDIUM | Shadow scan only; short strings provide weak context |
| 6 | `default` and `const` strings | MEDIUM | HIGH | Integrity record only; no prose heuristic in first enablement |
| 7 | Property names and tool names | MEDIUM | VERY HIGH | Explicit non goal pending a separate study |
| 8 | Regex, format, enum, and numeric constraints | LOW for prose poison | VERY HIGH | Never feed to the prose detector in this plan |

### Enablement phases

| Phase | Flag state | Corpus and action | Exit gate |
|---|---|---|---|
| F5.0 inventory | Off | Record string loci, JSON Pointers, lengths, and merge source for at least 50 real benign parameter documents. No decisions change. | Provenance complete for every model visible field. |
| F5.1 shadow | Off | Scan only `description` loci and emit hidden diagnostics. Preserve model input unchanged. | Zero schema parser mutations; manual review of every flag. |
| F5.2 challenge | Off | Add paired redacted poisons and benign security prose. Measure recall and benign quarantine counterfactuals. | At least 90 percent recall on frozen low FP patterns; no category collapse. |
| F5.3 opt in | `AGENT_SHIELD_SCREEN_SCHEMA=1` | Quarantine only schema descriptions with cross purpose directives or unrelated destinations. | Benign point estimate at most 1 percent, upper Wilson bound published, utility above defense DoS floor. |
| F5.4 broaden | Same flag, new proxy policy version | Consider examples and merged annotations using separate policies. | New untouched holdout and independent false positive gate per locus. |

Fifty benign documents are enough to discover common structures but not enough to establish a tight 1 percent error bound. Zero false quarantines in 50 still yields an upper 95 percent Wilson bound near 7 percent. A serious upper bound near 1 percent needs roughly 380 to 400 independent benign documents with zero errors. Report the point estimate and interval rather than implying that 0 of 50 proves the target.

### Benign corpus protocol

Sample by source project and tool category, not by convenient field count. Include authentication, audit, messaging, payments, cloud administration, file operations, developer tools, healthcare style fields, and destructive actions. Cap any single project at 10 percent. Freeze source commit, path, license, schema hash, and extraction version. Split by source project so sibling descriptions do not cross development and holdout.

Manually label whether each field legitimately instructs the user, the client developer, the model, or another tool. False positive review must distinguish quarantine, alert, and shadow findings. Padded synthetic benign schemas do not count toward the gate.

### Structural policy

Imperative mood alone is insufficient because legitimate parameter descriptions say “provide,” “select,” “do not include,” or “confirm.” Quarantine should require an instruction aimed at the model plus a cross purpose feature: unrelated tool call, undeclared destination, credential request unrelated to the parameter, hidden sequence, role reassignment, or instruction to ignore higher level intent.

### Oversize behavior

Large schemas receive a `note`, not an injection alert, when length alone exceeds the scan budget. Scan budgets must be deterministic and locus aware. If full scanning is impossible, emit `schema_screen_coverage`, `unscanned_chars`, and the JSON Pointer ranges skipped. Never present partial coverage as a clean result.

Before F5.3, developer and proof views should show a neutral `schema screening: off` badge. After enablement, the badge should show `full`, `partial`, or `off` plus the policy version. It should not create one interruptive operator alert per tool because that would turn an honest coverage disclosure into alert noise.

### Explicit non goals

1. No screening of tool or property names in F5.
2. No recursive decoding of encoded strings.
3. No mutation of schemas or tool arguments.
4. No claim that description screening covers schemas.
5. No content ruleset version bump for proxy schema policy.
6. No rejection based only on schema size.

## D. Operationalization for Agent Shield

Add a deterministic walker that yields only approved annotation kinds with exact JSON Pointers. Record `schema_policy_version`, `field_kind`, `source_component`, `pre_merge_hash`, `post_merge_hash`, and `coverage`. Screen after the final host merge or verify that the presented hash equals the screened hash. A mismatch must fail closed for catalog exposure because otherwise raw text can be reintroduced after screening.

Reason codes should include `SCHEMA_DESC_CROSS_PURPOSE`, `SCHEMA_DESC_UNRELATED_DESTINATION`, `SCHEMA_DESC_ROLE_CHANGE`, `SCHEMA_POST_SCREEN_MERGE`, and `SCHEMA_PARTIAL_COVERAGE`. Keep the current pins and add new opt in tests rather than rewriting expectations.

## E. Failure modes and confounds

1. Post screen host merge restores unsafe raw annotations.
2. A recursive walker follows hostile references or consumes unbounded resources.
3. A benign messaging parameter is flagged because sending data is its declared purpose.
4. Field count is mistaken for independent corpus size.
5. Shadow findings leak into operator alerts and spend attention before promotion.
6. Truncation consistently excludes suffix fields, creating a predictable blind region.
7. Schema normalization changes validation semantics.

## F. Ethics and dual use

Use inert destinations and redacted payloads. Never resolve remote `$ref` values during import or screening. Never execute example commands or third party schema code. High risk examples remain private and require `CONFIRM_HIGH_RISK`.

## G. BACKLOG candidates, not ship line

1. Collect 400 source diverse benign parameter documents.
2. Study example field policy separately from description policy.
3. Add signed presented schema hashes to adapter contracts.
4. Evaluate multilingual parameter descriptions.

## H. Open questions Aditya must decide

1. Is the 1 percent gate a point estimate gate or an upper confidence bound gate? The latter needs a much larger corpus.
2. Can adapters expose the final post merge schema bytes for hash verification?
3. Should incomplete coverage alert the operator or only mark proof output?
4. Which annotation vendor extensions are in the first inventory?
