"""Print configured free agent backends without exposing secrets."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FreeAgent:
    name: str
    command: str
    required_env: tuple[str, ...]
    note: str
    local_models_url: str | None = None
    model_env: str | None = None


FREE_AGENTS: tuple[FreeAgent, ...] = (
    FreeAgent(
        name="Ollama local",
        command="make eval-free-ollama FREE_MODULE=inputs",
        required_env=(),
        note="Requires local Ollama server and model pull.",
        local_models_url="http://localhost:11434/api/tags",
        model_env="OLLAMA_MODEL",
    ),
    FreeAgent(
        name="LM Studio local",
        command="make eval-free-lmstudio FREE_MODULE=inputs LMSTUDIO_MODEL=<model>",
        required_env=(),
        note="Requires LM Studio local server on port 1234.",
        local_models_url="http://localhost:1234/v1/models",
        model_env="LMSTUDIO_MODEL",
    ),
    FreeAgent(
        name="vLLM local",
        command="make eval-free-vllm FREE_MODULE=inputs VLLM_MODEL=<model>",
        required_env=(),
        note="Requires a vLLM OpenAI compatible server on port 8000.",
        local_models_url="http://localhost:8000/v1/models",
        model_env="VLLM_MODEL",
    ),
    FreeAgent(
        name="Groq free tier",
        command="make eval-inputs-groq",
        required_env=("GROQ_API_KEY",),
        note="Fast hosted Llama 3.3 70B path with free rate limits.",
    ),
    FreeAgent(
        name="Google AI Studio free tier",
        command="make eval-inputs-gemini",
        required_env=("GOOGLE_API_KEY",),
        note="Gemini API free tier path for testing.",
    ),
    FreeAgent(
        name="OpenRouter free router",
        command="make eval-free-openrouter FREE_MODULE=inputs",
        required_env=("OPENROUTER_API_KEY",),
        note="Routes to currently available free models.",
    ),
    FreeAgent(
        name="Cerebras free tier",
        command="make eval-free-cerebras FREE_MODULE=inputs",
        required_env=("CEREBRAS_API_KEY",),
        note="Hosted open models through an OpenAI compatible endpoint.",
    ),
    FreeAgent(
        name="GitHub Models free usage",
        command="make eval-free-github-models FREE_MODULE=inputs",
        required_env=("GITHUB_MODELS_API_KEY",),
        note="Uses a GitHub token with models read scope.",
    ),
    FreeAgent(
        name="Cloudflare Workers AI",
        command="make eval-free-cloudflare FREE_MODULE=inputs",
        required_env=("CLOUDFLARE_API_KEY", "CLOUDFLARE_ACCOUNT_ID"),
        note="Daily free neuron allocation.",
    ),
    FreeAgent(
        name="Hugging Face Inference Providers",
        command="make eval-free-hf FREE_MODULE=inputs",
        required_env=("HF_TOKEN",),
        note="Monthly included credits for routed provider calls.",
    ),
    FreeAgent(
        name="Kaggle Benchmarks proxy",
        command="make kaggle-inputs",
        required_env=("MODEL_PROXY_API_KEY",),
        note="Notebook flow, not a plain Inspect endpoint.",
    ),
    FreeAgent(
        name="xAI Grok (extended sweep)",
        command="make eval-inputs-grok",
        required_env=("XAI_API_KEY",),
        note="OpenAI-compatible endpoint at api.x.ai/v1. Outside v1.0.0 paper set. Key prefix: xai-",
    ),
)


DEFAULT_MODELS: dict[str, str] = {
    "OLLAMA_MODEL": "llama3.1:8b",
    "LMSTUDIO_MODEL": "local-model",
    "VLLM_MODEL": "meta-llama/Llama-3.1-8B-Instruct",
    "GROQ_MODEL": "llama-3.3-70b-versatile",
    "GEMINI_MODEL": "gemini-3.5-flash",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    env_path = repo_root() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("'\"")
        if name and name not in os.environ:
            os.environ[name] = value


def fetch_json(url: str) -> dict[str, object] | None:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=1.0) as response:
            raw = response.read().decode("utf-8")
    except (OSError, URLError, TimeoutError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def model_names(agent: FreeAgent, data: dict[str, object]) -> list[str]:
    if agent.name == "Ollama local":
        models = data.get("models")
        if isinstance(models, list):
            return [
                str(model.get("name"))
                for model in models
                if isinstance(model, dict) and model.get("name")
            ]
        return []

    models = data.get("data")
    if isinstance(models, list):
        return [
            str(model.get("id"))
            for model in models
            if isinstance(model, dict) and model.get("id")
        ]
    return []


def local_status(agent: FreeAgent) -> str | None:
    if agent.local_models_url is None:
        return None

    data = fetch_json(agent.local_models_url)
    if data is None:
        return "server unavailable"

    configured_model = DEFAULT_MODELS.get(agent.model_env or "", "")
    configured_model = os.getenv(agent.model_env or "", configured_model)
    names = model_names(agent, data)
    if not names:
        return "server up, no models listed"
    if configured_model in names:
        return f"ready: {configured_model}"
    return f"server up, set {agent.model_env} to one of: {', '.join(names[:3])}"


def status(agent: FreeAgent) -> str:
    local = local_status(agent)
    if local is not None:
        return local
    if not agent.required_env:
        return "local setup"
    missing = [name for name in agent.required_env if not os.getenv(name)]
    if missing:
        return "missing " + ", ".join(missing)
    return "configured"


def main() -> None:
    load_local_env()
    print("| Agent backend | Status | Command | Note |")
    print("|---|---|---|---|")
    for agent in FREE_AGENTS:
        print(
            f"| {agent.name} | {status(agent)} | `{agent.command}` | {agent.note} |"
        )


if __name__ == "__main__":
    main()
