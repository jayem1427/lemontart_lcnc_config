"""Render the VISE STOP tab images from the H67 meshes exported from Fusion.

    python3 make_images.py h67_vise.stl h67_jaws.stl OUT_DIR

Writes vise_<X|Y>_<pos|neg>_<edge|center>.png and meta.json (pixel positions
the tab uses to map a tap to a part side).  Meshes: Fusion "Save As Mesh",
STL (Binary), mm.  Vise mesh: clamp along mesh X, jaws along mesh Y, z up.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import render as r

SIZE = (720, 400)
SS = 3

# scene numbers (mm, vise frame: u = along the jaws, v = clamp axis, z up)
BODY_TOP = 9.0          # jaws sit here
PARALLEL_H = 8.0
Z0 = BODY_TOP + PARALLEL_H          # vise WCS Z0 = parallel top
JAW_FACE = 22.0         # jaw faces at v = +-22 in the exported jaw position
PART_L, PART_H = 40.0, 21.0
PIN_R = 3.0
STOP_Z = 5.0            # pin tip above Z0 in the picture

M_BODY = r.Material((74, 78, 84), metal=0.35, rough=0.45, spec=0.35)
M_JAW = r.Material((168, 171, 176), metal=0.75, rough=0.32, spec=0.5)
M_PART = r.Material((196, 203, 212), metal=0.55, rough=0.45, spec=0.35)
M_PAR = r.Material((140, 146, 152), metal=0.8, rough=0.3, spec=0.5)
M_PIN = r.Material((226, 228, 232), metal=0.95, rough=0.12, spec=0.9)
M_NUT = r.Material((182, 185, 190), metal=0.85, rough=0.25, spec=0.7)
M_SPIN = r.Material((112, 117, 124), metal=0.2, rough=0.5, spec=0.3)

C_PUSH = (94, 200, 255, 235)
C_X, C_Y, C_Z = (239, 41, 41, 255), (115, 210, 22, 255), (52, 101, 255, 255)


def load(vise_stl, jaws_stl):
    v = r.load_stl(vise_stl)
    j = r.load_stl(jaws_stl)
    vp, jp = v.reshape(-1, 3), j.reshape(-1, 3)
    vc = (vp.min(0) + vp.max(0)) / 2
    jc = (jp.min(0) + jp.max(0)) / 2
    v = v - [vc[0], vc[1], 0]
    j = j - [jc[0], jc[1], 0]
    # vise frame: u along the jaws = mesh Y, v clamp = -mesh X (a proper rotation)
    rot = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1.0]])
    v = v @ rot.T
    j = j @ rot.T
    return v, j


PIN_STICK = 40.0         # stop pin stickout below the collet nut


def spindle_parts(u_pin, z_tip):
    k = z_tip + PIN_STICK
    pin = r.cylinder(u_pin, 0, z_tip, k, PIN_R, n=40)
    chamfer = r.cylinder(u_pin, 0, z_tip - 0.5, z_tip, PIN_R - 0.5, n=40, r_top=PIN_R)
    nut_cone = r.cylinder(u_pin, 0, k - 2, k, 6, n=48, r_top=15, cap=False)
    nut = r.cylinder(u_pin, 0, k, k + 11, 15, n=64)
    nose = r.cylinder(u_pin, 0, k + 11, k + 17, 19, n=64)
    body = r.cylinder(u_pin, 0, k + 17, k + 110, 24, n=72)
    return [(pin, M_PIN), (chamfer, M_PIN), (nut_cone, M_NUT), (nut, M_NUT), (nose, M_NUT),
            (body, M_SPIN)]


def scene(vise, jaws, side):
    """All in the vise frame (u, v, z). side = +1 part on the + side of the pin."""
    u_pin = -side * (PART_L / 2 + PIN_R)
    part = r.box(-PART_L / 2, -JAW_FACE, Z0, PART_L / 2, JAW_FACE, Z0 + PART_H)
    pars = [r.box(-PART_L / 2 - 6, JAW_FACE - 6, BODY_TOP, PART_L / 2 + 6, JAW_FACE, Z0),
            r.box(-PART_L / 2 - 6, -JAW_FACE, BODY_TOP, PART_L / 2 + 6, -JAW_FACE + 6, Z0)]
    objs = [(vise, M_BODY), (jaws, M_JAW), (part, M_PART)] + [(p, M_PAR) for p in pars]
    objs += spindle_parts(u_pin, Z0 + STOP_Z)
    fit = [vise, jaws, part, r.box(u_pin - 16, -16, Z0, u_pin + 16, 16, Z0 + STOP_Z + PIN_STICK + 24)]
    return objs, fit, u_pin


def camera(axis, side):
    """Operator's view from the front, swung toward the pin so it is not hidden by the part."""
    if axis == "X":
        return r.Ortho(-38 if side > 0 else 38, 38)   # pin on -X: look from front-left
    return r.Ortho(30, 50 if side < 0 else 38)          # pin at +Y (back): look over the part


