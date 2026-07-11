# AutoDL collection host

The first collection uses API-hosted agent and extractor models. GPU is optional;
Docker capacity, CPU, RAM, and disk are the limiting resources.

## Recommended first host

- At least 8 vCPU and 32 GB RAM (16 GB is only a small smoke-test minimum).
- At least 200 GB free local disk; 300 GB is safer once Docker images accumulate.
- Ubuntu 22.04/CUDA image is convenient, but GPU is not required for API-only runs.
- Docker must work for the logged-in user: `docker info` must succeed.

Do not use a 0.5-vCPU/2-GB instance for SWE-bench. It is suitable only for
editing files or downloading results, not running Docker task environments.

## One-time setup

Clone this private repository and run:

```bash
git clone https://github.com/jwj83/CogTrace.git
cd CogTrace
bash scripts/autodl_bootstrap.sh
cp .env.example .env
chmod 600 .env
```

Put the API key only in `.env`; do not paste it into a shell history, commit it,
or place it in an experiment configuration.

The bootstrap script clones the pinned OpenHands benchmark source into
`benchmarks/` and applies the versioned CogTrace integration patch. It stops if
Docker is unavailable.

## First smoke run

Use `tmux` so an SSH disconnect does not terminate the job:

```bash
tmux new -s cogtrace
set -a; source .env; set +a
python -m scripts.run_online_openhands /secure/path/agent.json \
  --mode shadow \
  --extractor-model deepseek-v4-flash \
  --instances astropy__astropy-13236 \
  --max-iterations 80 \
  --output-dir artifacts/online_runs/smoke
```

`agent.json` remains local to the server and must not be committed. The initial
shadow run records grounded state and credit events without changing the Agent's
context or blocking tools. Only after it succeeds do we run the larger SWE-bench
Pro collection.

## Retrieving results

Archive `artifacts/online_runs/` after each batch and copy it to durable storage.
Do not rely on a rented server's local disk as the only copy.
