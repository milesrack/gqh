#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/gqh-uv-cache}"
export MPLCONFIGDIR="$PWD/.agent-work/.cache/matplotlib"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
mkdir -p results/sr3-macro-revisions-v1 "$MPLCONFIGDIR"
uv sync --locked
{
  uv run --env-file .env --locked python tools/sr3_macro_experiment.py acquire
  uv run --env-file .env --locked python tools/sr3_macro_experiment.py run --workers "${SR3_WORKERS:-4}"
} 2>&1 | tee -a results/sr3-macro-revisions-v1/run.log
