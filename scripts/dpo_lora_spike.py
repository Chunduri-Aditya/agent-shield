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
"""DPO + LoRA spike. Not a permanent module -- see BACKLOG.md.

Trains a LoRA adapter with DPO to prefer direct answers over hedged ones, on a
small instruct model.

Two decode-time bugs from the first version of this script are fixed here, and
both are now guarded rather than merely corrected:

FIX 1 -- generate in eval() mode.
    `trainer.train()` leaves the model in train() mode with gradient
    checkpointing on, which forces use_cache=False and breaks incremental
    decoding: output degenerates to one token followed by newlines forever.
    That reproduces on the UNTRAINED base model, so it was never a training
    result. `_assert_decode_ready` refuses to generate in that state.

FIX 2 -- report raw tokens, never stripped text.
    The original reported `.strip()`ed text, which rendered 40 generated
    newline tokens as the string 'The' and made a decode bug look like brevity
    collapse. Generations now carry token ids, count, and stop reason.

Scoring is deterministic and lives in Python, not in a judgment call: held-out
preference accuracy and the implicit DPO reward margin are computed from
log-probabilities, because a nudge too small to change a greedy decode is
still a real effect and must be measurable.
"""

import argparse
import json
import time
from pathlib import Path

import torch
from datasets import Dataset
from dpo_pairs import AXES, TRAIN_PAIRS, answer_present, hedge_count, validate_pairs
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
OUT_DIR = Path(__file__).parent / "dpo_lora_spike_out"
OUT_DIR.mkdir(exist_ok=True)

# Kept so the earlier diagnostic scripts, which import PAIRS, still run.
PAIRS = TRAIN_PAIRS


def _assert_decode_ready(model):
    """FIX 1 guard. Refuse to decode from a model left in training state."""
    if model.training:
        raise RuntimeError(
            "model is in train() mode; call .eval() before generating. "
            "Decoding in train mode with gradient checkpointing yields "
            "one token followed by endless newlines."
        )
    if getattr(model, "is_gradient_checkpointing", False):
        raise RuntimeError(
            "gradient checkpointing is still enabled; it forces use_cache=False "
            "and breaks incremental decoding. Call gradient_checkpointing_disable()."
        )


def encode_prompt(tokenizer, prompt, device):
    enc = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    return enc["input_ids"].to(device)


def generate(model, tokenizer, prompt, max_new_tokens=48):
    """FIX 2. Returns raw token evidence alongside the decoded text."""
    _assert_decode_ready(model)
    device = next(model.parameters()).device
    input_ids = encode_prompt(tokenizer, prompt, device)
    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
    new_ids = out[0][input_ids.shape[1]:].tolist()
    text = tokenizer.decode(new_ids, skip_special_tokens=True)
    return {
        "text": text.strip(),
        "text_raw": tokenizer.decode(new_ids, skip_special_tokens=False),
        "n_new_tokens": len(new_ids),
        "stop_reason": "max_new_tokens" if len(new_ids) >= max_new_tokens else "eos",
        "token_ids": new_ids,
        "hedge_markers": hedge_count(text),
    }


def seq_logprob(model, tokenizer, prompt, response):
    """Total and per-token log-probability of `response` given `prompt`."""
    device = next(model.parameters()).device
    prompt_ids = encode_prompt(tokenizer, prompt, device)
    resp_ids = tokenizer(response, add_special_tokens=False, return_tensors="pt")[
        "input_ids"
    ].to(device)
    full = torch.cat([prompt_ids, resp_ids], dim=1)
    with torch.no_grad():
        logits = model(full).logits
    logprobs = torch.log_softmax(logits.float(), dim=-1)
    n_prompt = prompt_ids.shape[1]
    # Token at position i is predicted by the logits at position i-1.
    idx = full[0, n_prompt:]
    lp = logprobs[0, n_prompt - 1 : full.shape[1] - 1, :].gather(1, idx.unsqueeze(1))
    total = float(lp.sum())
    return total, total / max(1, idx.shape[0])


