#!/usr/bin/env bash
# Launch this mill config with the experimental tpnext-ma RIP build.
# Stock apt LinuxCNC is untouched — use launch.sh for that.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RIP="${LINUXCNC_TPNEXT_RIP:-/home/jon/src/linuxcnc-tpnext}"
DEPS="${LINUXCNC_TPNEXT_DEPS:-/home/jon/src/deps-prefix}"

if [[ ! -f "$RIP/scripts/rip-environment" ]]; then
  echo "tpnext RIP not found at $RIP" >&2
  exit 1
fi
if [[ ! -e "$RIP/bin/rtapi_app" ]]; then
  echo "rtapi_app missing — build incomplete" >&2
  exit 1
fi
# Hardware access needs setuid/setcap once after build:
if [[ ! -u "$RIP/bin/rtapi_app" ]] && ! getcap "$RIP/bin/rtapi_app" 2>/dev/null | grep -q cap_sys_rawio; then
  echo "WARNING: $RIP/bin/rtapi_app is not setuid/setcap." >&2
  echo "Run once:  cd $RIP/src && sudo make setuid" >&2
fi

# libfmt and other locally extracted runtime libs
export LD_LIBRARY_PATH="${DEPS}/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

cd "$HERE"
# shellcheck disable=SC1091
source "$RIP/scripts/rip-environment"
exec env QT_QUICK_BACKEND=software linuxcnc "$HERE/ethercat_mill.ini"
