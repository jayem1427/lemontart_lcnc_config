#!/bin/sh
# Bench test for components/a6home.comp: extracts the plain-C state machine
# between the LOGIC-BEGIN / LOGIC-END markers and runs it against a simulated
# A6 drive and LinuxCNC index-only homing. Needs only gcc.
#   sh components/test/test_a6home.sh
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
sed -n '/LOGIC-BEGIN/,/LOGIC-END/p' "$HERE/../a6home.comp" > "$TMP/a6home_logic.inc"
gcc -std=c99 -Wall -Wextra -Werror -O1 -I"$TMP" -o "$TMP/test_a6home" "$HERE/test_a6home.c" -lm
"$TMP/test_a6home"
