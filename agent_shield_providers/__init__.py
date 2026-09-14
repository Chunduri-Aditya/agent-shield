"""Inspect AI model providers for agent-shield."""

from inspect_ai.model import ModelAPI, modelapi


@modelapi(name="mlx")
def mlx() -> type[ModelAPI]:
    # The entry point imports this package everywhere; mlx ships only in the optional group.
    from .mlx_lm_api import MLXLMAPI

    return MLXLMAPI