def preference_metrics(model, tokenizer, pairs, ref_scores=None):
    """Deterministic scoring. Accuracy plus the implicit DPO reward margin.

    ref_scores: per-pair (chosen, rejected) logprobs from the reference model.
    When supplied, the implicit reward margin is
        (lp_policy_chosen - lp_ref_chosen) - (lp_policy_rejected - lp_ref_rejected)
    which is the quantity DPO actually optimizes.
    """
    rows, correct, margins = [], 0, []
    for i, (prompt, chosen, rejected, _key) in enumerate(pairs):
        lp_c, mean_c = seq_logprob(model, tokenizer, prompt, chosen)
        lp_r, mean_r = seq_logprob(model, tokenizer, prompt, rejected)
        # Length-normalized comparison: raw sums favour whichever side is shorter.
        is_correct = mean_c > mean_r
        correct += int(is_correct)
        row = {
            "prompt": prompt,
            "lp_chosen": lp_c,
            "lp_rejected": lp_r,
            "mean_lp_chosen": mean_c,
            "mean_lp_rejected": mean_r,
            "correct": is_correct,
        }
        if ref_scores is not None:
            rc, rr = ref_scores[i]
            margin = (lp_c - rc) - (lp_r - rr)
            margins.append(margin)
            row["implicit_reward_margin"] = margin
        rows.append(row)

    out = {
        "n": len(pairs),
        "preference_accuracy": correct / len(pairs),
        "rows": rows,
        "raw_scores": [(r["lp_chosen"], r["lp_rejected"]) for r in rows],
    }
    if margins:
        out["mean_implicit_reward_margin"] = sum(margins) / len(margins)
        out["margin_positive_rate"] = sum(1 for m in margins if m > 0) / len(margins)
    return out


