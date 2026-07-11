# CogTrace-B

CogTrace-B maintains an evidence-grounded cognitive state for long-horizon coding
agents. It links explicit claims to exact trajectory spans and tool evidence, uses
that state for OpenHands context condensation and guards, and emits auditable
step-credit events for failure-conditioned distillation.

## What is implemented

- Grounded event, node, relation, snapshot, guard, and credit schemas.
- Exact-span and content-hash provenance validation.
- Verified-evidence state transitions with abstention-safe behavior.
- Structural extraction triggers instead of per-step LLM calls.
- Four guards: stale/refuted claim, repeated exploration, unsupported patch, and
  premature finish. Semantic guards fail open when no extractor is configured.
- OpenAI-compatible local extractor client for a Qwen2.5-Coder-32B endpoint.
- OpenHands observer/controller and a CogTrace-backed rolling condenser.
- Configurable 128K and 512K context profiles plus 4K/16K/32K state ablations.
- Repository-isolated data splits, annotation contracts, extractor metrics,
  clustered prediction bootstrap, and failure-conditioned OPD data contracts.

The repository does not fabricate the planned 240 trajectories, 200 human labels,
or GPU training results. Scripts and frozen schemas are provided to produce them.

## Install and test

```powershell
python -m pip install -e . --no-build-isolation
python -m pytest -q
```

Offline replay of the ten legacy Astropy traces:

```powershell
python -m scripts.replay_offline --context-profile deepseek-512k
```

Outputs go to `artifacts/cogtrace_grounded_v1/`. Existing `artifacts/cogtrace/`
and `artifacts/cognitive_graph/` are legacy V1 results and are not mixed with the
grounded evaluation.

Prepare annotation windows and repository-isolated splits:

```powershell
python -m scripts.prepare_annotations artifacts/trajectories/deepseek_v4_flash_500 annotations/windows.jsonl
python -m scripts.split_trajectories artifacts/trajectories/deepseek_v4_flash_500 annotations/splits.json
```

## Local extractor

Serve `Qwen/Qwen2.5-Coder-32B-Instruct` through an OpenAI-compatible endpoint and
set:

```text
COGTRACE_EXTRACTOR_BASE_URL=http://127.0.0.1:8001/v1
COGTRACE_EXTRACTOR_MODEL=Qwen/Qwen2.5-Coder-32B-Instruct
COGTRACE_EXTRACTOR_API_KEY=
COGTRACE_CONTEXT_PROFILE=deepseek-512k
```

Without these variables CogTrace records deterministic state and structural signals,
but claim-dependent guards are disabled. This is intentional: missing semantic state
must never cause patches to be blocked.

## Online OpenHands

The launcher installs CogTrace as an editable package into the benchmark environment,
so the integration contains no import-path hack.

```powershell
python -m scripts.run_online_openhands path/to/llm_config.json `
  --context-profile deepseek-512k `
  --condenser-max-tokens 524288
```

Context profiles separate the full model window from the CogTrace payload:

| Profile | Model input cap | Recent raw events | State/evidence |
|---|---:|---:|---:|
| `qwen-128k` | 131,072 | 8,192 | 16,384 |
| `deepseek-512k` | 524,288 | 16,384 | 32,768 |

Raw, summary, and CogTrace comparisons must use the same total input cap. Unused
CogTrace state capacity should be filled with provenance-linked raw evidence.

## Research gates

Do not start OPD until all three gates pass:

1. Grounded claim precision >= 0.90 and hallucination rate <= 0.05.
2. Failure-prediction macro-AUPRC improves by at least 0.05 over the best baseline.
3. Online resolution improves by 3 percentage points, or key failures fall by 20%
   without more than a 1-point resolution regression.

See `docs/experiment_protocol.md`, `docs/annotation_guidelines.md`, and
`docs/single_host_opd.md` for the frozen protocol.
