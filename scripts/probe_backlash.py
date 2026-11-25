#!/usr/bin/env python3
"""Probe-based reversal (backlash + probe hysteresis) check on the test block.

For each face: touch it slowly (G38.2), then back away slowly until the probe
releases (G38.4). The gap between touch and release, in machine coordinates,
is axis reversal error + probe hysteresis. The Z top (gravity-loaded) gives
the probe-hysteresis baseline.

Needs: T99 loaded with its length, G54 on the block center (X/Y) and top (Z),
probe parked over the center about 2 mm above the top. All moves are G38.

Usage: python3 scripts/probe_backlash.py out.csv [--cycles 5]
"""
import argparse, time, statistics as st
import linuxcnc

ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--cycles', type=int, default=5)
ap.add_argument('--faces', default='XYZ', help='which checks to run, e.g. YZ')
a = ap.parse_args()

HALF_X, HALF_Y = 25.37, 25.40     # block half-widths (G54), from the ridge runs
CLEAR = 2.0                        # tip height above the top (G54 Z) for moves
DEPTH = -3.0                       # probing depth for side faces (G54 Z)
SLOW = 20

c = linuxcnc.command(); s = linuxcnc.stat(); e = linuxcnc.error_channel()
s.poll()
assert s.tool_in_spindle == 99 and s.probe_val == 0 and s.interp_state == linuxcnc.INTERP_IDLE

def run(cmd, tmo=60):
    c.mdi(cmd); t = time.time()
    while time.time() - t < tmo:
        time.sleep(0.03); s.poll(); m = e.poll()
        if m and m[0] in (linuxcnc.OPERATOR_ERROR, linuxcnc.NML_ERROR):
            raise SystemExit('LinuxCNC error on %r: %s' % (cmd, m[1]))
        if s.interp_state == linuxcnc.INTERP_IDLE and time.time() - t > 0.15:
            return
    raise SystemExit('timeout on ' + cmd)

def probed(ax):
    s.poll(); return s.probed_position[ax]

c.mode(linuxcnc.MODE_MDI); c.wait_complete()
run('G90 G54 G43')
rows = []

def side(name, ax, letter, face, sign):
    """Face at G54 `face` on axis `letter`; probe moves in direction `sign` (+1/-1) to touch it."""
    start = face - sign * 4.0
    other = 'Y' if letter == 'X' else 'X'
    run('G90 G38.3 Z%.3f F3000' % CLEAR)
    run('G90 G38.3 %s0 F3000' % other)          # stay on the face's centre line
    run('G90 G38.3 %s%.3f F3000' % (letter, start))
    run('G90 G38.3 Z%.3f F800' % DEPTH)
    s.poll(); assert s.probe_val == 0, 'probe tripped on the way down beside the %s face' % name
    for i in range(a.cycles):
        run('G91 G38.2 %s%.3f F200' % (letter, sign * 8))
        run('G91 G1 %s%.3f F800' % (letter, -sign * 1.0))
        run('G91 G38.2 %s%.3f F%d' % (letter, sign * 2.0, SLOW)); touch = probed(ax)
        run('G91 G38.4 %s%.3f F%d' % (letter, -sign * 1.0, SLOW)); release = probed(ax)
        gap = (touch - release) * sign * 1000
        rows.append((name, i + 1, touch, release, gap))
        print('%-6s %d  touch %.4f  release %.4f  gap %.2f um' % (name, i + 1, touch, release, gap), flush=True)
        run('G90 G38.3 %s%.3f F800' % (letter, start))
    run('G90 G38.3 Z%.3f F800' % CLEAR)

if 'X' in a.faces: side('X-face', 0, 'X', -HALF_X, +1)
if 'Y' in a.faces: side('Y-face', 1, 'Y', -HALF_Y, +1)

# Z top at the center: gravity-loaded baseline
run('G90 G38.3 Z%.3f F3000' % CLEAR)
run('G90 G38.3 X0 Y0 F3000')
for i in (range(a.cycles) if 'Z' in a.faces else []):
    run('G91 G38.2 Z-4 F200'); run('G91 G1 Z1 F800')
    run('G91 G38.2 Z-2 F%d' % SLOW); touch = probed(2)
    run('G91 G38.4 Z1 F%d' % SLOW); release = probed(2)
    gap = (release - touch) * 1000
    rows.append(('Z-top', i + 1, touch, release, gap))
    print('%-6s %d  touch %.4f  release %.4f  gap %.2f um' % ('Z-top', i + 1, touch, release, gap), flush=True)
    run('G90 G38.3 Z%.3f F800' % CLEAR)

run('G90')
c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
with open(a.out, 'w') as f:
    f.write('face,cycle,touch_machine,release_machine,gap_um\n')
    for r in rows: f.write('%s,%d,%.5f,%.5f,%.3f\n' % r)
for name in ('X-face', 'Y-face', 'Z-top'):
    g = [r[4] for r in rows if r[0] == name]
    if len(g) < 2: continue
    print('%-6s gap mean %.2f um  sd %.2f' % (name, st.mean(g), st.stdev(g)))
