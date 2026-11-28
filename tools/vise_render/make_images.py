"""Render the VISE STOP tab images from the H67 meshes exported from Fusion.

    python3 make_images.py h67_vise.stl h67_jaws.stl OUT_DIR

Writes vise_<X|Y>_<pos|neg>.png (jaw axis, part side of the pin) and meta.json
(pixel positions the tab uses to map a tap to a side).  Meshes: Fusion "Save As Mesh",
STL (Binary), mm.  Vise mesh: clamp along mesh X, jaws along mesh Y, z up.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import render as r

SIZE = (720, 400)
SS = 4

# scene numbers (mm, vise frame: u along the jaws, v clamp axis, z up, z = 0 body top)
JAW_SINK = 2.5          # jaw key sits this far into the body
PARALLEL_H = 10.0
Z0 = PARALLEL_H         # vise WCS Z0 = parallel top (part bottom)
JAW_FACE = 22.0         # jaw faces at v = +-22 in the exported jaw position
PART_L, PART_H = 50.0, 30.0
PIN_R = 3.0
STOP_Z = 5.0            # pin tip above Z0 in the picture

M_BODY = r.Material((92, 96, 102), metal=0.45, rough=0.5, spec=0.3)     # black oxide body
M_JAW = r.Material((176, 180, 186), metal=0.8, rough=0.38, spec=0.45)     # ground steel jaws
M_PART = r.Material((178, 190, 204), metal=0.65, rough=0.55, spec=0.25)   # aluminium stock
M_PAR = r.Material((128, 134, 140), metal=0.8, rough=0.35, spec=0.4)
M_PIN = r.Material((236, 238, 242), metal=0.95, rough=0.15, spec=0.8)
M_NUT = r.Material((190, 193, 198), metal=0.85, rough=0.28, spec=0.6)
M_SPIN = r.Material((150, 155, 162), metal=0.35, rough=0.45, spec=0.35)

C_PUSH = (226, 32, 32, 240)
C_X, C_Y, C_Z = (239, 41, 41, 255), (115, 210, 22, 255), (52, 101, 255, 255)


def load(vise_stl, jaws_stl):
    """Vise frame: u along the jaws, v clamp axis, z up, origin at the vise center on the body top.

    Fusion's "Save As Mesh" writes each component in its own coordinates, so the
    jaws are placed here: centered on the vise, turned right side up (the
    exported jaw component is upside down: narrow upright with the grip teeth
    goes on top), base sitting on the body top.
    """
    v = r.load_stl(vise_stl)
    j = r.load_stl(jaws_stl)
    vp, jp = v.reshape(-1, 3), j.reshape(-1, 3)
    vc = (vp.min(0) + vp.max(0)) / 2
    jc = (jp.min(0) + jp.max(0)) / 2
    v = v - [vc[0], vc[1], vp[:, 2].max()]
    j = j - jc
    # mesh X = clamp, mesh Y = along the jaws -> u = mesh Y, v = -mesh X (proper rotation)
    rot = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1.0]])
    v = v @ rot.T
    j = j @ rot.T
    # jaws right side up: 180 deg about the u axis
    flip = np.diag([1.0, -1.0, -1.0])
    j = j @ flip.T
    j = j - [0, 0, j.reshape(-1, 3)[:, 2].min() + JAW_SINK]
    return v, j


PIN_STICK = 45.0         # stop pin stickout below the collet nut


def spindle_parts(u_pin, z_tip):
    k = z_tip + PIN_STICK
    pin = r.cylinder(u_pin, 0, z_tip, k, PIN_R, n=48)
    nut_cone = r.cylinder(u_pin, 0, k - 3, k, 5, n=64, r_top=13, cap=False)
    nut = r.cylinder(u_pin, 0, k, k + 10, 13.5, n=72)
    nose = r.cylinder(u_pin, 0, k + 10, k + 16, 17, n=72, r_top=19)
    body = r.cylinder(u_pin, 0, k + 16, k + 90, 21, n=72)
    return [(pin, M_PIN), (nut_cone, M_NUT), (nut, M_NUT), (nose, M_NUT), (body, M_SPIN)]


def scene(vise, jaws, side):
    """All in the vise frame. side = +1: part toward + of the pin (pin on the - side)."""
    u_pin = -side * (PART_L / 2 + PIN_R)
    part = r.box(-PART_L / 2, -JAW_FACE, Z0, PART_L / 2, JAW_FACE, Z0 + PART_H)
    pars = [r.box(-PART_L / 2 - 4, JAW_FACE - 5, 0, PART_L / 2 + 4, JAW_FACE, Z0),
            r.box(-PART_L / 2 - 4, -JAW_FACE, 0, PART_L / 2 + 4, -JAW_FACE + 5, Z0)]
    objs = [(vise, M_BODY), (jaws, M_JAW), (part, M_PART)] + [(p, M_PAR) for p in pars]
    objs += spindle_parts(u_pin, Z0 + STOP_Z)
    fit = [vise, jaws, part, r.box(u_pin - 14, -14, Z0, u_pin + 14, 14, Z0 + STOP_Z + PIN_STICK + 14)]
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


C_AXIS = (240, 240, 240, 255)


def draw_axes(d, cam, size):
    """Corner indicator: +X and +Y machine directions as the camera sees them."""
    from PIL import ImageFont
    font = ImageFont.load_default(size=int(22 * SS))
    o2 = np.array([92.0, size[1] - 78.0]) * SS          # bottom-left corner
    L = 62.0 * SS
    zero = cam.project(np.zeros(3))[:2]
    for vec, label in (((1.0, 0, 0), "+X"), ((0, 1.0, 0), "+Y")):
        dv = cam.project(np.array(vec) * 10.0)[:2] - zero
        dv = dv / np.linalg.norm(dv)
        tip = o2 + dv * L
        nrm = np.array([-dv[1], dv[0]])
        w, hl, hw = 2.2 * SS, 13 * SS, 7 * SS
        base = tip - dv * hl
        shaft = [o2 + nrm * w, base + nrm * w, base - nrm * w, o2 - nrm * w]
        head = [base + nrm * hw, tip, base - nrm * hw]
        for poly in (shaft, head):
            d.polygon([tuple(q) for q in poly], fill=C_AXIS, outline=(20, 20, 20, 255), width=SS)
        lp = o2 + dv * (L + 20 * SS)
        bb = d.textbbox((0, 0), label, font=font, stroke_width=SS)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((lp[0] - tw / 2, lp[1] - th / 2 - bb[1]), label, fill=C_AXIS, font=font,
               stroke_width=SS, stroke_fill=(20, 20, 20, 255))
    r_ = 4 * SS
    d.ellipse([o2[0] - r_, o2[1] - r_, o2[0] + r_, o2[1] + r_], fill=C_AXIS,
              outline=(20, 20, 20, 255), width=SS)


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
            img, cam = r.render(objs_m, cam, size=SIZE, ss=SS, fit=fit_m, margin=0.04,
                                ground=None)
            d = ImageDraw.Draw(img, "RGBA")
            draw_axes(d, cam, SIZE)
            z_top = Z0 + PART_H + 0.2
            far = side * (PART_L / 2 - 6)
            near = -side * (PART_L / 2 - 3)
            draw_arrow(d, cam, R, (far, 0, z_top), (near, 0, z_top), 7.0, C_PUSH)
            out = r.downsample(img, SS)
            name = "vise_{}_{}.png".format(axis, sname)
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