def generation_metrics(model, tokenizer, pairs):
    """Generation-side scoring, with the anti-degeneration anchor.

    On the verbosity axis, shorter output is the goal, so length alone cannot
    be the score: a model that answers "The." is maximally concise and useless.
    `answer_key_rate` is the counterweight. Length falling while answer_key_rate
    also falls is degeneration, not concision.
    """
    gens = {}
    for prompt, _, _, key in pairs:
        g = generate(model, tokenizer, prompt)
        g["answer_key"] = key
        g["answer_key_present"] = answer_present(key, g["text"])
        gens[prompt] = g
    lengths = [g["n_new_tokens"] for g in gens.values()]
    hedges = [g["hedge_markers"] for g in gens.values()]
    degenerate = sum(
        1 for g in gens.values() if len(set(g["token_ids"][1:])) <= 1 and g["n_new_tokens"] > 5
    )
    return {
        "generations": gens,
        "mean_new_tokens": sum(lengths) / len(lengths),
        "mean_hedge_markers": sum(hedges) / len(hedges),
        "answer_key_rate": sum(g["answer_key_present"] for g in gens.values()) / len(gens),
        "degenerate_outputs": degenerate,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", choices=sorted(AXES), default="verbosity")
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--epochs", type=float, default=6)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--tag", default="baseline")
    ap.add_argument(
        "--mlp", action="store_true", help="also adapt the MLP projections"
    )
    args = ap.parse_args()

    train_pairs, heldout_pairs = AXES[args.axis]

    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"=== DATASET VALIDATION (axis={args.axis}) ===")
    train_stats = validate_pairs(train_pairs, tokenizer, "train", axis=args.axis)
    held_stats = validate_pairs(heldout_pairs, tokenizer, "heldout", axis=args.axis)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"\ndevice: {device}")

    # Reference model, frozen. Also the BEFORE measurement.
    ref = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32).to(device)
    ref.eval()

    print("\n=== BEFORE: held-out metrics ===")
    before_pref = preference_metrics(ref, tokenizer, heldout_pairs)
    print(f"preference_accuracy = {before_pref['preference_accuracy']:.3f}")
    before_gen = generation_metrics(ref, tokenizer, heldout_pairs)
    print(f"mean_new_tokens     = {before_gen['mean_new_tokens']:.1f}")
    print(f"answer_key_rate     = {before_gen['answer_key_rate']:.3f}")
    print(f"mean_hedge_markers  = {before_gen['mean_hedge_markers']:.2f}")
    print(f"degenerate_outputs  = {before_gen['degenerate_outputs']}")
    for p in list(before_gen["generations"])[:3]:
        g = before_gen["generations"][p]
        print(f"  [Q] {p}\n  [A] {g['text']!r} ({g['n_new_tokens']} tok, {g['stop_reason']})")

    ref_scores = before_pref["raw_scores"]

    # Train.
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32)
    targets = ["q_proj", "k_proj", "v_proj", "o_proj"]
    if args.mlp:
        targets += ["gate_proj", "up_proj", "down_proj"]

    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=DPOConfig(
            output_dir=str(OUT_DIR / f"ckpt_{args.tag}"),
            per_device_train_batch_size=4,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            beta=0.1,
            max_length=192,
            logging_steps=10,
            report_to=[],
            remove_unused_columns=False,
            disable_tqdm=True,
        ),
        train_dataset=Dataset.from_list(
            [{"prompt": p, "chosen": c, "rejected": r} for p, c, r, _ in train_pairs]
        ),
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=args.rank,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            target_modules=targets,
            task_type="CAUSAL_LM",
        ),
    )
    train_result = trainer.train()

    tuned = trainer.model
    # FIX 1 applied here. Both calls matter: eval() alone leaves checkpointing on.
    tuned.gradient_checkpointing_disable()
    tuned.config.use_cache = True
    tuned.eval()
    _assert_decode_ready(tuned)

    print("\n=== AFTER: held-out metrics ===")
    after_pref = preference_metrics(tuned, tokenizer, heldout_pairs, ref_scores=ref_scores)
    after_gen = generation_metrics(tuned, tokenizer, heldout_pairs)
    print(f"preference_accuracy        = {after_pref['preference_accuracy']:.3f} "
          f"(before {before_pref['preference_accuracy']:.3f})")
    print(f"mean_implicit_reward_margin= {after_pref['mean_implicit_reward_margin']:.4f}")
    print(f"margin_positive_rate       = {after_pref['margin_positive_rate']:.3f}")
    print(f"mean_new_tokens            = {after_gen['mean_new_tokens']:.1f} "
          f"(before {before_gen['mean_new_tokens']:.1f})")
    print(f"answer_key_rate            = {after_gen['answer_key_rate']:.3f} "
          f"(before {before_gen['answer_key_rate']:.3f})")
    print(f"mean_hedge_markers         = {after_gen['mean_hedge_markers']:.2f} "
          f"(before {before_gen['mean_hedge_markers']:.2f})")
    print(f"degenerate_outputs         = {after_gen['degenerate_outputs']}")
    for p in list(after_gen["generations"])[:3]:
        g = after_gen["generations"][p]
        print(f"  [Q] {p}\n  [A] {g['text']!r} ({g['n_new_tokens']} tok, {g['stop_reason']})")

    changed = sum(
        1 for p in after_gen["generations"]
        if after_gen["generations"][p]["text"] != before_gen["generations"][p]["text"]
    )
    print(f"\ngreedy generations changed: {changed}/{len(heldout_pairs)}")

    # The verdict the verbosity axis actually turns on: did output get shorter
    # WITHOUT dropping the answer? Length alone is not success.
    d_len = after_gen["mean_new_tokens"] - before_gen["mean_new_tokens"]
    d_key = after_gen["answer_key_rate"] - before_gen["answer_key_rate"]
    print(f"delta mean_new_tokens = {d_len:+.1f} | delta answer_key_rate = {d_key:+.3f}")
    if d_len < 0 and d_key < -1e-9:
        print("WARNING: shorter but losing answers -- degeneration, not concision.")

    results = {
        "tag": args.tag,
        "axis": args.axis,
        "model_id": MODEL_ID,
        "device": device,
        "hyperparams": {
            "lr": args.lr, "epochs": args.epochs, "rank": args.rank,
            "target_modules": targets, "beta": 0.1,
        },
        "dataset": {"train": train_stats, "heldout": held_stats},
        "final_train_loss": train_result.training_loss,
        "wall_clock_seconds": round(time.time() - t0, 1),
        "before": {"preference": before_pref, "generation": before_gen},
        "after": {"preference": after_pref, "generation": after_gen},
        "greedy_generations_changed": changed,
        "log_history": trainer.state.log_history,
    }
    path = OUT_DIR / f"results_{args.axis}_{args.tag}.json"
    path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {path}")
    print(f"Total wall clock: {results['wall_clock_seconds']}s")


if __name__ == "__main__":
    main()
