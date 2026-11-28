#!/usr/bin/env python3
"""Homing repeatability: re-home, then probe a block in the vise. Works on any homing config.

Each cycle: lift Z, move a random few mm away, unhome and home Z, X, Y (one at a
time), come back over the block, touch its top (Z), then run Probe Basic's ridge
probes for the X and Y centers. Everything is logged in G54 with measure-only
probing, so a shift of machine zero shows up 1:1 and no offset is changed.
The same script on dev-jerk-testing (switch homing) gives the baseline.

Setup (machine homed, block clamped in the vise, G54 roughly on the block):
  1. Load the touch probe (T99).
  2. Jog the stylus over the block center, about 2 mm above the top face.

    source ~/src/linuxcnc-tpnext/scripts/rip-environment
    python3 scripts/home_repeat_test.py logs/homing_repeat/<date>_<tag>.csv --cycles 20 --hint-x 51 --hint-y 53

Power-cycle series (the case that drifted tens of um with switch homing): run
once with --cycles 0 to save the start position, then after every restart +
REF ALL (probe still loaded, do not jog first):

    python3 scripts/home_repeat_test.py logs/homing_repeat/<date>_powercycle.csv --measure-only --note "restart 3"

Safety: the only moves below the start height are G38 probing moves. XY moves
are made 12 mm or more above the block top, so a home that is one screw turn
(10 mm) off still does not rapid into the block; it shows up as a ~10 mm
result and the script stops.
"""
import argparse, json, os, random, statistics, time
import linuxcnc

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--cycles', type=int, default=20)
ap.add_argument('--reps', type=int, default=2, help='ridge probes per axis per cycle')
ap.add_argument('--hint-x', type=float, help='block width in X + ~2 mm (default: keep #3028)')
ap.add_argument('--hint-y', type=float, help='block width in Y + ~2 mm (default: keep #3029)')
ap.add_argument('--scatter', type=float, default=15.0, help='random XY start offset before each home, mm')
ap.add_argument('--measure-only', action='store_true', help='no re-home: go to the saved position and measure once')
ap.add_argument('--note', default='')
ap.add_argument('--seed', type=int, default=1)
a = ap.parse_args()
out = os.path.abspath(a.out)
state_file = out + '.start.json'
os.makedirs(os.path.dirname(out), exist_ok=True)
rng = random.Random(a.seed)

c, s, e = linuxcnc.command(), linuxcnc.stat(), linuxcnc.error_channel()

def check():
    s.poll()
    if s.task_state != linuxcnc.STATE_ON:
        raise SystemExit('machine went off (E-stop or fault) - stopped')
    m = e.poll()
    if m and m[0] in (linuxcnc.OPERATOR_ERROR, linuxcnc.NML_ERROR):
        raise SystemExit('LinuxCNC error: ' + m[1])

def run(cmd, tmo=180):
    c.mdi(cmd); t = time.time()
    while time.time() - t < tmo:
        time.sleep(0.05); check()
        if s.interp_state == linuxcnc.INTERP_IDLE and time.time() - t > 0.3:
            return
    raise SystemExit('timeout on ' + cmd)

def mdi_mode():
    c.mode(linuxcnc.MODE_MDI); c.wait_complete()

def rehome(order=(2, 0, 1), tmo=240):
    c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()
    c.teleop_enable(0); c.wait_complete()
    for j in order:
        c.unhome(j)
    c.wait_complete(); time.sleep(0.5)
    for j in order:
        c.home(j); t = time.time(); time.sleep(0.5)
        while True:
            time.sleep(0.1); check()
            if s.homed[j] and not s.joint[j]['homing'] and s.joint[j]['inpos']:
                break
            if time.time() - t > tmo:
                raise SystemExit('joint %d did not home in %d s' % (j, tmo))
        if time.time() - t < 1.0:
            raise SystemExit('joint %d reported homed with no motion (homed in place?) - stopped' % j)
    time.sleep(1.0)

