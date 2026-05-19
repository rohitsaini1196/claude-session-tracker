#!/usr/bin/env bash
# Start the local dashboard server. Standard library only — no venv needed.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec python3 -m server.app
