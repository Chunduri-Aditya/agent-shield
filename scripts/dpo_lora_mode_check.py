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
"""Isolate Hypothesis C: was the spike's collapse caused by generating in train() mode?

dpo_lora_spike.py calls trainer.train() and then generates from trainer.model
without ever calling .eval(). That leaves LoRA dropout (p=0.05) active and
gradient checkpointing on during greedy decoding.

Trains once on the default device (MPS, matching the original spike run), then
decodes the SAME adapter under four conditions:
  1. train() mode                    -- reproduces the spike exactly
  2. eval() mode                     -- the fix
  3. train() mode, dropout forced 0  -- isolates dropout from checkpointing
  4. train() mode again              -- shows run-to-run nondeterminism if dropout is the cause

If 1 degenerates and 2 does not, the collapse is a decode-time bug, not a
training result.
"""

import json
from pathlib import Path

import torch
import torch.nn as nn
from datasets import Dataset
from dpo_lora_spike import MODEL_ID, PAIRS
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

OUT_DIR = Path(__file__).parent / "dpo_lora_spike_out"
OUT_DIR.mkdir(exist_ok=True)

EVAL_PROMPTS = [
    "What is the capital of Italy?",
    "What is 5 + 3?",
    "How many sides does a triangle have?",
]


def generate(model, tokenizer, prompt, max_new_tokens=40):
    device = next(model.parameters()).device
    enc = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    input_ids = enc["input_ids"].to(device)
    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    new_ids = out[0][input_ids.shape[1]:]
    return {
        "text": tokenizer.decode(new_ids, skip_special_tokens=True).strip(),
        "n_new_tokens": len(new_ids),
    }


def sweep(model, tokenizer, label):
    n_training = sum(1 for m in model.modules() if m.training)
    n_dropout_active = sum(
        1 for m in model.modules() if isinstance(m, nn.Dropout) and m.training and m.p > 0
    )
    print(f"\n=== {label} ===")
    print(f"model.training={model.training} | modules in train mode={n_training} "
          f"| active dropout modules={n_dropout_active}")
    results = {}
    for p in EVAL_PROMPTS:
        r = generate(model, tokenizer, p)
        results[p] = r
        print(f"[Q] {p}\n[A] {r['text']!r}  ({r['n_new_tokens']} tok)")
    return {"generations": results, "modules_in_train_mode": n_training,
            "active_dropout_modules": n_dropout_active}


def main():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32)
    dataset = Dataset.from_list(
        [{"prompt": p, "chosen": c, "rejected": r} for p, c, r, _ in PAIRS]
    )
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=DPOConfig(
            output_dir=str(OUT_DIR / "mode_checkpoints"),
            per_device_train_batch_size=2,
            num_train_epochs=6,
            learning_rate=5e-5,
            beta=0.1,
            max_length=128,
            logging_steps=30,
            report_to=[],
            remove_unused_columns=False,
            disable_tqdm=True,
        ),
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=8, lora_alpha=16, lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    trainer.train()
    tuned = trainer.model
    print(f"\ndevice after training: {next(tuned.parameters()).device}")
    print(f"model.training immediately after trainer.train(): {tuned.training}")

    out = {}
    # 1. Exactly what the spike did: no .eval() call.
    out["1_train_mode"] = sweep(tuned, tokenizer, "1. train() mode -- reproduces the spike")

    # 2. The fix.
    tuned.eval()
    out["2_eval_mode"] = sweep(tuned, tokenizer, "2. eval() mode -- the fix")

    # 3. train() mode but dropout neutralized, to separate dropout from checkpointing.
    tuned.train()
    for m in tuned.modules():
        if isinstance(m, nn.Dropout):
            m.p = 0.0
    out["3_train_mode_no_dropout"] = sweep(
        tuned, tokenizer, "3. train() mode, dropout p=0 -- isolates dropout"
    )

    # 4. Restore dropout, decode again: nondeterminism is itself evidence.
    for m in tuned.modules():
        if isinstance(m, nn.Dropout):
            m.p = 0.05
    out["4_train_mode_again"] = sweep(
        tuned, tokenizer, "4. train() mode again -- greedy decode should NOT vary if deterministic"
    )

    print("\n=== VERDICT INPUTS ===")
    t1 = out["1_train_mode"]["generations"]
    t2 = out["2_eval_mode"]["generations"]
    t3 = out["3_train_mode_no_dropout"]["generations"]
    t4 = out["4_train_mode_again"]["generations"]
    print(f"train-mode collapsed (all <=4 tok) : "
          f"{all(v['n_new_tokens'] <= 4 for v in t1.values())}")
    print(f"eval-mode collapsed  (all <=4 tok) : "
          f"{all(v['n_new_tokens'] <= 4 for v in t2.values())}")
    print(f"train-no-dropout == eval-mode      : "
          f"{all(t3[p]['text'] == t2[p]['text'] for p in EVAL_PROMPTS)}")
    print(f"train run1 == train run2 (determinism): "
          f"{all(t1[p]['text'] == t4[p]['text'] for p in EVAL_PROMPTS)}")

    (OUT_DIR / "mode_check.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_DIR / 'mode_check.json'}")


if __name__ == "__main__":
    main()
