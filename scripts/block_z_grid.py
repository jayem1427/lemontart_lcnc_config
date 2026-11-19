#!/usr/bin/env python3
"""16x16 Z probe map of the block top (touch probe T99).

Usage: python3 scripts/block_z_grid.py out.csv   (tpnext rip-environment sourced)
Writes CSV: i,j,x_g54,y_g54,z_machine. Grid is G54 X/Y -22.5..+22.5 at 3 mm pitch,
for the 50.74 x 50.81 mm block zeroed 2026-11-18 (G54 X97.013 Y141.8911).
CLEAR_Z is a machine Z about 2 mm above that block's top. If the part moved,
re-zero G54 and update G54_X/G54_Y/CLEAR_Z first; the script refuses to run
when G54 doesn't match. Moves between points are G38.3, so they stop on contact.
"""
import linuxcnc, time, sys

OUT = sys.argv[1]
N, HALF = 16, 22.5           # points per side, G54 half-extent (mm)
CLEAR_Z = -15.37             # machine Z, ~2 mm above block top
G54_X, G54_Y = 97.013, 141.8911
FAST, SLOW, TRAV = 200, 50, 800

c = linuxcnc.command(); s = linuxcnc.stat(); e = linuxcnc.error_channel()
s.poll()
assert s.tool_in_spindle == 99 and all(s.homed[:3]) and s.interp_state == linuxcnc.INTERP_IDLE
assert abs(s.g5x_offset[0] - G54_X) < 1e-3 and abs(s.g5x_offset[1] - G54_Y) < 1e-3 and s.g5x_index == 1, 'G54 does not match'

c.mode(linuxcnc.MODE_MDI); c.wait_complete()

def run(cmd, tmo=60):
    c.mdi(cmd); t = time.time()
    while time.time() - t < tmo:
        time.sleep(0.02); s.poll()
        m = e.poll()
        if m and m[0] in (linuxcnc.OPERATOR_ERROR, linuxcnc.NML_ERROR):
            raise SystemExit('LinuxCNC error on %r: %s' % (cmd, m[1]))
        if s.interp_state == linuxcnc.INTERP_IDLE and time.time() - t > 0.15:
            return
    raise SystemExit('timeout on ' + cmd)

step = 2 * HALF / (N - 1)
run('G90 G54')
run('G53 G1 Z%.4f F%d' % (CLEAR_Z, TRAV))
t0 = time.time()
with open(OUT, 'w') as f:
    f.write('i,j,x_g54,y_g54,z_machine\n')
    for j in range(N):
        cols = range(N) if j % 2 == 0 else range(N - 1, -1, -1)
        for i in cols:
            x, y = -HALF + i * step, -HALF + j * step
            run('G90 G38.3 X%.4f Y%.4f F%d' % (x, y, TRAV))
            s.poll()
            if abs(s.position[0] - (G54_X + x)) > 0.01 or abs(s.position[1] - (G54_Y + y)) > 0.01:
                raise SystemExit('XY move stopped early at point %d,%d' % (i, j))
            run('G91 G38.2 Z-4 F%d' % FAST)
            run('G91 G1 Z0.5 F%d' % TRAV)
            run('G91 G38.2 Z-1 F%d' % SLOW)
            s.poll(); z = s.probed_position[2]
            run('G90'); run('G53 G1 Z%.4f F%d' % (CLEAR_Z, TRAV))
            f.write('%d,%d,%.4f,%.4f,%.5f\n' % (i, j, x, y, z)); f.flush()
        print('row %2d done  %.0fs' % (j + 1, time.time() - t0), flush=True)
run('G90')
c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
print('DONE')
