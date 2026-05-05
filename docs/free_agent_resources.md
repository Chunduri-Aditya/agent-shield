# Free Agent Backends

Use this as the zero dollar test lane before spending paid API money. In this
file, "agent" means a model backend that can serve as the agent under Inspect.
For `tools/`, prefer backends with tool calling support; for `inputs/` and
`psych/`, plain chat completion is enough.

Run the local status table:

```bash
make free-agents
```

Run one backend against one live module:

```bash
make eval-free-groq FREE_MODULE=inputs
make eval-free-gemini FREE_MODULE=psych
make eval-free-ollama FREE_MODULE=tools
make eval-free-lmstudio FREE_MODULE=inputs LMSTUDIO_MODEL=<model>
make eval-free-vllm FREE_MODULE=inputs VLLM_MODEL=<model>
```

Free tiers change. Treat every hosted backend here as a smoke path first, not a
paper grade measurement path, until the exact model ID, seed, n, date, and
commit SHA are logged in `RESULTS.md`.

## Best first pass

| Rank | Backend | Why it belongs first | Inspect command |
|---|---|---|---|
| 1 | Ollama local | No API spend, good for repeatable harness checks | `make eval-free-ollama FREE_MODULE=inputs` |
| 2 | Groq free tier | Fast hosted open models and simple API key setup | `make eval-free-groq FREE_MODULE=inputs` |
| 3 | Google AI Studio free tier | Useful Gemini comparison row with no paid tier required | `make eval-free-gemini FREE_MODULE=inputs` |
| 4 | OpenRouter free router | Broadest free model coverage, but model choice can vary | `make eval-free-openrouter FREE_MODULE=inputs` |
| 5 | GitHub Models | Good free account path and many model families | `make eval-free-github-models FREE_MODULE=inputs` |

## Backend matrix

| Backend | Setup | Default model variable | Env vars | Notes |
|---|---|---|---|---|
| Ollama | Install Ollama, pull a model, keep server running | `OLLAMA_MODEL=llama3.1:8b` | none | Inspect has a native `ollama/` provider. |
| LM Studio | Start local OpenAI compatible server | `LMSTUDIO_MODEL=local-model` | none for local default target | Uses Inspect `openai-api/lmstudio/...`. |
| vLLM | Serve a local or rented GPU model | `VLLM_MODEL=meta-llama/Llama-3.1-8B-Instruct` | none for local default target | Uses Inspect `openai-api/vllm/...`. |
| Groq | Create free Groq key | `GROQ_MODEL=llama-3.1-8b-instant` | `GROQ_API_KEY` | Hosted open models with published free plan limits. |
| Google AI Studio | Create Gemini API key | `GEMINI_MODEL=gemini-2.5-flash` | `GOOGLE_API_KEY` | Free tier exists for testing with lower rate limits. |
| OpenRouter | Create OpenRouter key | `OPENROUTER_MODEL=openrouter/free` | `OPENROUTER_API_KEY` | `openrouter/free` routes to available free models. |
| Cerebras | Create Cerebras key | `CEREBRAS_MODEL=openai/gpt-oss-20b` | `CEREBRAS_API_KEY` | Uses Inspect `openai-api/cerebras/...`. |
| GitHub Models | Create PAT with models read scope | `GITHUB_MODELS_MODEL=openai/gpt-4.1-mini` | `GITHUB_MODELS_API_KEY` | Uses Inspect `openai-api/github-models/...`. |
| Cloudflare Workers AI | Create token and account ID | `CLOUDFLARE_MODEL=meta/llama-3.1-8b-instruct-fp8-fast` | `CLOUDFLARE_API_KEY`, `CLOUDFLARE_ACCOUNT_ID` | Daily free neuron allocation. |
| Hugging Face Inference Providers | Create HF token | `HF_MODEL=openai/gpt-oss-20b` | `HF_TOKEN` | Included monthly credits are small but useful for smoke tests. |
| Kaggle Benchmarks proxy | Use Kaggle notebook flow | `KAGGLE_MODELS=google/gemini-2.5-flash` | `MODEL_PROXY_API_KEY` | Existing scaffold lives in `docs/kaggle_free_models.md`. |

## Source links

Inspect provider support:

1. [Inspect model providers](https://inspect.aisi.org.uk/providers.html)
2. [Inspect model usage](https://inspect.aisi.org.uk/models.html)

Local OpenAI compatible paths:

1. [Ollama OpenAI compatibility](https://docs.ollama.com/openai)
2. [LM Studio OpenAI compatibility endpoints](https://lmstudio.ai/docs/developer/openai-compat/)
3. [vLLM OpenAI compatible server](https://docs.vllm.ai/serving/openai_compatible_server.html)

Hosted free or free allocation paths:

1. [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
2. [Groq rate limits](https://console.groq.com/docs/rate-limits)
3. [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
4. [Google Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
5. [OpenRouter free models router](https://openrouter.ai/docs/guides/routing/routers/free-models-router)
6. [OpenRouter free variant](https://openrouter.ai/docs/guides/routing/model-variants/free)
7. [GitHub Models quickstart](https://docs.github.com/en/github-models/quickstart)
8. [GitHub Models billing](https://docs.github.com/en/billing/concepts/product-billing/github-models)
9. [Cerebras OpenAI compatibility](https://inference-docs.cerebras.ai/resources/openai)
10. [Cerebras pricing](https://www.cerebras.ai/pricing)
11. [Cloudflare Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
12. [Cloudflare OpenAI compatible endpoints](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/)
13. [Hugging Face Inference Providers pricing](https://huggingface.co/docs/inference-providers/main/en/pricing)
14. [Hugging Face Inspect guide](https://huggingface.co/docs/inference-providers/en/guides/evaluation-inspect-ai)
15. [Kaggle Benchmarks package](https://pypi.org/project/kaggle-benchmarks/)
