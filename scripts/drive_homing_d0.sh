#!/usr/bin/env bash
# Test H0c for drive homing (docs/DRIVE_HOMING.md): READ-ONLY survey of every
# A6-EC slave's homing objects. Writes nothing to the drives and moves nothing.
#
#   scripts/drive_homing_d0.sh            # slaves 0..3
#   scripts/drive_homing_d0.sh 0 3        # just X and A
#
# The output is also saved to logs/drive_homing/<date>_D0.txt. Keep it: it is
# the record of the drives' original values for rollback (the A6 keeps SDO
# writes even after they are removed from ethercat-conf.xml).
#
# Run with LinuxCNC stopped or running; the bus must be at least PREOP.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SLAVES=("$@"); [[ ${#SLAVES[@]} -eq 0 ]] && SLAVES=(0 1 2 3)
OUTDIR="$HERE/logs/drive_homing"; mkdir -p "$OUTDIR"
OUT="$OUTDIR/$(date +%Y-%m-%d_%H%M)_H0c.txt"

up() { # slave type index sub -> value or "ERR: ..."
  local v
  if v=$(ethercat upload -p "$1" -t "$2" "$3" "$4" 2>&1); then echo "$v"; else echo "ERR: ${v//$'\n'/ }"; fi
}

{
  echo "# drive homing D0 survey $(date -Is)"
  ethercat slaves 2>&1
  for p in "${SLAVES[@]}"; do
    echo
    echo "=== slave $p ==="
    echo "-- supported homing methods 0x60E3 (sub 0 = count) --"
    n=$(up "$p" uint8 0x60E3 0)
    echo "60E3:00 = $n"
    if [[ "$n" =~ ^(0x[0-9a-fA-F]+|[0-9]+) ]]; then
      cnt=$(( ${BASH_REMATCH[1]} ))
      for ((i = 1; i <= cnt && i <= 64; i++)); do
        echo "60E3:$(printf %02X $i) = $(up "$p" int16 0x60E3 $i)   (low byte = method, signed)"
      done
    fi
    echo "-- CiA 402 homing objects --"
    echo "6098:00 homing method        = $(up "$p" int8   0x6098 0)"
    echo "6099:01 speed search switch  = $(up "$p" uint32 0x6099 1)  (counts/s)"
    echo "6099:02 speed search zero    = $(up "$p" uint32 0x6099 2)  (counts/s)"
    echo "609A:00 homing acceleration  = $(up "$p" uint32 0x609A 0)  (counts/s^2)"
    echo "607C:00 home offset          = $(up "$p" int32  0x607C 0)"
    echo "60E6:00 homing calc method   = $(up "$p" uint8  0x60E6 0)  (0 = absolute: 6064 = 607C after homing)"
    echo "6065:00 following-error win  = $(up "$p" uint32 0x6065 0)"
    echo "6066:00 following-error time = $(up "$p" uint16 0x6066 0)"
    echo "6072:00 max torque           = $(up "$p" uint16 0x6072 0)"
    echo "-- A6 vendor homing parameters (C10.xx -> 0x2010:xx, expected) --"
    echo "2010:09 C10.08 homing time limit (ms, manual default 60000) = $(up "$p" uint32 0x2010 0x09)"
    # A6 maps C<g>.<n> to 0x20<g> subindex = (n+1) written as hex digits (C01.10 -> 0x2001:11)
    for sub in 29 30 31 32 33 34 35; do
      cpar=$(printf 'C10.%02d' $((10#$sub - 1)))
      echo "2010:$sub $cpar  u16 = $(up "$p" uint16 0x2010 0x$sub)   i32 = $(up "$p" int32 0x2010 0x$sub)"
    done
    echo "   (expect C10.30 = hard-stop homing torque, 0.1 %, A6-PN default 1000;"
    echo "    C10.31 = hard-stop homing speed, rpm, default 10; stall time nearby)"
    echo "2010:33 / 2010:34 (C10.32 hit-and-stop count, manual default 30) u16 = $(up "$p" uint16 0x2010 0x33) / $(up "$p" uint16 0x2010 0x34)"
    echo "-- DI functions C04.xx (5 = home switch, 6/7 = fwd/rev overtravel, 30/31 = probes) and logic (0 = active low, 1 = active high) --"
    i=1
    for sub in 01 05 09 0d 11; do
      lsub=$(printf '%02x' $((16#$sub + 1)))
      echo "DI$i function 2004:$sub = $(up "$p" uint16 0x2004 0x$sub)   logic 2004:$lsub = $(up "$p" uint16 0x2004 0x$lsub)"
      i=$((i + 1))
    done
    echo "60FD:00 digital inputs = $(up "$p" uint32 0x60FD 0)   (bit 2 = home active, bits 16-20 = DI1-DI5)"
    echo "-- touch probe (index latch used by scripts/index_survey.py) --"
    echo "60B8:00 function = $(up "$p" uint16 0x60B8 0)   60B9:00 status = $(up "$p" uint16 0x60B9 0)   60BA:00 latched = $(up "$p" int32 0x60BA 0)"
    echo "-- absolute encoder mode --"
    echo "2000:08 C00.07 absolute mode = $(up "$p" uint16 0x2000 0x08)"
  done
} 2>&1 | tee "$OUT"

echo
echo "saved: $OUT"
echo "Check: methods 5, 3 and 34 appear in the 60E3 list (-1/-2 there or not is torque-homing research)."
