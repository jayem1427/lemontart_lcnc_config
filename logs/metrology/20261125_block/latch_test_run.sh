#!/usr/bin/env bash
# Latch-speed test helper (2026-11-25): wait for all joints homed, then probe the block center 3x in X and Y.
# Usage: latch_test_run.sh <tag>   e.g. slow / normal
set -e
TAG=${1:?tag}
CFG=/home/jon/linuxcnc/configs/ethercat_mill
D=$CFG/logs/metrology/20261125_block
source ~/src/linuxcnc-tpnext/scripts/rip-environment >/dev/null 2>&1
cd "$CFG"
python3 - <<'EOF'
import linuxcnc, time
s = linuxcnc.stat(); t = time.time()
while time.time() - t < 900:
    try:
        s.poll()
        if all(s.homed[:4]) and s.interp_state == linuxcnc.INTERP_IDLE and s.task_state == linuxcnc.STATE_ON:
            print('all homed', flush=True); break
    except linuxcnc.error:
        pass
    time.sleep(0.5)
else:
    raise SystemExit('timed out waiting for homing')
time.sleep(2)
c = linuxcnc.command(); e = linuxcnc.error_channel()
def run(cmd):
    c.mdi(cmd); t = time.time()
    while time.time() - t < 60:
        time.sleep(0.1); s.poll(); m = e.poll()
        if m and m[0] in (linuxcnc.OPERATOR_ERROR, linuxcnc.NML_ERROR): raise SystemExit('ERR ' + m[1])
        if s.interp_state == linuxcnc.INTERP_IDLE and time.time() - t > 0.3: return
s.poll()
c.mode(linuxcnc.MODE_MDI); c.wait_complete()
if s.tool_in_spindle != 99:
    run('M61 Q99')
run('G90 G54 G43')
s.poll()
print('tool', s.tool_in_spindle, 'offset', round(s.tool_offset[2], 4), 'pos', [round(p, 3) for p in s.actual_position[:3]], flush=True)
assert s.tool_in_spindle == 99 and abs(s.tool_offset[2] - 45.0422) < 1e-3 and s.probe_val == 0
assert s.actual_position[2] > -1.0, 'expected spindle up after homing'
run('G53 G0 X97.013 Y141.8911')
run('G38.3 Z1.978 F800')
s.poll(); print('over center at', [round(p, 3) for p in s.actual_position[:3]], flush=True)
assert abs(s.actual_position[2] + 15.37) < 0.05
c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
EOF
python3 scripts/block_ridge_repeat.py X $D/ridge_x_latch_$TAG.csv --runs 3 --hint 51
python3 scripts/block_ridge_repeat.py Y $D/ridge_y_latch_$TAG.csv --runs 3 --hint 53
echo DONE
