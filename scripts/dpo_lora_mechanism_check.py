# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch>=2.4",
#   "transformers>=4.46",
#   "accelerate>=1.0",
# ]
# ///
"""Pin the mechanism behind the train()-mode decode collapse.

mode_check proved: same adapter, train() mode collapses, eval() mode does not,
dropout is NOT the cause (p=0 still collapses), and it is deterministic.
The remaining suspect is gradient checkpointing forcing use_cache=False.

This uses the UNTRAINED base model -- no DPO, no LoRA -- so if the collapse
reproduces, it is a decode-time interaction with gradient checkpointing that
has nothing to do with preference training at all.

Also dumps raw token ids, because 'The' decoded from 40 generated tokens is a
very different failure than generation stopping after 1 token.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
PROMPT = "What is the capital of Italy?"


def gen(model, tokenizer, label, max_new_tokens=20):
    device = next(model.parameters()).device
    enc = tokenizer.apply_chat_template(
        [{"role": "user", "content": PROMPT}],
        add_generation_prompt=True, return_tensors="pt", return_dict=True,
    )
    input_ids = enc["input_ids"].to(device)
    with torch.no_grad():
        out = model.generate(
            input_ids, max_new_tokens=max_new_tokens,
            do_sample=False, pad_token_id=tokenizer.pad_token_id,
        )
    new_ids = out[0][input_ids.shape[1]:].tolist()
    print(f"\n--- {label} ---")
    print(f"training={model.training} "
          f"gc={getattr(model, 'is_gradient_checkpointing', 'n/a')} "
          f"use_cache={model.config.use_cache}")
    print(f"n_new={len(new_ids)}")
    print(f"ids   = {new_ids}")
    print(f"toks  = {[tokenizer.decode([t]) for t in new_ids]}")
    print(f"skip_special=True  -> {tokenizer.decode(new_ids, skip_special_tokens=True)!r}")
    print(f"skip_special=False -> {tokenizer.decode(new_ids, skip_special_tokens=False)!r}")


def main():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    print(f"eos_token_id={tokenizer.eos_token_id} pad_token_id={tokenizer.pad_token_id}")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).to(device)

    model.eval()
    gen(model, tokenizer, "base, eval(), cache on  [control]")

    model.train()
    gen(model, tokenizer, "base, train(), cache on  [train mode alone]")

    model.eval()
    model.gradient_checkpointing_enable()
    gen(model, tokenizer, "base, eval(), gradient checkpointing ON")

    model.train()
    gen(model, tokenizer, "base, train(), gradient checkpointing ON  [spike config]")


if __name__ == "__main__":
    main()
