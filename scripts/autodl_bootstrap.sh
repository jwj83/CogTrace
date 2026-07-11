#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARKS="$ROOT/benchmarks"
PINNED_BENCHMARKS_COMMIT="4e5469e0caaf54d1ad827d18b524bdfb79d58430"
PATCH="$ROOT/patches/openhands_benchmarks_cogtrace.patch"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}

require git
require python3
require docker

if ! docker info >/dev/null 2>&1; then
  echo "Docker is unavailable. Select an AutoDL image with usable Docker support before continuing." >&2
  exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [[ ! -d "$BENCHMARKS/.git" ]]; then
  git clone https://github.com/OpenHands/benchmarks.git "$BENCHMARKS"
fi

git -C "$BENCHMARKS" fetch --depth=1 origin "$PINNED_BENCHMARKS_COMMIT"
git -C "$BENCHMARKS" checkout --detach "$PINNED_BENCHMARKS_COMMIT"
git -C "$BENCHMARKS" submodule update --init --recursive

if ! git -C "$BENCHMARKS" apply --check "$PATCH"; then
  echo "CogTrace integration patch does not apply cleanly. Do not continue with an unpinned benchmark tree." >&2
  exit 2
fi
git -C "$BENCHMARKS" apply "$PATCH"

uv sync --project "$BENCHMARKS"
uv run --project "$BENCHMARKS" --with-editable "$ROOT" python -c 'import cog_trace; print("CogTrace import OK")'
echo "Bootstrap complete. Copy .env.example to .env and configure the local API key."
