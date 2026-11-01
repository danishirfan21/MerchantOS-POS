#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
venv_dir="${RUNNER_TEMP:?}/merchantos-operations-python"
python3 -m venv "$venv_dir"
"$venv_dir/bin/pip" install --require-hashes -r "$root/requirements.lock" --quiet
"$venv_dir/bin/pip" install --require-hashes -r "$root/requirements-ci.lock" --quiet
echo "$venv_dir/bin" >> "$GITHUB_PATH"
