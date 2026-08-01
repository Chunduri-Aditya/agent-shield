# 08 — Encoding and Structure Evasion Findings

Status: defensive measurement plan. The report intentionally omits exact encoded TL01 payloads and executable bypass sequences.

Local evidence basis: [aggressive runtime findings](../../runtime_aggressive_testing_research.md) and [ethics controls](../../../ETHICS.md).

## A. Psychology and HCI primary sources, ranked

1. Mack and Rock establish inattentional blindness under focused attention. The transfer hypothesis is that encoded or peripheral content can evade scrutiny when the task is directed elsewhere. ISBN 9780262133395, [MIT Press](https://mitpress.mit.edu/9780262133395/inattentional-blindness/).
2. Simons and Chabris show that unexpected visible events may be missed during a demanding task. [DOI 10.1068/p281059](https://doi.org/10.1068/p281059).
3. Reber and Schwarz show that processing fluency can influence judged truth, supporting a testable hypothesis that familiar technical wrappers may receive unearned trust. [DOI 10.1006/ccog.1999.0386](https://doi.org/10.1006/ccog.1999.0386).
4. Dhamija, Tygar, and Hearst found that many users failed to identify phishing indicators even when the relevant cues were visible, supporting caution around visual similarity and confusable text. [DOI 10.1145/1124772.1124861](https://doi.org/10.1145/1124772.1124861).

## B. Cybersecurity and agent security primary sources, ranked

1. Unicode Technical Standard 39 defines confusable detection and security mechanisms for Unicode identifiers, directly relevant to homoglyph normalization. [UTS 39](https://unicode.org/reports/tr39/).
2. Unicode Technical Report 36 catalogs Unicode security considerations, including visual spoofing and mixed script risks. [UTR 36](https://www.unicode.org/reports/tr36/tr36-15.html).
3. Trojan Source demonstrates that Unicode control characters can make source display differ from logical ordering, providing a strong precedent for canonical display and control character logging. [USENIX Security 2023](https://www.usenix.org/conference/usenixsecurity23/presentation/boucher).
4. RFC 4648 defines Base16, Base32, and Base64 encodings. It does not prescribe recursive security decoding. [RFC 4648](https://datatracker.ietf.org/doc/html/rfc4648).
5. Lost in the Middle shows that language models can perform worse when relevant information is placed in the middle of long contexts, supporting placement controlled suffix tests. [DOI 10.1162/tacl_a_00638](https://aclanthology.org/2024.tacl-1.9/).
6. ArtPrompt demonstrates that nonstandard visual text representations can bypass safety alignment in tested models, supporting representation diversity in defense evaluation. [arXiv 2402.11753](https://arxiv.org/abs/2402.11753).

## C. MERGE — D1 through D5 prioritization and safe test design

### Ranking method

Each dimension is scored 1 through 3. `Attacker value` estimates transfer and ease of placing the representation. `Defender FP risk` estimates harm from automatic normalization or screening. `Overlook probability` is a research hypothesis grounded in salience, visual similarity, or context position. The product score is a prioritization aid, not an empirical result.

| Risk product rank | Family | Attacker value | Defender FP risk | Overlook probability | Product | Phase 1 action priority | Phase decision |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | D1 Base64, hexadecimal, or URL wrapper | 3 | 3 | 3 | 27 | 3 | Preserve the Base64 miss pin; bounded decoding stays BACKLOG until limits pass |
| 2 | D5 empty description plus schema poison | 3 | 2 | 3 | 18 | 2 | Add a known miss pin now; gate any fix through F5 schema research |
| 3 | D4 poison in tool name | 2 | 3 | 2 | 12 | 5 | Add a diagnostic miss pin; tool name screening requires a separate FP study |
| 4 | D3 long benign prefix plus short poison suffix | 3 | 1 | 3 | 9 | 1 | Measure now; add catch and miss pins across length and position |
| 5 | D2 JSON Unicode escapes and confusables | 2 | 2 | 2 | 8 | 4 | Test canonical parser boundaries now; normalize safe Unicode forms only |

The risk product is ranked in descending order exactly as displayed. It measures combined research difficulty because high attacker value, high defensive FP cost, and high overlook probability all increase risk. Phase 1 action priority is separate: D1 scores highest overall risk but is not the safest immediate detector expansion, while D3 has high attacker value and low defensive cost and is therefore the first measurement target.

### Family decisions

#### D1 — encoded wrappers

Keep a permanent miss pin for the known Base64 description case. Add nonpayload fixtures that confirm common encoded identifiers remain benign. Do not recursively decode arbitrary text. A future decoder must cap input length, output length, expansion ratio, nesting depth, decode attempts, character set, and time. It must screen decoded content without executing or fetching it.

#### D2 — Unicode escapes and visual confusables

Test at three boundaries: raw transport bytes, parsed JSON string, and normalized display string. JSON escapes should normally resolve during parsing; a detector that only inspects raw syntax may miss the semantic text. Record format control characters and mixed script confusables. Preserve raw hash and normalized hash. Never silently rewrite tool identifiers because normalization collisions can change semantics.

#### D3 — long context placement

Create the same redacted poison at beginning, middle, and suffix positions within benign text drawn from the same parent. Vary total length by preregistered buckets below, near, and above scan budgets. Record bytes scanned and omitted ranges. This is a placement test, not a new attack family count. Catch pins cover content within the declared scan region; miss pins cover known truncation or coverage failures.

#### D4 — tool name poison

Tool names are identifiers and commonly contain verbs, namespaces, acronyms, and vendor strings. Broad prose rules would have high FP risk and normalization might break routing. Preserve a diagnostic miss pin with an inert name. Defer screening, renaming, or rejection to a dedicated corpus study.

#### D5 — schema only poison

Keep description empty and place only a redacted semantic marker in an approved schema description fixture. The current expected result remains a miss. Any change belongs to `AGENT_SHIELD_SCREEN_SCHEMA=1` and must pass the schema locus false positive gate. Do not quietly make description scanning recurse into schemas.

### Ingress versus exfiltration claim boundary

Ingress evasion asks whether untrusted encoded content bypasses the perimeter and influences the agent. The existing `exfil/` work asks whether data leaves through an encoded covert channel. A case may involve both, but the report must record separate source, sink, attack predicate, and metric. One episode cannot be counted as two independent cases merely because both transformations appear.

### Public artifact safety

Publish transform identifiers, hashes, lengths, expected catch or miss status, and redacted semantic labels. Keep exact decoded attack text private. A test generator may operate only on inert placeholders and must never emit live endpoints, secrets, executable commands, or target specific sequences.

## D. Operationalization for Agent Shield

Add `representation_family`, `raw_sha256`, `parsed_sha256`, `normalized_sha256`, `decode_attempted`, `decode_layers`, `decoded_chars`, `unicode_scripts`, `format_controls`, `content_position`, `total_chars`, `scanned_ranges`, and `coverage_complete`.

Phase 1 additions: D3 placement pins, D2 parser boundary pins, D1 Base64 known miss, D4 name known miss, and D5 schema known miss. None changes runtime policy. Each pin states whether it is a security expectation, a known gap, or a coverage assertion.

## E. Failure modes and confounds

1. Decode before screen expands compressed or nested input into a resource exhaustion attack.
2. Normalization creates identifier collisions.
3. Test cases retain other canonical markers, making the intended evasion appear detected.
4. Long prefix tests exceed a harness cap and never reach the model.
5. Generated encoded fixtures accidentally contain transferable content.
6. A parser automatically decodes escapes, so “evasion” exists only in the raw log and not model input.
7. A miss pin becomes obsolete but remains described as current without version binding.

## F. Ethics and dual use

No bypass cookbook, live endpoint, credential, or executable sequence appears in public files. Full high risk fixtures require `CONFIRM_HIGH_RISK`, private storage, and redacted exports. Decoders never execute, import, or fetch decoded material.

## G. BACKLOG candidates, not ship line

1. Bounded single layer decoding experiment for D1.
2. Tool name benign corpus and collision study.
3. Script aware confusable policy for display only.
4. Scan coverage proofs for very long tool results and schemas.

## H. Open questions Aditya must decide

1. Is any automatic decoding acceptable in product mode?
2. What scan coverage guarantee applies above the current character cap?
3. May Unicode normalization affect only detection and display, never routing?
4. Which known misses are public versus private?