def to_machine(objs, fit, axis):
    """axis 'X': u -> machine +X, v -> machine +Y.  axis 'Y': u -> +Y, v -> -X."""
    R = np.eye(3) if axis == "X" else r.rot_z(90)
    return [(o @ R.T, m) for o, m in objs], [f @ R.T for f in fit], R


def draw_arrow(d, cam, R, a, b, width, col, head=None):
    """Flat arrow in the plane z = a[2], from a to b (vise frame), drawn over the image."""
    a, b = np.array(a, float), np.array(b, float)
    t = (b - a) / np.linalg.norm(b - a)
    n = np.array([-t[1], t[0], 0])
    head = head or width * 2.4
    hw = width / 2
    shaft_end = b - t * head
    poly = [a + n * hw, shaft_end + n * hw, shaft_end + n * hw * 2.6, b,
            shaft_end - n * hw * 2.6, shaft_end - n * hw, a - n * hw]
    pts = cam.project(np.array(poly) @ R.T)[:, :2]
    d.polygon([tuple(p) for p in pts], fill=col, outline=(20, 30, 40, 255), width=SS)


def draw_triad(d, cam, R, origin, L=16.0):
    o = cam.project(np.array(origin) @ R.T)[:2]
    for axis_dir, col in (((1, 0, 0), C_X), ((0, 1, 0), C_Y), ((0, 0, 1), C_Z)):
        e = cam.project(np.array(origin) @ R.T + np.array(axis_dir, float) * L)[:2]
        v = e - o
        nrm = np.array([-v[1], v[0]]) / max(np.linalg.norm(v), 1e-6)
        hl = 0.32 * v
        d.line([tuple(o), tuple(e - hl * 0.6)], fill=col, width=3 * SS)
        tip = [tuple(e), tuple(e - hl + nrm * 3.2 * SS), tuple(e - hl - nrm * 3.2 * SS)]
        d.polygon(tip, fill=col)
    rad = 5 * SS
    d.ellipse([o[0] - rad, o[1] - rad, o[0] + rad, o[1] + rad], fill=(255, 255, 255, 255),
              outline=(20, 20, 20, 255), width=SS)


def main(vise_stl, jaws_stl, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    vise, jaws = load(vise_stl, jaws_stl)
    meta = {"size": SIZE, "images": {}}
    for axis in ("X", "Y"):
        for side, sname in ((1, "pos"), (-1, "neg")):
            objs, fit, u_pin = scene(vise, jaws, side)
            objs_m, fit_m, R = to_machine(objs, fit, axis)
            cam = camera(axis, side)
            img, cam = r.render(objs_m, cam, size=SIZE, ss=SS, fit=fit_m, margin=0.05)
            for mode in ("edge", "center"):
                im = img.copy()
                d = ImageDraw.Draw(im, "RGBA")
                z_top = Z0 + PART_H + 0.2
                far = side * (PART_L / 2 - 4)
                near = -side * (PART_L / 2 - 2)
                draw_arrow(d, cam, R, (far, 0, z_top), (near, 0, z_top), 6.0, C_PUSH)
                u_org = 0.0 if mode == "center" else -side * PART_L / 2
                draw_triad(d, cam, R, (u_org, 0, Z0))
                out = r.downsample(im, SS)
                name = "vise_{}_{}_{}.png".format(axis, sname, mode)
                out.save(os.path.join(out_dir, name), optimize=True)
                c = cam.project(np.zeros(3))[:2] / SS
                pu = cam.project(np.array([10.0, 0, 0]) @ R.T)[:2] / SS - c
                meta["images"][name] = {"center": [round(float(x), 1) for x in c],
                                        "u_dir": [round(float(x), 3) for x in pu / np.linalg.norm(pu)]}
                print("wrote", name, flush=True)
    with open(os.path.join(out_dir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
