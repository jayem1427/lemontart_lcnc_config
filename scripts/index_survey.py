#!/usr/bin/env python3
"""Find where an axis's encoder index (Z pulse) sits, without drive homing.

Why: drive homing "switch, then index" (docs/DRIVE_HOMING.md on branch
dev-drive-homing) lands on the first index next to the home switch edge. If
that index is within a fraction of a mm of the edge, switch scatter can pick
the neighbouring index and home jumps one screw turn (10 mm). This measures
the edge-to-index distance and the HOME_OFFSET that keeps machine zero where
it is today.

How: the drive's touch-probe function (0x60B8) can latch the position at the
encoder Z signal (on these absolute encoders: single-turn position = 0). The
script arms it over SDO, YOU jog the axis, and it reads the latch (0x60BA).
The script itself commands no motion and changes nothing but 0x60B8, which it
sets back to 0.

Run on the SWITCH-homing config (dev-jerk-testing), axis homed this session:

    source ~/src/linuxcnc-tpnext/scripts/rip-environment
    python3 scripts/index_survey.py X            # then jog X about 25 mm, slowly
    python3 scripts/index_survey.py Z --latches 2

--switch-pos is the machine coordinate of the home switch edge, which after
a LinuxCNC switch home is exactly the old HOME_OFFSET (X -5, Y -2, Z +2).
"""
import argparse, datetime, os, subprocess, sys, time
import linuxcnc

AX = {'X': 0, 'Y': 1, 'Z': 2, 'A': 3}
SWITCH = {'X': (-5.0, -1), 'Y': (-2.0, -1), 'Z': (2.0, +1)}   # edge position, end of travel it is at
CPR = 131072

ap = argparse.ArgumentParser()
ap.add_argument('axis', choices=list(AX))
ap.add_argument('--switch-pos', type=float, help='machine coordinate of the home switch edge')
ap.add_argument('--latches', type=int, default=2, help='index crossings to latch (default 2)')
ap.add_argument('--timeout', type=float, default=180.0)
a = ap.parse_args()
n = AX[a.axis]

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('FAILED: %s\n%s' % (' '.join(cmd), (r.stderr or r.stdout).strip()))
    return r.stdout.strip()

def up(typ, idx, sub=0):
    return int(sh('ethercat', 'upload', '-p', str(n), '-t', typ, hex(idx), str(sub)).split()[0], 0)

def down(typ, idx, val, sub=0):
    sh('ethercat', 'download', '-p', str(n), '-t', typ, hex(idx), str(sub), str(val))

s = linuxcnc.stat()
def sample():
    """(raw counts, joint position) taken close together, axis at rest."""
    s.poll()
    return int(sh('halcmd', 'getp', 'lcec.0.%d.pos-fb' % n)), s.joint_actual_position[n]

s.poll()
if not s.homed[n]:
    raise SystemExit('%s is not homed: home it on the switch first (machine coordinates must be valid)' % a.axis)
if not s.enabled:
    raise SystemExit('machine is off')

lines = []
def say(t=''):
    print(t, flush=True); lines.append(t)

say('# index survey %s (slave %d) %s' % (a.axis, n, datetime.datetime.now().isoformat(timespec='seconds')))
raw0, pos0 = sample()
latched = []
try:
    for i in range(a.latches):
        down('uint16', 0x60B8, 0)
        down('uint16', 0x60B8, 0x0015)      # probe 1: enable, single shot, Z signal, positive edge
        say('armed (%d/%d): jog %s slowly (<= 5 mm/s) one way, at least 11 mm ...' % (i + 1, a.latches, a.axis))
        t = time.time()
        while not up('uint16', 0x60B9) & 0x0002:
            if time.time() - t > a.timeout:
                raise SystemExit('no Z latch within %.0f s (did the axis move a full turn? is 0x60B8 writable by SDO?)' % a.timeout)
            time.sleep(0.2)
        latched.append(up('int32', 0x60BA))
        say('  latched raw %d   (mod %d = %d)' % (latched[-1], CPR, latched[-1] % CPR))
finally:
    try: down('uint16', 0x60B8, 0)
    except SystemExit: pass

input('stop jogging, wait for the axis to stand still, then press Enter ')
raw1, pos1 = sample()
if abs(pos1 - pos0) < 5:
    raise SystemExit('axis moved only %.2f mm between the two samples: cannot work out the scale' % (pos1 - pos0))
scale = (raw1 - raw0) / (pos1 - pos0)                   # counts per mm, signed
off = raw1 / scale - pos1                               # machine = raw / scale - off
say('scale %.2f counts/unit (expect +-13107.2)   machine = raw/scale - %.4f' % (scale, off))
res = [v % CPR for v in latched]
spread = max(res) - min(res)
say('index residue spread over %d latches: %d counts (%.2f um)%s' % (
    len(res), spread, abs(spread / scale) * 1000, '' if spread <= 8 else '   <-- NOT repeatable, stop and report'))

if a.axis in SWITCH:
    edge, end = SWITCH[a.axis]
    if a.switch_pos is not None: edge = a.switch_pos
    pitch = abs(CPR / scale)
    i0 = latched[0] / scale - off                       # one index, machine coordinates
    k = round((edge - i0) / pitch)
    cands = sorted(i0 + (k + d) * pitch for d in (-2, -1, 0, 1, 2))
    # the drive backs off the switch and takes the first index on the travel side of the edge
    home = min(c for c in cands if c > edge) if end < 0 else max(c for c in cands if c < edge)
    clr = abs(home - edge)
    say('home switch edge at machine %.3f (%s end). Index pitch %.3f mm.' % (edge, '-' if end < 0 else '+', pitch))
    say('index the drive will take: machine %.4f   -> clearance from the switch edge %.3f mm' % (home, clr))
    ok = 0.2 * pitch <= clr <= 0.8 * pitch
    say('clearance verdict: %s (want %.1f to %.1f mm)' % ('OK' if ok else 'MARGINAL - home can jump one turn; move the switch flag or re-clock the coupling', 0.2 * pitch, 0.8 * pitch))
    say('HOME_OFFSET that keeps machine zero where it is now: %.4f   (method %d)' % (home, 5 if end < 0 else 3))

d = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'drive_homing')
os.makedirs(d, exist_ok=True)
f = os.path.join(d, datetime.datetime.now().strftime('%Y-%m-%d_%H%M') + '_index_%s.txt' % a.axis)
open(f, 'w').write('\n'.join(lines) + '\n')
print('saved', os.path.normpath(f))
