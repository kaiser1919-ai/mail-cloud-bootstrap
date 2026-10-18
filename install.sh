#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
command -v python3 >/dev/null || { echo 'Install Python 3 first: apt-get install python3' >&2; exit 1; }
exec python3 -I installer/wizard.py "$@"
