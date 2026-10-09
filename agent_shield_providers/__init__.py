"""Inspect AI model providers for agent-shield."""

from inspect_ai.model import ModelAPI, modelapi


@modelapi(name="mlx")
def mlx() -> type[ModelAPI]:
    # The entry point imports this package everywhere; mlx ships only in the optional group.
    from .mlx_lm_api import MLXLMAPI

    return MLXLMAPI


@modelapi(name="twin")
def twin() -> type[ModelAPI]:
    # twin itself runs in its own checkout (TWIN_DIR) through its CLI; nothing extra imports here.
    from .twin_api import TwinAPI

    return TwinAPI


@modelapi(name="cli")
def cli() -> type[ModelAPI]:
    # The subscription CLIs (claude, codex, gemini) run as subprocesses; nothing extra imports here.
    from .cli_api import CLIAPI

    return CLIAPI
