"""Hash check of the multimodal_injection PNG files. No PIL: the eval imports this file.

The generator (scripts/make_multimodal_images.py) writes SHA256SUMS next to the PNG files.
The eval checks every file against it on each load and raises with the file name on a
mismatch, the same way evals/tools_v2.py checks tools_v2_tasks.sha256.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "evals" / "data" / "multimodal_injection"
SHA256SUMS = DATA_DIR / "SHA256SUMS"
VERSION_PREFIX = "# toolchain:"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_sums(sums_path: Path = SHA256SUMS) -> tuple[str, dict[str, str]]:
    """Return (toolchain line, {file name: sha256}) from a SHA256SUMS file."""
    toolchain = ""
    sums: dict[str, str] = {}
    for raw in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.startswith(VERSION_PREFIX):
                toolchain = line
            continue
        digest, _, name = line.partition("  ")
        sums[name.strip()] = digest.strip()
    return toolchain, sums


def verified_png(path: Path, sums_path: Path = SHA256SUMS) -> bytes:
    """Read one PNG file and return its bytes, or raise if its hash is not in SHA256SUMS."""
    _, sums = read_sums(sums_path)
    expected = sums.get(path.name)
    if expected is None:
        raise RuntimeError(f"{path} has no entry in {sums_path}")
    data = path.read_bytes()
    actual = sha256_hex(data)
    if actual != expected:
        raise RuntimeError(f"{path} sha256 {actual} does not match the recorded {expected}")
    return data


def verify_all(names: list[str], data_dir: Path = DATA_DIR) -> None:
    """Check every named PNG file in `data_dir`. Raises on the first bad or missing file."""
    for name in names:
        verified_png(data_dir / name, data_dir / "SHA256SUMS")
