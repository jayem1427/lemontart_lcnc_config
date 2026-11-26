"""Small numpy software renderer for the VISE STOP tab images.

Orthographic camera, z-buffer, smooth normals with a crease angle, studio-style
lighting with a fake environment reflection for metals, shadow map, cheap
screen-space AO and soft CAD outlines.  Supersampled, transparent background.

Only needs numpy, scipy and Pillow.  See make_images.py for the scene.
"""

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# ----------------------------------------------------------------------------- meshes

STL_DTYPE = np.dtype([("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])


def load_stl(path):
    with open(path, "rb") as fh:
        head = fh.read(80)
        if head.lstrip().lower().startswith(b"solid") and b"facet" in fh.read(512):
            raise ValueError("ASCII STL not supported: export STL (Binary)")
        fh.seek(80)
        n = int(np.frombuffer(fh.read(4), "<u4")[0])
        data = np.frombuffer(fh.read(n * 50), STL_DTYPE, count=n)
    return data["v"].astype(np.float64)


def box(x0, y0, z0, x1, y1, z1):
    p = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    q = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return p[np.array(q)]


def cylinder(cx, cy, z0, z1, r, n=48, r_top=None, cap=True):
    """Vertical cylinder (or cone frustum) along +z."""
    r_top = r if r_top is None else r_top
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    b = np.roll(a, -1)
    lo0 = np.stack([cx + r * np.cos(a), cy + r * np.sin(a), np.full(n, z0)], 1)
    lo1 = np.stack([cx + r * np.cos(b), cy + r * np.sin(b), np.full(n, z0)], 1)
    hi0 = np.stack([cx + r_top * np.cos(a), cy + r_top * np.sin(a), np.full(n, z1)], 1)
    hi1 = np.stack([cx + r_top * np.cos(b), cy + r_top * np.sin(b), np.full(n, z1)], 1)
    tris = [np.stack([lo0, lo1, hi1], 1), np.stack([lo0, hi1, hi0], 1)]
    if cap:
        c0 = np.tile([cx, cy, z0], (n, 1))
        c1 = np.tile([cx, cy, z1], (n, 1))
        tris += [np.stack([c0, lo1, lo0], 1), np.stack([c1, hi0, hi1], 1)]
    return np.concatenate(tris)


def prism(points2d, z0, z1):
    """Extrude a convex 2D polygon (CCW) along z."""
    p = np.asarray(points2d, float)
    n = len(p)
    tris = []
    c = p.mean(0)
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        tris.append([[a[0], a[1], z0], [b[0], b[1], z0], [b[0], b[1], z1]])
        tris.append([[a[0], a[1], z0], [b[0], b[1], z1], [a[0], a[1], z1]])
        tris.append([[c[0], c[1], z1], [a[0], a[1], z1], [b[0], b[1], z1]])
        tris.append([[c[0], c[1], z0], [b[0], b[1], z0], [a[0], a[1], z0]])
    return np.array(tris, float)


def transform(tris, R=None, t=(0, 0, 0)):
    out = tris.copy()
    if R is not None:
        out = out @ np.asarray(R).T
    return out + np.asarray(t, float)


def rot_z(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def smooth_normals(tris, crease_deg=35.0):
    """Per-corner normals: average adjacent face normals within the crease angle."""
    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    fn = np.cross(e1, e2)
    area = np.linalg.norm(fn, axis=1, keepdims=True)
    fn_u = fn / np.maximum(area, 1e-12)
    verts = tris.reshape(-1, 3)
    key = np.round(verts * 1e3).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    nv = inv.max() + 1
    face_of = np.repeat(np.arange(len(tris)), 3)
    # accumulate area-weighted normals per vertex, then pick per corner those
    # within the crease of the corner's own face: approximate with two passes
    acc = np.zeros((nv, 3))
    np.add.at(acc, inv, fn[face_of])
    vn = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    corner = vn[inv]
    own = fn_u[face_of]
    cos_c = np.cos(np.radians(crease_deg))
    ok = (corner * own).sum(1) >= cos_c
    corner[~ok] = own[~ok]
    return corner.reshape(-1, 3, 3), fn_u


def feature_edges(tris, angle_deg=30.0):
    """Edges whose two faces meet at more than angle_deg, plus open edges. Returns (E, 2, 3)."""
    fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    verts = tris.reshape(-1, 3)
    key = np.round(verts * 1e3).astype(np.int64)
    _, vid = np.unique(key, axis=0, return_inverse=True)
    vid = vid.reshape(-1, 3)
    e = np.concatenate([vid[:, [0, 1]], vid[:, [1, 2]], vid[:, [2, 0]]])
    face = np.tile(np.arange(len(tris)), 3)
    e.sort(axis=1)
    order = np.lexsort((e[:, 1], e[:, 0]))
    e, face = e[order], face[order]
    same = np.all(e[1:] == e[:-1], axis=1)
    keep = []
    # pairs of faces sharing an edge
    i_pair = np.nonzero(same)[0]
    cosang = (fn[face[i_pair]] * fn[face[i_pair + 1]]).sum(1)
    sharp = i_pair[cosang < np.cos(np.radians(angle_deg))]
    keep.append(sharp)
    # open edges: not part of any pair
    in_pair = np.zeros(len(e), bool)
    in_pair[i_pair] = True
    in_pair[i_pair + 1] = True
    keep.append(np.nonzero(~in_pair)[0])
    idx = np.concatenate(keep)
    # look up coordinates: first occurrence of each vertex id
    first = np.zeros(vid.max() + 1, np.int64)
    first[vid.reshape(-1)[::-1]] = np.arange(verts.shape[0])[::-1]
    p0 = verts[first[e[idx, 0]]]
    p1 = verts[first[e[idx, 1]]]
    return np.stack([p0, p1], 1)


# ----------------------------------------------------------------------------- camera

class Ortho:
    def __init__(self, azimuth_deg, elevation_deg):
        az, el = np.radians(azimuth_deg), np.radians(elevation_deg)
        # camera direction (from scene toward camera)
        c = np.array([np.cos(el) * np.sin(az), -np.cos(el) * np.cos(az), np.sin(el)])
        f = -c
        right = np.cross(f, [0, 0, 1.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, f)
        self.R = np.stack([right, up, f])  # rows
        self.cam_dir = c
        self.scale = 1.0
        self.offset = np.zeros(2)
        self.size = (100, 100)

    def fit(self, tris_list, size, margin=0.06):
        pts = np.concatenate([t.reshape(-1, 3) for t in tris_list])
        sc = pts @ self.R.T
        lo, hi = sc[:, :2].min(0), sc[:, :2].max(0)
        w, h = size
        self.scale = min(w * (1 - 2 * margin) / (hi[0] - lo[0]),
                         h * (1 - 2 * margin) / (hi[1] - lo[1]))
        mid = (lo + hi) / 2
        self.offset = np.array([w / 2 - mid[0] * self.scale, h / 2 + mid[1] * self.scale])
        self.size = size

    def project(self, p):
        """World -> (px, py, depth). py grows downward."""
        sc = np.asarray(p, float) @ self.R.T
        x = sc[..., 0] * self.scale + self.offset[0]
        y = -sc[..., 1] * self.scale + self.offset[1]
        return np.stack([x, y, sc[..., 2]], -1)

    def unproject(self, x, y, depth):
        sx = (x - self.offset[0]) / self.scale
        sy = -(y - self.offset[1]) / self.scale
        sc = np.stack([sx, sy, depth], -1)
        return sc @ self.R


# ----------------------------------------------------------------------------- raster

def rasterize(tris_screen, W, H, normals=None, attr_id=None):
    """Z-buffer rasterizer. Returns depth, normal, id buffers (depth = +inf for empty)."""
    depth = np.full((H, W), np.inf)
    nbuf = np.zeros((H, W, 3)) if normals is not None else None
    ibuf = np.full((H, W), -1, np.int32)
    P = tris_screen
    xmin = np.clip(np.floor(P[:, :, 0].min(1)).astype(int), 0, W - 1)
    xmax = np.clip(np.ceil(P[:, :, 0].max(1)).astype(int), 0, W - 1)
    ymin = np.clip(np.floor(P[:, :, 1].min(1)).astype(int), 0, H - 1)
    ymax = np.clip(np.ceil(P[:, :, 1].max(1)).astype(int), 0, H - 1)
    for t in range(len(P)):
        x0, x1, y0, y1 = xmin[t], xmax[t], ymin[t], ymax[t]
        if x1 < x0 or y1 < y0:
            continue
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = P[t]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not inside.any():
            continue
        z = w0 * az + w1 * bz + w2 * cz
        sub = depth[y0:y1 + 1, x0:x1 + 1]
        win = inside & (z < sub)
        if not win.any():
            continue
        sub[win] = z[win]
        ibuf[y0:y1 + 1, x0:x1 + 1][win] = attr_id[t] if attr_id is not None else t
        if nbuf is not None:
            n = (w0[..., None] * normals[t, 0] + w1[..., None] * normals[t, 1] +
                 w2[..., None] * normals[t, 2])
            nbuf[y0:y1 + 1, x0:x1 + 1][win] = n[win]
    return depth, nbuf, ibuf


# ----------------------------------------------------------------------------- shading

class Material:
    def __init__(self, color, metal=0.0, rough=0.5, emissive=0.0, spec=0.25):
        self.color = np.array(color, float) / 255.0
        self.metal = metal
        self.rough = rough
        self.emissive = emissive
        self.spec = spec


def _env(r):
    """Fake studio environment seen by a reflection vector r (world, z up)."""
    z = r[..., 2]
    sky = np.clip(0.55 + 0.45 * z, 0, 1)
    softbox = np.exp(-((z - 0.75) ** 2) / 0.02) * 0.9          # big overhead box
    side = np.exp(-((r[..., 0] + 0.6) ** 2 + (z - 0.2) ** 2) / 0.05) * 0.5   # left strip
    ground = np.where(z < -0.05, 0.12, 0.0)
    return np.clip(sky * 0.35 + softbox + side - ground, 0.0, 1.6)


def render(objects, cam, size=(760, 440), ss=3, light_dir=(-0.45, -0.35, 0.82),
           outline=0.35, ao_strength=0.45, shadow=True, fit=None, margin=0.06, ground=None,
           lines=True, line_px=1.4, line_angle=30.0):
    """objects: list of (tris, Material). Returns the supersampled RGBA image and the camera.

    fit: list of tris arrays the camera frames (default: everything)."""
    W, H = size[0] * ss, size[1] * ss
    cam.fit(fit if fit is not None else [o[0] for o in objects], (W, H), margin=margin)
    all_tris = np.concatenate([o[0] for o in objects])
    mats = [o[1] for o in objects]
    mat_id = np.concatenate([np.full(len(o[0]), i) for i, o in enumerate(objects)])
    vnorm, fnorm = smooth_normals(all_tris)

    scr = cam.project(all_tris)
    depth, nbuf, ibuf = rasterize(scr, W, H, vnorm, mat_id)
    mask = np.isfinite(depth)
    n = nbuf / np.maximum(np.linalg.norm(nbuf, axis=-1, keepdims=True), 1e-9)

    # world positions for shadowing
    ys, xs = np.mgrid[0:H, 0:W] + 0.5
    pos = cam.unproject(xs, ys, np.where(mask, depth, 0))

    L = np.array(light_dir, float)
    L /= np.linalg.norm(L)
    V = cam.cam_dir

    # shadow map from the key light (orthographic)
    shadow_f = np.ones((H, W))
    if shadow:
        lc = Ortho(0, 90)
        f = -L
        right = np.cross(f, [0, 1.0, 0])
        if np.linalg.norm(right) < 1e-6:
            right = np.cross(f, [1.0, 0, 0])
        right /= np.linalg.norm(right)
        up = np.cross(right, f)
        lc.R = np.stack([right, up, f])
        SW = 1400
        lc.fit([all_tris], (SW, SW), margin=0.02)
        ls = lc.project(all_tris)
        sdepth, _, _ = rasterize(ls, SW, SW)
        sdepth = ndimage.grey_erosion(np.where(np.isfinite(sdepth), sdepth, 1e9), size=2)
        pl = lc.project(pos[mask])
        px = np.clip(pl[:, 0].astype(int), 0, SW - 1)
        py = np.clip(pl[:, 1].astype(int), 0, SW - 1)
        bias = 0.35
        lit = pl[:, 2] <= sdepth[py, px] + bias
        sh = np.ones((H, W))
        sh[mask] = np.where(lit, 1.0, 0.0)
        sh = ndimage.gaussian_filter(sh, 1.2 * ss)
        shadow_f = 0.45 + 0.55 * sh

    # screen-space AO from the depth buffer
    dfill = np.where(mask, depth, np.nan)
    dmean = ndimage.uniform_filter(np.nan_to_num(dfill, nan=np.nanmax(dfill)), size=9 * ss)
    occl = np.clip((depth - dmean) / 6.0, 0, 1)
    ao = 1 - ao_strength * np.where(mask, occl, 0)

    base = np.zeros((H, W, 3))
    metal = np.zeros((H, W))
    rough = np.zeros((H, W))
    emis = np.zeros((H, W))
    specw = np.zeros((H, W))
    for i, m in enumerate(mats):
        sel = ibuf == i
        base[sel] = m.color
        metal[sel] = m.metal
        rough[sel] = m.rough
        emis[sel] = m.emissive
        specw[sel] = m.spec

    ndl = np.clip((n * L).sum(-1), 0, 1)
    fill = np.clip((n * np.array([0.6, -0.5, 0.3])).sum(-1), 0, 1) * 0.35
    hemi = 0.30 + 0.20 * n[..., 2]
    Hh = (L + V)
    Hh /= np.linalg.norm(Hh)
    shin = 8 + (1 - rough) * 120
    spec = np.clip((n * Hh).sum(-1), 0, 1) ** shin * specw * (1.5 - rough)
    r = 2 * (n * V).sum(-1, keepdims=True) * n - V
    env = _env(r)
    env = ndimage.gaussian_filter(env, 0.6 * ss)
    diffuse = base * (hemi + 0.85 * ndl * shadow_f + fill)[..., None]
    metallic = base * (0.25 + 0.95 * env)[..., None] * (0.55 + 0.45 * shadow_f)[..., None]
    col = diffuse * (1 - metal[..., None]) + metallic * metal[..., None]
    col = col * ao[..., None] + (spec * shadow_f)[..., None]
    col = col * (1 - emis[..., None]) + base * emis[..., None]

    # Fusion-style black lines: visible sharp mesh edges + silhouettes / object breaks
    if lines:
        line = np.zeros((H, W), bool)
        E = feature_edges(all_tris, line_angle)
        if len(E):
            Ps = cam.project(E)
            seg_len = np.linalg.norm(Ps[:, 1, :2] - Ps[:, 0, :2], axis=1)
            nsamp = np.maximum(2, np.ceil(seg_len)).astype(int)
            tot = nsamp.sum()
            rep = np.repeat(np.arange(len(E)), nsamp)
            start = np.repeat(np.cumsum(nsamp) - nsamp, nsamp)
            t = (np.arange(tot) - start) / np.maximum(np.repeat(nsamp, nsamp) - 1, 1)
            pts = Ps[rep, 0] + (Ps[rep, 1] - Ps[rep, 0]) * t[:, None]
            xi = np.clip(pts[:, 0].astype(int), 0, W - 1)
            yi = np.clip(pts[:, 1].astype(int), 0, H - 1)
            # visible if not behind the surface there (check a small neighbourhood)
            dmin = ndimage.minimum_filter(np.where(mask, depth, np.inf), size=3)
            dmax = ndimage.maximum_filter(np.where(mask, depth, -np.inf), size=3)
            bias = 0.25
            vis = (pts[:, 2] <= dmax[yi, xi] + bias) & (pts[:, 2] <= dmin[yi, xi] + 1.5) \
                | ~np.isfinite(dmin[yi, xi])
            line[yi[vis], xi[vis]] = True
        # silhouettes and object-to-object breaks from the buffers
        sil = ndimage.binary_dilation(mask) & ~ndimage.binary_erosion(mask)
        brk = (ndimage.maximum_filter(ibuf, 2) != ndimage.minimum_filter(ibuf, 2)) & mask
        dz = np.where(mask, depth, 1e6)
        jump = (ndimage.maximum_filter(dz, 2) - ndimage.minimum_filter(dz, 2)) > 3.0
        line |= sil | brk | (jump & mask)
        r_ = max(1, int(round(line_px * ss / 2)))
        line = ndimage.binary_dilation(line, iterations=r_ - 1) if r_ > 1 else line
        line_f = line.astype(float)
        col = col * (1 - 0.92 * line_f[..., None]) + 0.03 * line_f[..., None]
        mask = mask | line
    col = np.clip(col, 0, 1)
    rgba_extra = None
    if ground is not None and shadow:
        # soft contact shadow of the whole scene on a floor at z = ground, seen by the camera
        floor_pts = all_tris.reshape(-1, 3).copy()
        floor_pts = floor_pts - np.outer((floor_pts[:, 2] - ground) / L[2], L) * 0.15
        floor_pts[:, 2] = ground
        fp = cam.project(floor_pts)
        smask = np.zeros((H, W))
        xs_ = np.clip(fp[:, 0].astype(int), 0, W - 1)
        ys_ = np.clip(fp[:, 1].astype(int), 0, H - 1)
        smask[ys_, xs_] = 1.0
        smask = ndimage.binary_closing(smask > 0, iterations=6 * ss).astype(float)
        smask = ndimage.gaussian_filter(smask, 10 * ss) * 0.55
        rgba_extra = smask
    # gentle tone curve
    col = col ** (1 / 1.12)
    rgba = np.zeros((H, W, 4))
    rgba[..., :3] = col
    rgba[..., 3] = mask
    if rgba_extra is not None:
        sh = rgba_extra * (~mask)
        rgba[..., 3] = np.maximum(rgba[..., 3], sh)
    img = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")
    return img, cam


def downsample(img, ss):
    """Box-filter with premultiplied alpha."""
    a = np.asarray(img).astype(np.float64) / 255.0
    H, W = a.shape[0] // ss, a.shape[1] // ss
    a = a[:H * ss, :W * ss]
    rgb = a[..., :3] * a[..., 3:4]
    rgb = rgb.reshape(H, ss, W, ss, 3).mean((1, 3))
    al = a[..., 3].reshape(H, ss, W, ss).mean((1, 3))
    rgb = rgb / np.maximum(al[..., None], 1e-6)
    out = np.dstack([rgb, al])
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def overlay_draw(img):
    return ImageDraw.Draw(img, "RGBA")
