# 12 — Corpus Provenance and Dual Use Ethics Findings

Status: governance and importer design, not legal advice. Current manifest decisions remain binding: only approved sources at pinned commits enter Phase 1; missing license and PolyForm Shield sources remain blocked until explicit permission or a new legal basis is recorded.

Local evidence basis: [research prompt](../research_prompts/12_corpus_provenance_dual_use.md), [source manifest](../research_packages/2026-07-31_external_benchmark/agent_shield_test_source_manifest.json), [acquisition plan](../research_packages/2026-07-31_external_benchmark/agent_shield_external_test_acquisition_plan.md), and [ethics controls](../../ETHICS.md).

## A. Psychology and organizational ethics primary sources, ranked

1. Tenbrunsel and Messick describe ethical fading, where decision framing can move moral dimensions out of attention. This supports forcing ethics fields into the normal importer workflow rather than a final optional review. [DOI 10.1023/B:SORE.0000027411.35832.53](https://doi.org/10.1023/B:SORE.0000027411.35832.53).
2. Bandura and colleagues describe diffusion and displacement of responsibility, euphemistic labeling, and consequence distortion as mechanisms of moral disengagement. This supports named human approval and explicit harm fields. [DOI 10.1037/0022-3514.71.2.364](https://doi.org/10.1037/0022-3514.71.2.364).
3. Merritt, Effron, and Monin review moral self licensing and competing explanations for it. This supports a checklist warning that attribution or an open license does not settle content safety. [DOI 10.1111/j.1751-9004.2010.00263.x](https://doi.org/10.1111/j.1751-9004.2010.00263.x).
4. Monin and Miller’s original moral credentials experiments found increased willingness to express potentially prejudiced preferences after establishing credentials. A recent registered replication failed to reproduce a central study, so the effect should be treated as a cautionary hypothesis rather than a fixed law. [Original DOI 10.1037/0022-3514.81.1.33](https://doi.org/10.1037/0022-3514.81.1.33), [registered replication](https://pmc.ncbi.nlm.nih.gov/articles/PMC12372676/).

## B. Cybersecurity, provenance, and data documentation primary sources, ranked

1. in toto provides cryptographically verifiable software supply chain layouts and link metadata, supporting append only provenance and hash bound transformations. [USENIX Security 2019](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias).
2. SLSA provenance defines attestations about where, when, and how artifacts were produced. Its concepts transfer to corpus adapters, though Agent Shield is not claiming SLSA conformance. [SLSA v1.2 provenance](https://slsa.dev/spec/v1.2/provenance).
3. SPDX 3.0.1 includes datasets, AI models, provenance, integrity, licenses, copyrights, and relationships in its system package data model. [SPDX 3.0.1](https://spdx.github.io/spdx-spec/).
4. Datasheets for Datasets proposes documentation of motivation, composition, collection, use, and distribution. [DOI 10.1145/3458723](https://doi.org/10.1145/3458723).
5. The Apache License 2.0 text imposes conditions on reproduction and distribution, including license and NOTICE handling where applicable. The exact upstream files and obligations must be inspected rather than inferred from a repository badge. [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
6. NIST SSDF provides secure development practices across software lifecycle activities, supporting review, protection, and response controls around importers. [NIST SP 800 218](https://csrc.nist.gov/pubs/sp/800/218/final).
7. Carlini and colleagues demonstrate practical attacks on mutable web scale dataset sources, supporting immutable snapshots and content hashes rather than future URL refetches. [arXiv 2302.10149](https://arxiv.org/abs/2302.10149).

## C. MERGE — paste ready ethics and provenance checklist

### Case admission checklist

Every imported case must have all required fields before it can appear in a results table.

| Control | Required record | Stop if absent? |
|---|---|---:|
| Identity | `case_id`, `source_id`, `source_case_id`, source repo, HTTPS URL, commit, path | Yes |
| Acquisition | retrieval time, retrieval method, retriever version, response status, raw byte length | Yes |
| Integrity | raw SHA256, canonical SHA256, canonicalization version | Yes |
| License | exact license file path and hash, SPDX expression if known, copyright holder, NOTICE presence and obligations | Yes |
| Transformation | adapter name and version, parent hash, deterministic seed, transform IDs, output hash | Yes |
| Evidence lane | public replay, deterministic mutation, adaptive, benign control, or frozen holdout | Yes |
| Deduplication | exact duplicate status, normalized duplicate status, semantic cluster ID and reviewer | Yes |
| Content safety | risk tier, secret scan, personal data review, toxic content review, live target review, executable content review | Yes |
| Purpose | research question, allowed use, prohibited use, expected metric, release audience | Yes |
| Approval | decision, named human approver, time, reason, prior decision link | Yes |
| Release | public, restricted, metric only, or rejected; redaction version and export hash | Yes |
| History | append only events for discovered, blocked, approved, transformed, superseded, and released | Yes |

### Import procedure

1. Discover the source and log it before access under the approved resource rule.
2. Fetch only over HTTPS at the exact approved commit or immutable artifact reference.
3. Store bytes as data. Do not import packages, run setup scripts, execute tests, open notebooks, render active HTML, resolve remote references, or follow repository automation.
4. Hash raw bytes before parsing.
5. Inspect repository and file level license evidence plus NOTICE. A homepage badge or manifest string alone is insufficient.
6. Parse with a nonexecuting, bounded reader. Treat archives as hostile and enforce file count, path, size, nesting, and expansion limits.
7. Run exact hash deduplication before any semantic process.
8. Apply the versioned deterministic adapter and hash its output.
9. Screen content for secrets, personal data, live targets, harmful executables, and dual use risk.
10. Assign lane and semantic cluster. Public replay stays public replay.
11. Obtain the required human decision. HIGH rows require Aditya’s explicit `CONFIRM_HIGH_RISK`; an automated check cannot grant it.
12. Export only the permitted representation and bind it to its source, adapter, and decision history.

### Stop conditions

Stop import or promotion when any of these is true:

1. No license, ambiguous file level license, incompatible redistribution term, or unresolved NOTICE obligation.
2. Source is PolyForm Shield or another restricted license without recorded permission for the intended use.
3. URL is HTTP only, redirects to HTTP, or the approved immutable reference cannot be obtained.
4. Commit, path, raw hash, archive member hash, or signature differs from the approved manifest.
5. Access requires credentials, a paid model run, personal account action, or acceptance of new terms not reviewed.
6. Parsing requires third party code execution, package installation from the source, macro execution, notebook execution, or network callbacks.
7. Archive has path traversal, links outside the extraction root, excessive expansion, unexpected binaries, or nested archives beyond the fixed limit.
8. Content includes real credentials, personal data without a lawful and ethical basis, live vulnerable targets, malware, or an unredactable transferable attack chain.
9. Source case provenance is missing or upstream origin is unclear.
10. Exact duplicate conflicts with a different label or license and the conflict is unresolved.
11. HIGH dual use content lacks explicit human approval.
12. The proposed public release exceeds the upstream license, consent, or recorded purpose.

### Approved with attribution is not a safety decision

`approved_with_attribution` means the current license and provenance review permits the intended import subject to recorded obligations. It does not authorize live execution, public release of toxic or personal content, redistribution of malware, publication of reusable exploits, or paid inference. Content safety and release decisions remain separate gates.

### Blocked source upgrade without history rewriting

Append a new decision event referencing the blocked event. Record permission text or new license bytes, their hashes, scope, signer, date, and intended use. Re run acquisition and content review from the newly approved immutable reference. Never edit the earlier blocked event. If permission covers research but not redistribution, set `release=restricted` and preserve that constraint downstream.

### Separation of duties for one human contributor

Agent Shield cannot claim true two person separation while Aditya is the sole human contributor. Use explicit single contributor compensating controls:

1. Automation may prepare hashes, diffs, and checklist failures but cannot approve HIGH content.
2. Aditya records a first review, then performs a fresh context final approval against immutable hashes after a cooling interval or separate session.
3. A read only independent review may identify omissions, but authorship and approval remain Aditya’s.
4. HIGH public release should obtain an external human ethics or legal review when feasible; until then it remains restricted.
5. The importer author cannot make the approval implicit through a code merge. A separate signed decision record is required.

### Paste ready policy text

> External benchmark material is untrusted data. Agent Shield imports only explicitly approved HTTPS sources at pinned immutable revisions. Importers never execute third party code, macros, notebooks, setup scripts, or fetched content, and never require paid model runs. Every admitted case records repository, commit, path, exact license evidence, NOTICE obligations, raw and canonical SHA256, adapter version, parent lineage, evidence lane, duplicate status, semantic cluster, content risk, human decision, and release scope. Exact deduplication precedes semantic processing. Open licensing does not waive privacy, dual use, malware, live target, attribution, or ethical review. Missing or ambiguous evidence stops promotion. Blocked decisions remain append only and can be superseded only by a new hash bound approval event. HIGH risk rows require Aditya’s explicit confirmation and default to restricted release.

## D. Operationalization for Agent Shield

The manifest should use event sourced decisions rather than a mutable status alone. Minimum objects: `source`, `artifact`, `case`, `transform`, `review`, `decision`, `release`, and `supersedes`. Each object gets a stable ID and content hash. Results rows reference the admitted case decision ID, not just the source name.

Phase 1 remains the pinned doronp and Evalyze sources only. Preserve per source results and do not sum overlapping Evalyze versions. The MIT business seed stays citation only unless a later import decision is recorded. Blocked missing license and PolyForm sources remain absent from import code and aggregates.

## E. Failure modes and confounds

1. Repository level Apache labeling hides differently licensed files.
2. A mutable branch is recorded instead of a commit.
3. Canonicalization removes meaningful attack differences or license notices.
4. Deduplication occurs after mutation, inflating apparent source diversity.
5. A clean hash proves integrity of malicious bytes, not safety.
6. Automated scanners miss contextual personal data or dual use harm.
7. A blocked row is deleted after approval and the audit history disappears.
8. An importer library evaluates constructors or custom tags while “parsing.”
9. An open license is treated as consent for all public redistribution.
10. Independent review is claimed when only automated checks ran.

## F. Ethics and dual use

Prefer case metrics, labels, hashes, and redacted evidence over full harmful text. Public artifacts exclude live endpoints, secrets, personal data, malware, and executable attack chains. This workflow does not replace legal advice. Ambiguity is a stop condition, not a reason to infer permission.

## G. BACKLOG candidates, not ship line

1. Event sourced corpus manifest with signed decisions.
2. Bounded archive and parser conformance suite.
3. SPDX compatible export for dataset and license metadata.
4. External human review path for HIGH public releases.
5. Permission request template for blocked sources.

## H. Open questions Aditya must decide

1. What cooling interval or separate session qualifies for final single contributor approval?
2. Which HIGH categories are categorically nonredistributable?
3. Is an SPDX compatible export worth maintaining before Phase 1 importers exist?
4. Who can provide external legal or ethics review when license or release scope remains ambiguous?
