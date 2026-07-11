# Online Rerun Protocol

## Configure the grounded extractor

Run the 32B extractor on the same host through an OpenAI-compatible endpoint:

```powershell
$env:COGTRACE_EXTRACTOR_BASE_URL = "http://127.0.0.1:8001/v1"
$env:COGTRACE_EXTRACTOR_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
$env:COGTRACE_EXTRACTOR_API_KEY = ""
```

If the endpoint is absent, CogTrace fails open: it records deterministic events and
may report structural signals, but it does not block patches based on missing Claims.

## Pilot rerun

```powershell
python -m scripts.run_online_openhands <llm-config.json> `
  --instances astropy__astropy-13236 astropy__astropy-13033 `
  --workspace docker `
  --output-dir artifacts\online_runs\cogtrace_grounded `
  --context-profile deepseek-512k `
  --condenser-max-tokens 524288 `
  --num-workers 1
```

The launcher enables CogTrace, installs the root package into the benchmark
environment with `uv --with-editable`, and uses `CogTraceCondenser` in place of the
ordinary LLM summary. The controller writes graph, credit, guard, and summary files
under `cogtrace_online/<instance_id>/`.

## Formal conditions

Do not compare a 512K raw condition with a smaller CogTrace cap. For each condition,
keep the same model input cap, tools, max iterations, prompt, and instance seeds.
Use separate output directories for:

```text
raw
summary
cogtrace_context
cogtrace_context_guard
```

Run the 4K/16K/32K state-payload ablation separately from the primary total-context
comparison.
