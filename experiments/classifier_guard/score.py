r"""Score the Phase 1 evaluation set with the pinned classifier, on CPU or GPU.

    uv run --group classifier python experiments/classifier_guard/score.py --device cpu \
        --run-id cpu1 [--data-dir data/v2] [--latency-repeats 20]

Same code path on both devices; only --device changes. fp32, eager, TF32 off.
Writes runs/<run-id>/scores.jsonl, latency.jsonl (raw timings) and env.json.
torch and transformers are imported inside the functions that need them, so the
windowing and decision helpers load without the classifier group installed.
"""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MODEL = "protectai/deberta-v3-base-prompt-injection-v2"
REVISION = "90c9989b1a342275dd0d1a95aad283c04e075671"
MAX_LEN, STRIDE, THRESHOLD = 512, 256, 0.5


def encode_windows(tok: Any, text: str, return_tensors: str | None = "pt") -> Any:
    """Tokenize text into MAX_LEN token windows that overlap by STRIDE tokens."""
    return tok(
        text,
        truncation=True,
        max_length=MAX_LEN,
        stride=STRIDE,
        return_overflowing_tokens=True,
        padding=True,
        return_tensors=return_tensors,
    )


def pick_window(probs: Sequence[float], threshold: float = THRESHOLD) -> dict[str, float | int]:
    """Per text verdict: the first window with the maximum injection probability."""
    if not probs:
        raise ValueError("no windows to score")
    i = max(range(len(probs)), key=lambda j: probs[j])
    p = float(probs[i])
    return {"prob": p, "label": int(p >= threshold), "window": i, "n_windows": len(probs)}


class Guard:
    """Windowed classifier: max injection probability over 512 token windows."""

    def __init__(self, device: str) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.device = torch.device(device)
        self.tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = (
            AutoModelForSequenceClassification.from_pretrained(
                MODEL, revision=REVISION, torch_dtype=torch.float32
            )
            .to(self.device)
            .eval()
        )
        labels = {v.upper(): int(k) for k, v in self.model.config.id2label.items()}
        self.pos = labels["INJECTION"]

    def sync(self) -> None:
        import torch

        if self.device.type == "cuda":
            torch.cuda.synchronize()

    def score(self, text: str) -> dict[str, float | int]:
        import torch

        with torch.inference_mode():
            enc = encode_windows(self.tok, text)
            inputs = {k: enc[k].to(self.device) for k in ("input_ids", "attention_mask")}
            probs = torch.softmax(self.model(**inputs).logits.float(), dim=-1)[:, self.pos]
            return pick_window(probs.tolist())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env_record(device: str, data: Path) -> dict[str, Any]:
    import torch
    import transformers

    rec: dict[str, Any] = {
        "utc": datetime.now(UTC).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "torch_threads": torch.get_num_threads(),
        "model": MODEL,
        "revision": REVISION,
        "device": device,
        "data_dir": str(data),
        "manifest_sha256": sha256(data / "manifest.jsonl"),
        "texts_sha256": sha256(data / "eval_texts.jsonl"),
    }
    if device == "cuda":
        rec.update(
            cuda=torch.version.cuda,
            cudnn=torch.backends.cudnn.version(),
            gpu=torch.cuda.get_device_name(0),
            nvidia_smi=subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
            ).stdout.strip(),
        )
    return rec


def main() -> None:
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("--device", choices=["cpu", "cuda"], required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--data-dir", type=Path, default=HERE / "data" / "v2")
    ap.add_argument("--out-dir", type=Path, default=HERE / "runs")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--latency-repeats", type=int, default=20)
    args = ap.parse_args()

    torch.manual_seed(0)
    torch.set_num_threads(args.threads)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True, warn_only=True)

    out = args.out_dir / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    with open(args.data_dir / "eval_texts.jsonl") as fh:
        texts = [json.loads(line) for line in fh]

    t0 = time.perf_counter()
    guard = Guard(args.device)
    guard.sync()
    load_s = time.perf_counter() - t0

    with open(out / "scores.jsonl", "w") as f:
        for r in texts:
            f.write(json.dumps({"id": r["id"], **guard.score(r["text"])}) + "\n")

    for r in texts[: args.warmup]:
        guard.score(r["text"])
    if args.device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    with open(out / "latency.jsonl", "w") as f:
        for r in texts:
            ms = []
            for _ in range(args.latency_repeats):
                guard.sync()
                t = time.perf_counter()
                guard.score(r["text"])
                guard.sync()
                ms.append((time.perf_counter() - t) * 1000)
            f.write(json.dumps({"id": r["id"], "ms": ms}) + "\n")

    rec = env_record(args.device, args.data_dir.resolve())
    rec.update(
        model_load_s=load_s,
        warmup=args.warmup,
        latency_repeats=args.latency_repeats,
        peak_rss_bytes_raw=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        peak_rss_unit="bytes on macOS, kilobytes on Linux",
    )
    if args.device == "cuda":
        rec.update(
            cuda_max_allocated=torch.cuda.max_memory_allocated(),
            cuda_max_reserved=torch.cuda.max_memory_reserved(),
        )
    (out / "env.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
