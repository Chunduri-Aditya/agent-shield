# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch>=2.4",
#   "transformers>=4.46",
#   "trl>=0.19",
#   "peft>=0.13",
#   "accelerate>=1.0",
#   "datasets>=3.0",
# ]
# ///
"""Diagnostic for the dpo_lora_spike generation collapse.

Separates two hypotheses for why post-training generations degenerated:
  A. likelihood displacement -- DPO suppressed the rejected (long, fluent)
     distribution and displaced mass onto EOS.
  B. device artifact -- BEFORE ran on CPU, AFTER ran on MPS with mismatched
     input_ids, so the comparison was confounded.

Everything here is pinned to CPU so device is no longer a free variable.
Reports, on identical device and identical decode settings:
  1. base model
  2. trained model, adapter ENABLED
  3. trained model, adapter DISABLED  (should match #1 if the adapter is the cause)
  4. P(EOS) at the first few generation positions, base vs trained
  5. raw token ids + stop reason, so "short output" is not confused with
     "truncated output"
"""

import json
from pathlib import Path

import torch
from datasets import Dataset
from dpo_lora_spike import MODEL_ID, PAIRS
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

DEVICE = torch.device("cpu")
OUT_DIR = Path(__file__).parent / "dpo_lora_spike_out"
OUT_DIR.mkdir(exist_ok=True)

EVAL_PROMPTS = [
    "What is the capital of Italy?",
    "What is 5 + 3?",
    "How many sides does a triangle have?",
    "Explain in a few sentences why the sky appears blue.",
]


def encode(tokenizer, prompt):
    out = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    return out["input_ids"].to(DEVICE)


def generate_verbose(model, tokenizer, prompt, max_new_tokens=48):
    """Greedy decode, reporting token ids and why generation stopped."""
    input_ids = encode(tokenizer, prompt)
    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    new_ids = out[0][input_ids.shape[1]:].tolist()
    text = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
    stop = "max_new_tokens" if len(new_ids) >= max_new_tokens else "eos"
    return {
        "text": text,
        "n_new_tokens": len(new_ids),
        "stop_reason": stop,
        "token_ids": new_ids[:12],
        "token_strs": [tokenizer.decode([t]) for t in new_ids[:12]],
    }


def eos_profile(model, tokenizer, prompt, n_steps=3):
    """P(EOS) and top-3 next tokens at the first n_steps greedy positions."""
    input_ids = encode(tokenizer, prompt)
    eos_ids = set()
    if tokenizer.eos_token_id is not None:
        eos_ids.add(tokenizer.eos_token_id)
    gc_eos = getattr(model.generation_config, "eos_token_id", None)
    if isinstance(gc_eos, int):
        eos_ids.add(gc_eos)
    elif isinstance(gc_eos, list):
        eos_ids.update(gc_eos)

    steps = []
    cur = input_ids
    with torch.no_grad():
        for _ in range(n_steps):
            logits = model(cur).logits[0, -1]
            probs = torch.softmax(logits.float(), dim=-1)
            p_eos = float(sum(probs[i].item() for i in eos_ids))
            top_p, top_i = torch.topk(probs, 3)
            steps.append({
                "p_eos": round(p_eos, 5),
                "top3": [
                    (tokenizer.decode([int(i)]), round(float(p), 4))
                    for p, i in zip(top_p, top_i, strict=True)
                ],
            })
            nxt = torch.argmax(probs).view(1, 1)
            cur = torch.cat([cur, nxt], dim=1)
    return {"eos_token_ids": sorted(eos_ids), "steps": steps}


