#!/usr/bin/env bash
# Run LinuxCNC with this config from any working directory.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
exec env QT_QUICK_BACKEND=software linuxcnc "$HERE/ethercat_mill.ini"
