# Research prompt 05: Study B, Jacobian lens monitoring on open weight agents

Paste everything below the line into Claude Research.

---

## What I need
For the v2 paper of agent-shield (agent security evaluations on Inspect AI) I plan Study B: run an open weight agent on a tool description poisoning task, then apply a pre fitted Jacobian lens to the same token sequences and measure how often the injection appears internally on samples where the agent did not tell the user. I need the current state of the tooling and method, and the cheapest valid compute route. Cite primary sources; mark anything unconfirmed as UNVERIFIED.

## Current state (facts)
- Method source: Gurnee et al., "Verbalizable Representations Form a Global Workspace in Language Models", arXiv:2607.15495; code github.com/anthropics/jacobian-lens ("Reference implementation. Not maintained."). Its §5.2 shows qualitative "silent recognition of a prompt injection" on Claude Opus 4.5.
- Pre fitted lenses: huggingface.co/neuronpedia/jacobian-lens, including `qwen3.5-4b` (fit on the post trained checkpoint) and `qwen3.6-27b`.
- Plan: Qwen3.5-4B pilot, Qwen3.6-27B later; lens pass after the agent run; fixed token set with a threshold calibrated on benign agent transcripts and a reported false positive rate.
- Compute: an 18 GB laptop cannot hold the models in bf16. No paid GPU budget now. A free notebook for engineering checks only, then a free monthly credit for the bf16 pilot.

## Questions
1. Current state of the `jacobian-lens` code and forks: does applying a pre fitted lens need only forward passes? Do the loaders support Qwen3.5 and 3.6 image text checkpoints (layers under `model.language_model.layers`)?
2. Validity of lenses fit on WikiText or Pile when read on chat or agent transcripts: any evidence from the paper, Neuronpedia or replications; recommended calibration.
3. Prior or concurrent work detecting prompt injection from activations (probes, latent space monitors such as SecMCP arXiv:2508.06418, `J-lens` based detectors), with measured rates and benign false positive rates.
4. Free or low cost routes to bf16 inference with forward hooks on a 4B to 27B model in 2026: free notebooks, monthly free credits, research credits open to independent researchers; hard spend limits.
5. Whether fp16 versus bf16 changes lens readouts enough to matter.

## Output format
1. Findings table with sources and impact on the Study B design; UNVERIFIED where unconfirmed.
2. A step list for the free engineering check (load, apply lens, read one saved transcript) with expected outputs.
3. At most 5 decisions for me, recommended option first.