def main():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("=== TOKENIZER / EOS CONFIG ===")
    print(f"eos_token={tokenizer.eos_token!r} id={tokenizer.eos_token_id}")
    print(f"pad_token={tokenizer.pad_token!r} id={tokenizer.pad_token_id}")

    # Length asymmetry in the preference data -- the suspected driver.
    ch_lens = [len(tokenizer(c).input_ids) for _, c, _, _ in PAIRS]
    rj_lens = [len(tokenizer(r).input_ids) for _, _, r, _ in PAIRS]
    print(f"chosen   tokens: mean={sum(ch_lens)/len(ch_lens):.1f} "
          f"min={min(ch_lens)} max={max(ch_lens)}")
    print(f"rejected tokens: mean={sum(rj_lens)/len(rj_lens):.1f} "
          f"min={min(rj_lens)} max={max(rj_lens)}")

    base = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).to(DEVICE)
    base.eval()

    print("\n=== 1. BASE MODEL (cpu) ===")
    base_gen = {}
    for p in EVAL_PROMPTS:
        r = generate_verbose(base, tokenizer, p)
        base_gen[p] = r
        print(f"[Q] {p}\n[A] {r['text']!r}  ({r['n_new_tokens']} tok, stop={r['stop_reason']})")

    print("\n=== BASE P(EOS) profile ===")
    base_eos = {p: eos_profile(base, tokenizer, p) for p in EVAL_PROMPTS[:2]}
    for p, prof in base_eos.items():
        print(f"[{p}] eos_ids={prof['eos_token_ids']}")
        for i, s in enumerate(prof["steps"]):
            print(f"   step{i}: P(eos)={s['p_eos']} top3={s['top3']}")

    # Retrain, pinned to CPU so no device change occurs mid-run.
    train_model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).to(DEVICE)
    dataset = Dataset.from_list(
        [{"prompt": p, "chosen": c, "rejected": r} for p, c, r, _ in PAIRS]
    )
    lora_config = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    dpo_config = DPOConfig(
        output_dir=str(OUT_DIR / "diag_checkpoints"),
        per_device_train_batch_size=2,
        num_train_epochs=6,
        learning_rate=5e-5,
        beta=0.1,
        max_length=128,
        logging_steps=10,
        report_to=[],
        remove_unused_columns=False,
        use_cpu=True,
        disable_tqdm=True,
    )
    trainer = DPOTrainer(
        model=train_model,
        ref_model=None,
        args=dpo_config,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=lora_config,
    )
    trainer.train()

    tuned = trainer.model
    tuned.eval()
    print(f"\ntuned model device: {next(tuned.parameters()).device}")

    print("\n=== 2. TRAINED, ADAPTER ENABLED (cpu) ===")
    tuned_gen = {}
    for p in EVAL_PROMPTS:
        r = generate_verbose(tuned, tokenizer, p)
        tuned_gen[p] = r
        print(f"[Q] {p}\n[A] {r['text']!r}  ({r['n_new_tokens']} tok, stop={r['stop_reason']})")

    print("\n=== 3. TRAINED, ADAPTER DISABLED (cpu) ===")
    disabled_gen = {}
    with tuned.disable_adapter():
        for p in EVAL_PROMPTS:
            r = generate_verbose(tuned, tokenizer, p)
            disabled_gen[p] = r
            print(f"[Q] {p}\n[A] {r['text']!r}  ({r['n_new_tokens']} tok, stop={r['stop_reason']})")

    print("\n=== 4. TRAINED P(EOS) profile ===")
    tuned_eos = {p: eos_profile(tuned, tokenizer, p) for p in EVAL_PROMPTS[:2]}
    for p, prof in tuned_eos.items():
        print(f"[{p}]")
        for i, s in enumerate(prof["steps"]):
            print(f"   step{i}: P(eos)={s['p_eos']} top3={s['top3']}")

    print("\n=== VERDICT INPUTS ===")
    same_as_base = all(
        disabled_gen[p]["text"] == base_gen[p]["text"] for p in EVAL_PROMPTS
    )
    collapsed = all(tuned_gen[p]["n_new_tokens"] <= 3 for p in EVAL_PROMPTS)
    print(f"adapter-disabled matches base : {same_as_base}")
    print(f"adapter-enabled collapsed(<=3 tok): {collapsed}")
    for p in EVAL_PROMPTS[:2]:
        print(
            f"P(eos) step0 base={base_eos[p]['steps'][0]['p_eos']} "
            f"tuned={tuned_eos[p]['steps'][0]['p_eos']}"
        )

    (OUT_DIR / "diagnosis.json").write_text(json.dumps({
        "chosen_tok_mean": sum(ch_lens) / len(ch_lens),
        "rejected_tok_mean": sum(rj_lens) / len(rj_lens),
        "base": base_gen,
        "tuned_adapter_on": tuned_gen,
        "tuned_adapter_off": disabled_gen,
        "base_eos": base_eos,
        "tuned_eos": tuned_eos,
        "adapter_disabled_matches_base": same_as_base,
        "adapter_enabled_collapsed": collapsed,
        "log_history": trainer.state.log_history,
    }, indent=2))
    print(f"\nWrote {OUT_DIR / 'diagnosis.json'}")


if __name__ == "__main__":
    main()