def measure(tag):
    """Probe at the saved spot; append one row. Returns the row as floats."""
    mdi_mode()
    run('G90 G54 G43 G21')
    run('G53 G0 Z%.4f' % min(st['z'] + 12.0, -1.0))       # 14 mm above the top if home is right
    run('G53 G0 X%.4f Y%.4f' % (st['x'], st['y']))
    run('G91 G38.3 Z-30 F600'); run('G90')
    s.poll()
    if not s.probe_tripped:
        raise SystemExit('no block top within 30 mm - stopped')
    run('G91 G0 Z1'); run('G91 G38.3 Z-2 F40'); run('G90')
    run('#<_hr_top>=#5063')                                    # block top, G54 Z
    run('G91 G0 Z2'); run('G90')
    run('#3030=1'); run('#3018=10')                       # measure only; 10 mm search per side
    if a.hint_x: run('#3028=%.3f' % a.hint_x)
    if a.hint_y: run('#3029=%.3f' % a.hint_y)
    rows = []
    for rep in range(a.reps):
        run('#1001=-1'); run('o<probe_ridge_x> call')
        run('#1003=-1'); run('o<probe_ridge_y> call')
        run('(LOGAPPEND,%s)' % out)
        run('(LOG,%s %d #<_hr_top> #1002 #1001 #1004 #1003)' % (tag, rep + 1))
        run('(LOGCLOSE)')
        last = open(out).read().strip().split('\n')[-1].split()
        vals = [float(v) for v in last[2:7]]
        print('  %s rep %d  top Z %.4f  X center %.4f (w %.4f)  Y center %.4f (w %.4f)' % (tag, rep + 1, *vals), flush=True)
        if vals[2] < 0 or vals[4] < 0:
            raise SystemExit('ridge probe failed - stopped (home one screw turn off?)')
        rows.append(vals)
    return [statistics.mean(r[i] for r in rows) for i in range(5)]

s.poll()
assert s.tool_in_spindle == 99, 'load the touch probe (T99) first'
assert all(s.homed[:3]) and s.interp_state == linuxcnc.INTERP_IDLE, 'home X Y Z first, interpreter idle'
assert s.probe_val == 0, 'probe input is already tripped'

if a.measure_only:
    st = json.load(open(state_file))
else:
    p = s.joint_actual_position
    st = {'x': p[0], 'y': p[1], 'z': p[2]}
    assert st['z'] < -13.5, 'start Z too close to the top of travel for the 12 mm clearance move'
    json.dump(st, open(state_file, 'w'))
    print('start position (machine) X%.4f Y%.4f Z%.4f saved to %s' % (st['x'], st['y'], st['z'], state_file))
if not os.path.exists(out):
    mdi_mode()
    run('(LOGOPEN,%s)' % out); run('(LOG,tag rep top_z_g54 x_center_g54 x_width y_center_g54 y_width)'); run('(LOGCLOSE)')

results = []
if a.measure_only:
    results.append(measure((a.note or 'measure').replace(' ', '_')))
else:
    results.append(measure('start'))
    for i in range(1, a.cycles + 1):
        mdi_mode()
        run('G53 G0 Z%.4f' % min(st['z'] + 30.0, -1.0))
        run('G53 G0 X%.4f Y%.4f' % (st['x'] + rng.uniform(-a.scatter, a.scatter), st['y'] + rng.uniform(-a.scatter, a.scatter)))
        print('cycle %d/%d: homing Z, X, Y' % (i, a.cycles), flush=True)
        rehome()
        results.append(measure('home%02d' % i))
mdi_mode(); run('G53 G0 Z%.4f' % min(st['z'] + 12.0, -1.0))
c.mode(linuxcnc.MODE_MANUAL); c.wait_complete()

if len(results) > 2:
    print('\nspread over %d homes (first row = before any re-home):' % (len(results) - 1))
    for i, name in ((0, 'Z (block top)'), (1, 'X center'), (3, 'Y center')):
        v = [r[i] for r in results[1:]]
        print('  %-14s range %6.1f um   std %5.1f um   shift vs start %+6.1f um' % (
            name, (max(v) - min(v)) * 1000, statistics.pstdev(v) * 1000, (statistics.mean(v) - results[0][i]) * 1000))
print('rows in', out)
