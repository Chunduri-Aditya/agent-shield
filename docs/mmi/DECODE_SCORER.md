# mmi_decode scorer fields

`mmi_decode` (`evals/mmi_controls.py`) asks which sentence an icon chain expresses, with four lettered options, and then asks the model to name each icon alone. The `decode_correct` scorer reports two readings of the chain answer.

## Strict reading

- The score value, `chosen`, `icons_named`, `icons_all_named`, `icon_answers` and `image_channel` come from `parse_letter`.
- `parse_letter` accepts a leading letter token or the words "answer is X", "answer: X" or "option X". An answer it cannot read counts as unparsed and scores 0.
- The strict fields have not changed since the task was added. Every strict count in this repo uses them.

## Lenient reading

- `chosen_lenient` and `correct_lenient` come from `parse_letter_lenient`. The strict letter wins when it exists. Otherwise the last match in the answer wins, among three forms: a line that holds only the letter, a bold letter, or a line that starts with the letter and then holds the exact sentence shown for that letter.
- The lenient fields are a declared scorer for every `mmi_decode` run whose log records a commit that contains `78a9c1a`. For those runs both readings are reported side by side.
- A known risk: if a model repeats all four options as lines, the last option line wins, whatever the model chose. Read the answers where the two readings differ before you trust a lenient count.

## Post hoc label

The lenient reading of a log made before `78a9c1a` is computed afterwards by `decode_rows_lenient`, and it carries the label "post hoc". Only these local logs are in that group:

| Model | Log | Samples |
|---|---|---|
| ollama/qwen3-vl:8b | `2026-11-26T03-00-46-00-00_mmi-decode_ollama-qwen3-vl-8b_SMOKE-ONLY_Lrmz8PZWZzBVXpU7aQinek.eval` | 5 |
| ollama/qwen3-vl:8b | `2026-11-26T19-29-46-00-00_mmi-decode_ollama-qwen3-vl-8b_SMOKE-ONLY-BALANCED_iYHt5o6rYNdef28vNBgstb.eval` | 10 |
| ollama/qwen3-vl:8b | `2026-11-26T20-04-02-00-00_mmi-decode_3qyAuYqYAadYL2htJgkQ6d.eval` | 20 |
| ollama/gemma4:12b | `2026-11-26T20-25-06-00-00_mmi-decode_7Zpmk9iwj48MQyxsw6PtBs.eval` | 20 |

The two smoke logs are smoke runs only. No result row comes from them.
