#!/usr/bin/env bash
# Build and install components/a6home.comp (drive-internal homing glue) for
# BOTH LinuxCNC builds this mill runs. Realtime modules are not binary
# compatible between the two, so each needs its own build.
#
#   scripts/build-a6home.sh           # both
#   scripts/build-a6home.sh stock     # apt LinuxCNC 2.9.8 (needs sudo, linuxcnc-uspace-dev)
#   scripts/build-a6home.sh tpnext    # ~/src/linuxcnc-tpnext run-in-place build (no sudo)
#
# Run the bench test first: sh components/test/test_a6home.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMP="$HERE/components/a6home.comp"
RIP="${LINUXCNC_TPNEXT_RIP:-$HOME/src/linuxcnc-tpnext}"
which="${1:-both}"

sh "$HERE/components/test/test_a6home.sh"

if [[ "$which" == stock || "$which" == both ]]; then
  if ! command -v halcompile >/dev/null; then
    echo "halcompile missing: sudo apt install linuxcnc-uspace-dev" >&2; exit 1
  fi
  echo "== stock LinuxCNC: sudo halcompile --install $COMP"
  sudo halcompile --install "$COMP"
fi

if [[ "$which" == tpnext || "$which" == both ]]; then
  if [[ ! -f "$RIP/scripts/rip-environment" ]]; then
    echo "tpnext RIP not found at $RIP (set LINUXCNC_TPNEXT_RIP)" >&2; exit 1
  fi
  echo "== tpnext RIP: halcompile --install $COMP (into $RIP)"
  (
    set +u
    # shellcheck disable=SC1091
    source "$RIP/scripts/rip-environment"
    set -u
    halcompile --install "$COMP"
  )
fi
echo "done. Check with: halcmd loadrt a6home count=1 && halcmd show pin a6home.0 (inside a running session)"
