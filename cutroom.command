#!/bin/zsh
set -eu
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ -x data/venv/bin/python ]]; then
  exec data/venv/bin/python -m cutroom.launcher "$@"
fi
exec python3 -m cutroom.launcher "$@"
