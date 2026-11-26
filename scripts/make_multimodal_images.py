"""Render the multimodal_injection screenshots and write their SHA256SUMS file.

Run from the repo root: `uv run python scripts/make_multimodal_images.py`.

Output goes to evals/data/multimodal_injection/<sample_id>.png, one file per spec, then
ICON_<name>.png for each name in ICON_CHOICES, plus SHA256SUMS in `sha256sum` format. The
first line of SHA256SUMS is a comment that records the Pillow, FreeType and zlib versions
that drew the files. Another version can draw different bytes, so the regeneration test
skips when the running versions differ from that line.
"""

from __future__ import annotations

import sys
from pathlib import Path

import PIL
import PIL.features

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from multimodal_injection.attacks import ALL_SPECS, ICON_CHOICES  # noqa: E402
from multimodal_injection.hashes import SHA256SUMS, VERSION_PREFIX, sha256_hex  # noqa: E402
from multimodal_injection.render import icon_png_bytes, png_bytes  # noqa: E402


def toolchain_line() -> str:
    """The first line of SHA256SUMS: the versions that drew the PNG files."""
    freetype = PIL.features.version("freetype2")
    zlib = PIL.features.version("zlib")
    return f"{VERSION_PREFIX} pillow={PIL.__version__} freetype2={freetype} zlib={zlib}"


def main() -> None:
    out_dir = SHA256SUMS.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [toolchain_line()]
    # ALL_SPECS keeps the 50 older specs first, so their SHA256SUMS lines keep their order.
    files = [(f"{spec.sample_id}.png", png_bytes(spec)) for spec in ALL_SPECS]
    files += [(f"ICON_{name}.png", icon_png_bytes(name)) for name in ICON_CHOICES]
    for name, data in files:
        (out_dir / name).write_bytes(data)
        lines.append(f"{sha256_hex(data)}  {name}")
    SHA256SUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} PNG files and {SHA256SUMS}")


if __name__ == "__main__":
    main()
