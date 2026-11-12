#!/bin/bash
# SPDX-License-Identifier: LGPL-3.0-or-later
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
python_bin="${CFDOF_PYTHON:-}"
if [ -z "$python_bin" ]; then
    python_bin="$(command -v python3 || true)"
fi
if [ -z "$python_bin" ]; then
    for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if [ -x "$candidate" ]; then
            python_bin="$candidate"
            break
        fi
    done
fi
if [ -z "$python_bin" ]; then
    echo "需要 Python 3；也可设置 CFDOF_PYTHON 为 Python 解释器的完整路径。" >&2
    exit 1
fi
exec "$python_bin" "$script_dir/diagnostics.py" --json "$script_dir/diagnostics.json" "$@"
