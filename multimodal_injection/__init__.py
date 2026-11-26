"""Agent Shield multimodal_injection module.

A screenshot that a vision agent fetches carries an instruction to call a tool the user
never asked for. The sample table is in attacks.py. The image drawing code is in render.py.
"""

from .attacks import SPECS, SPECS_BY_ID, ImageSpec, Variant

__all__ = ["SPECS", "SPECS_BY_ID", "ImageSpec", "Variant"]
