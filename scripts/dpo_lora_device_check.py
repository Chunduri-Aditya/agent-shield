# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch>=2.4",
#   "transformers>=4.46",
#   "accelerate>=1.0",
# ]
# ///
"""Isolate Hypothesis B: does the CPU-inputs/MPS-model mismatch alone degenerate output?

No training involved. Untrained base model, three configurations:
  A. model cpu,  input_ids cpu   (matches the BEFORE block of the spike run)
  B. model mps,  input_ids mps   (correct MPS usage, control)
  C. model mps,  input_ids cpu   (reproduces the exact warning from the AFTER block)

If C degenerates while A and B do not, the spike's post-training collapse is a
measurement artifact and the training-effect conclusion is unsupported.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
PROMPTS = [
    "What is the capital of Italy?",
    "What is 5 + 3?",
    "How many sides does a triangle have?",
]


def run(model, tokenizer, input_device, label):
    print(f"\n=== {label} ===")
    print(f"model device: {next(model.parameters()).device}")
    for prompt in PROMPTS:
        enc = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        input_ids = enc["input_ids"].to(input_device)
        with torch.no_grad():
            out = model.generate(
                input_ids,
                max_new_tokens=40,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        new_ids = out[0][input_ids.shape[1]:]
        text = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        print(f"[Q] {prompt}\n[A] {text!r}  ({len(new_ids)} tok)")


def main():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"mps available: {torch.backends.mps.is_available()}")

    m_cpu = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32)
    m_cpu.eval()
    run(m_cpu, tokenizer, torch.device("cpu"), "A. model=cpu  inputs=cpu  (BEFORE-block config)")

    if not torch.backends.mps.is_available():
        print("\nMPS unavailable, cannot test B/C on this machine.")
        return

    m_mps = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).to("mps")
    m_mps.eval()
    run(m_mps, tokenizer, torch.device("mps"), "B. model=mps  inputs=mps  (correct MPS control)")
    run(m_mps, tokenizer, torch.device("cpu"), "C. model=mps  inputs=cpu  (AFTER-block config)")


if __name__ == "__main__":
    main()
