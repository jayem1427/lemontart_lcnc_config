#!/usr/bin/env python3
"""Repeat Probe Basic's ridge probe (block width/center) N times and log each result.

Usage (LinuxCNC running, machine on and homed, touch probe T99 loaded,
probe parked over the block center about 2 mm above the top):

    source ~/src/linuxcnc-tpnext/scripts/rip-environment
    python3 scripts/block_ridge_repeat.py X out.csv [--runs 10] [--hint 51]

It runs in measure-only mode (forces #3030 = 1), so no work offset changes.
LinuxCNC writes the results to the CSV itself through (LOG,...), because
Probe Basic also reads the error channel and can grab the result messages
first. --hint overrides #3028/#3029 (block width + ~2 mm) for this session only.
"""
import argparse, os, time
import linuxcnc

ap = argparse.ArgumentParser()
ap.add_argument('axis', choices=['X', 'Y'])
ap.add_argument('out')
ap.add_argument('--runs', type=int, default=10)
ap.add_argument('--hint', type=float, help='ridge width hint, mm (default: keep #3028/#3029)')
a = ap.parse_args()
out = os.path.abspath(a.out)

c = linuxcnc.command(); s = linuxcnc.stat()
s.poll()
assert s.tool_in_spindle == 99, 'load the touch probe (T99) first'
assert all(s.homed[:3]) and s.interp_state == linuxcnc.INTERP_IDLE and s.probe_val == 0

def run(cmd, tmo=180):
    c.mdi(cmd); t = time.time()
    while time.time() - t < tmo:
        time.sleep(0.1); s.poll()
        if s.interp_state == linuxcnc.INTERP_IDLE and time.time() - t > 0.5:
            return
    raise SystemExit('timeout on ' + cmd)

if a.axis == 'X':
    sub, width_p, center_p, edges, hint_p = 'probe_ridge_x', '#1001', '#1002', '#1006 #1005', '#3028'
else:
    sub, width_p, center_p, edges, hint_p = 'probe_ridge_y', '#1003', '#1004', '#1008 #1007', '#3029'

c.mode(linuxcnc.MODE_MDI); c.wait_complete()
run('#3030=1')                                   # measure only
if a.hint:
    run('%s=%.3f' % (hint_p, a.hint))
run('#3018=10')                                  # max search distance per side
new = not os.path.exists(out)
if new:
    run('(LOGOPEN,%s)' % out); run('(LOG,run width_g54 center_g54 minus_edge_g54 plus_edge_g54)'); run('(LOGCLOSE)')
for i in range(1, a.runs + 1):
    run('%s=-1' % width_p)
    run('o<%s> call' % sub)
    run('(LOGAPPEND,%s)' % out); run('(LOG,%d %s %s %s)' % (i, width_p, center_p, edges)); run('(LOGCLOSE)')
    last = open(out).read().strip().split('\n')[-1].split()
    print('run %2d  width %s  center %s' % (i, last[1], last[2]), flush=True)
    if float(last[1]) < 0:
        raise SystemExit('probe failed on run %d' % i)
c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
