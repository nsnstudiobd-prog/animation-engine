"""Rigged 2D cartoon character.

* Two-bone IK legs (planted feet, no sliding) and arms (reach targets).
* Head drawn with a pseudo-3D projection: facial features live on a sphere
  (longitude/latitude) so the head can turn (yaw), nod (pitch) and tilt (roll)
  while keeping consistent proportions.
* Face rig: eyes (openness, gaze, blink, squint), brows (raise, angle),
  mouth (jaw open, width, rounding, smile) driven by the lip-sync module.
"""
import math
import skia
from .draw import (paint, poly, smooth_path, ellipse, capsule, union, intersect,
                   difference, shifted, cel, hexc, mix)

SKIN = dict(base="#b8774c", shade="#8a5434", rim="#ffbe82", line="#3b2016", hi="#d79b6b")

HERO = dict(
    skin=SKIN,
    hair="#17110f", hair_hi="#3d2c26",
    shirt="#2e8f8a", shirt_shade="#1e6461", shirt_line="#133c3c", shirt_check="#4fb3a8",
    pants="#2b2f48", pants_shade="#1c1f33", pants_line="#0f1120",
    sandal="#5a3420", sandal_line="#2a160c",
    watch="#20232b", style="quiff", stubble=True, mustache=False, cap=False,
)

KEEPER = dict(
    skin=dict(base="#9c6440", shade="#734326", rim="#ffb877", line="#2e170d", hi="#bb7f55"),
    hair="#2a2a2a", hair_hi="#555555",
    shirt="#e9e2cf", shirt_shade="#c2b89d", shirt_line="#6b6250", shirt_check=None,
    style="short", stubble=False, mustache=True, cap=True, beard=True,
)

L = dict(thigh=114, shin=110, upper=80, fore=74, torso=150, hip_h=226)


def ik2(a, t, l1, l2, bend):
    ax, ay = a
    dx, dy = t[0] - ax, t[1] - ay
    d = math.hypot(dx, dy)
    d = max(abs(l1 - l2) + 1e-3, min(l1 + l2 - 1e-3, d))
    base = math.atan2(dy, dx)
    c = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    al = math.acos(max(-1, min(1, c)))
    j = (ax + l1 * math.cos(base + bend * al), ay + l1 * math.sin(base + bend * al))
    # end point (clamped reach)
    ang2 = math.atan2(t[1] - j[1], t[0] - j[0])
    e = (j[0] + l2 * math.cos(ang2), j[1] + l2 * math.sin(ang2))
    return j, e


def rot(p, a, o=(0, 0)):
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] - o[0], p[1] - o[1]
    return (o[0] + x * c - y * s, o[1] + x * s + y * c)


# ----------------------------------------------------------------------------- head
def draw_head(cv, cx, cy, s, yaw, pitch, roll, face, st, lw=2.2):
    """face: eye_open, blink, gaze(x,y), brow(raise_l, raise_r), brow_ang(l,r),
    squint, mouth(open, wide, round, smile)."""
    sk = st["skin"]
    cv.save()
    cv.translate(cx, cy)
    cv.rotate(math.degrees(roll))
    cv.scale(s, s)
    R = 42.0
    sy = math.sin(yaw)
    pit = pitch * 10.0

    def P(lon, y, r=R):
        a = lon + yaw
        return (r * math.sin(a), y + pit * math.cos(a) * 0.9), math.cos(a)

    m = face.get("mouth", (0, 0, 0, 0))
    jaw = m[0]
    # ---------------- silhouette
    cran = ellipse(-sy * 3, -6, 42, 46)
    jawp = ellipse(sy * 13, 15 + jaw * 4 + pit * 0.3, 33 - 4 * abs(sy), 30 + jaw * 3)
    chin = ellipse(sy * 29, 30 + jaw * 6 + pit * 0.5, 12, 11)
    head = union(cran, jawp, chin)
    if abs(sy) > 0.25:
        sg = 1 if sy > 0 else -1
        k = min(1, (abs(sy) - 0.25) / 0.4)
        (nx, ny), _ = P(0, 4)
        nose = smooth_path([(nx - sg * 4, ny - 12), (nx + sg * 8 * k, ny + 7), (nx + sg * 3 * k, ny + 11), (nx - sg * 6, ny + 11)], tension=0.4)
        head = union(head, nose)
    # ear (near side)
    (ex, ey), ec = P(-1.62 if sy > 0 else 1.62, 2)
    ear = None
    if ec > 0.05:
        ear = ellipse(ex, ey, 4 + 5 * ec, 11)
    # ---------------- draw skin
    cel(cv, head, sk["base"], sk["shade"], light=(1, -0.4), depth=5, rim=sk["rim"], rim_dir=(-1, 0), rim_w=2.2,
        line=None)
    if st.get("stubble"):
        cv.save(); cv.clipPath(head, skia.ClipOp.kIntersect, True)
        cv.drawPath(union(ellipse(sy * 16, 26 + jaw * 5 + pit * 0.4, 30, 15), chin), paint("#3a2418", 0.13, blur=2.5))
        cv.restore()
    if ear is not None:
        cel(cv, ear, sk["base"], sk["shade"], depth=3)
        cv.drawPath(ear, paint(sk["line"], stroke=lw * 0.8))
        cv.drawPath(smooth_path([(ex - 1, ey - 5), (ex + 2.5 * ec, ey - 1), (ex, ey + 5)], close=False), paint(sk["shade"], stroke=lw * 0.9))
    # cheek blush
    (bx, by), bc = P(-0.55, 16)
    if bc > 0:
        cv.drawCircle(bx, by, 8 * bc, paint("#d9644a", 0.22 * bc, blur=4))
    (bx, by), bc = P(0.75, 16)
    if bc > 0:
        cv.drawCircle(bx, by, 7 * bc, paint("#d9644a", 0.18 * bc, blur=4))
    cv.drawPath(head, paint(sk["line"], stroke=lw))

    # ---------------- nose (frontal hint)
    (nx, ny), nc = P(0, 8)
    if abs(sy) <= 0.6:
        sg = 1 if sy >= 0 else -1
        cv.drawPath(smooth_path([(nx + sg * 1, ny - 8), (nx + sg * 5, ny + 4), (nx - sg * 1, ny + 7)], close=False),
                    paint(sk["shade"], stroke=lw * 1.1))
        cv.drawCircle(nx - sg * 3, ny + 5, 1.6, paint(sk["line"], 0.6))

    # ---------------- eyes
    eo = face.get("eye_open", 1.0) * (1 - face.get("blink", 0.0))
    sq = face.get("squint", 0.0)
    gx, gy = face.get("gaze", (0, 0))
    browr = face.get("brow", (0, 0))
    browa = face.get("brow_ang", (0, 0))
    for side, lon in ((0, -0.5), (1, 0.5)):
        (x, y), c = P(lon, -3)
        if c < 0.12:
            continue
        w = 10.5 * (c ** 0.8)
        h = 13.0
        op = max(0.0, eo * (1 - 0.45 * sq))
        top = y - h * min(op, 1.35)
        bot = y + h * (0.85 - 0.25 * sq) * (0.5 + 0.5 * min(1, op * 2))
        if op > 0.06:
            eyeshape = smooth_path([(x - w, y + 1), (x - w * 0.3, top), (x + w * 0.5, top + 1), (x + w, y), (x + w * 0.2, bot), (x - w * 0.6, bot - 1)], tension=0.7)
            cv.drawPath(eyeshape, paint("#fbf7ef"))
            cv.save(); cv.clipPath(eyeshape, skia.ClipOp.kIntersect, True)
            ix = x + gx * 5.0 * c + sy * 1.5
            iy = y + gy * 4.0 + 1
            cv.save(); cv.translate(ix, iy); cv.scale(max(0.55, c ** 0.6), 1)
            cv.drawCircle(0, 0, 7.4, paint("#4a2a17"))
            cv.drawCircle(0, 0, 7.4, paint("#2a160b", stroke=1.2))
            cv.drawCircle(0, 0, 3.8, paint("#0d0706"))
            cv.restore()
            cv.drawCircle(ix - 2.4, iy - 2.8, 2.1, paint("#ffffff", 0.95))
            cv.drawCircle(ix + 2.2, iy + 2.4, 0.9, paint("#ffffff", 0.7))
            # upper lid shadow
            cv.drawPath(shifted(eyeshape, 0, -h * 1.15), paint(sk["shade"], 0.18, blur=1.5))
            cv.restore()
            lash = smooth_path([(x - w - 1, y + 1), (x - w * 0.3, top), (x + w * 0.5, top + 1), (x + w + 2.5, y - 1)], close=False, tension=0.7)
            cv.drawPath(lash, paint("#1a0f0b", stroke=lw * 1.5))
            cv.drawPath(smooth_path([(x - w * 0.6, bot - 0.5), (x + w * 0.2, bot + 0.5), (x + w * 0.9, y + 1)], close=False),
                        paint(sk["shade"], stroke=lw * 0.6))
        else:
            cv.drawPath(smooth_path([(x - w - 1, y + 2), (x, y + 4), (x + w + 2, y + 1)], close=False), paint("#1a0f0b", stroke=lw * 1.4))
        # brow
        r = browr[side]
        a = browa[side]
        (bx0, by0), c0 = P(lon - 0.32 * (1 if side == 0 else -1) * -1, -21)
        (bx1, by1), c1 = P(lon + 0.38 * (1 if side == 0 else -1) * -1, -20)
        inner, outer = ((bx1, by1), (bx0, by0)) if side == 0 else ((bx0, by0), (bx1, by1))
        bi = (inner[0], inner[1] - r * 7 - a * 5 + sq * 2)
        bo = (outer[0], outer[1] - r * 6 + a * 3)
        mid = ((bi[0] + bo[0]) / 2, min(bi[1], bo[1]) - 3 - r * 1.5)
        cv.drawPath(smooth_path([bi, mid, bo], close=False), paint(st["hair"], stroke=lw * 2.4 * max(0.6, c)))

    # ---------------- mouth
    mo, mw, mr, msm = m
    half = 0.24 + 0.08 * mw - 0.09 * mr
    (lx, ly), lc = P(-half, 23)
    (rx, ry), rc = P(half, 23)
    (cxm, cym), cc = P(0.0, 23)
    lc, rc = max(lc, 0), max(rc, 0)
    lift = msm * 3.5
    ly -= lift; ry -= lift
    if sy > 0.55:
        rx = min(rx, cxm + 6)
    opn = mo * 13.0
    if opn < 1.2:
        mp = smooth_path([(lx, ly), (cxm, cym + 1 + 0.5 * mr - msm * 0.5), (rx, ry)], close=False)
        cv.drawPath(mp, paint("#4a1f17", stroke=lw * 1.2))
        if msm > 0.2:
            cv.drawPath(smooth_path([(lx - 1.5, ly - 1.5), (lx, ly), (lx + 0.5, ly + 2)], close=False), paint(sk["shade"], stroke=lw * 0.8))
    else:
        top = cym - opn * 0.22 - 1
        bot = cym + opn * 0.85
        rnd = mr * 0.5
        pts = [(lx + rnd * (cxm - lx) * 0.4, ly + rnd * 2), (cxm - (cxm - lx) * 0.45, top - 1),
               (cxm + (rx - cxm) * 0.45, top - 1), (rx - rnd * (rx - cxm) * 0.4, ry + rnd * 2),
               (cxm + (rx - cxm) * 0.4, bot), (cxm - (cxm - lx) * 0.4, bot)]
        mp = smooth_path(pts, tension=0.75)
        cv.drawPath(mp, paint("#4b1712"))
        cv.save(); cv.clipPath(mp, skia.ClipOp.kIntersect, True)
        cv.drawRect(skia.Rect(cxm - 30, top - 6, cxm + 30, top + min(4.2, opn * 0.32)), paint("#f5f1e8"))
        if mo > 0.3:
            cv.drawOval(skia.Rect(cxm - 9, bot - 6, cxm + 9, bot + 5), paint("#c4555a"))
        cv.restore()
        cv.drawPath(mp, paint("#3b1510", stroke=lw * 1.0))
        cv.drawPath(smooth_path([(cxm - 6, bot + 2.5), (cxm, bot + 3.5), (cxm + 6, bot + 2.5)], close=False), paint(sk["shade"], 0.7, stroke=lw * 0.8))

    # ---------------- facial hair
    if st.get("mustache"):
        (mx, my), _ = P(0, 17)
        must = smooth_path([(lx - 3, ly + 1), (mx - 4, my - 3), (mx, my - 1), (mx + 4, my - 3), (rx + 3, ry + 1), (mx, my + 2)], tension=0.6)
        cv.drawPath(must, paint("#2d2a28"))
    if st.get("beard"):
        cv.save(); cv.clipPath(head, skia.ClipOp.kIntersect, True)
        bp = union(ellipse(sy * 18, 38 + jaw * 6, 26, 12), ellipse(sy * 29, 34 + jaw * 6, 13, 12))
        cv.drawPath(bp, paint("#4a4644", 0.9))
        cv.restore()

    # ---------------- hair
    if st.get("cap"):
        capp = intersect(ellipse(-sy * 3, -8, 44, 47), poly([(-60, -60), (60, -60), (60, -24 + sy * 6), (-60, -22 - sy * 4)]))
        cel(cv, capp, "#f4f1ea", "#cfc8b8", depth=4, line="#6d675c", line_w=lw)
        for k in range(5):
            yy = -48 + k * 6
            cv.save(); cv.clipPath(capp, skia.ClipOp.kIntersect, True)
            cv.drawPath(smooth_path([(-50, yy + 12), (0, yy), (50, yy + 10)], close=False), paint("#d8d2c4", stroke=0.9))
            cv.restore()
    else:
        hl = []
        N = 40
        for i in range(N + 1):
            lon = -math.pi / 2 - yaw + math.pi * i / N
            a = lon + yaw
            rel = lon  # longitude relative to face
            ar = abs(math.atan2(math.sin(rel), math.cos(rel)))
            # hairline height as function of angle from face front
            if ar < 0.9:
                hy = -27 + 7 * (ar / 0.9) ** 2
            elif ar < 1.55:
                hy = -20 + 14 * ((ar - 0.9) / 0.65) ** 1.5
            else:
                hy = -6 + 22 * min(1, (ar - 1.55) / 0.9)
            hl.append((44 * math.sin(a), hy + pit * math.cos(a) * 0.6))
        above = poly(hl + [(70, -140), (-70, -140)])
        vol = union(ellipse(-sy * 5, -10, 45.5, 48), ellipse(-sy * 22, -4, 30, 40))
        tufts = []
        for k, (lon, ln, up) in enumerate(((-0.6, 18, 0.4), (-0.15, 22, 0.5), (0.35, 22, 0.35), (0.8, 16, 0.1))):
            a = lon + yaw
            if math.cos(a) < -0.2:
                continue
            bx = 42 * math.sin(a)
            by = -38 + 8 * abs(math.sin(lon)) + pit * 0.4
            tip = (bx + ln * (0.55 + 0.45 * sy), by - ln * up - 3)
            ctl = (bx + ln * 0.15, by - 10 - ln * up * 0.6)
            tufts.append(smooth_path([(bx - 15, by + 8), (bx - 6, by - 8), ctl, tip, (bx + ln * 0.35, by - 1), (bx + 6, by + 6)], tension=0.65))
        hair = intersect(union(vol, *tufts) if tufts else vol, above)
        cel(cv, hair, st["hair"], "#0b0807", light=(1, -0.5), depth=3, rim="#7a4b36", rim_dir=(-1, -0.3), rim_w=2.5,
            line="#0a0605", line_w=lw)
        # glossy strands
        cv.save(); cv.clipPath(hair, skia.ClipOp.kIntersect, True)
        for k in range(3):
            off = -14 + k * 11
            cv.drawPath(smooth_path([(-sy * 10 - 26 + off, -26), (-sy * 6 + off, -42 + k * 2), (sy * 10 + 26 + off, -36)], close=False),
                        paint(st["hair_hi"], 0.8, stroke=lw * 1.3))
        cv.restore()
    cv.restore()


# ----------------------------------------------------------------------------- body
def draw_hand(cv, wrist, ang, grip, st, lw, flip=False):
    sk = st["skin"]
    cv.save()
    cv.translate(*wrist)
    cv.rotate(math.degrees(ang))
    if flip:
        cv.scale(1, -1)
    if grip > 0.5:
        palm = union(ellipse(9, 0, 11, 9.5), capsule((4, -6), (13, -10), 4, 3.5))
    else:
        palm = union(ellipse(8, 0, 10, 8.5), capsule((10, 0), (24, 1), 7.5, 5.5), capsule((4, -6), (14, -12), 4, 3.2))
    cel(cv, palm, sk["base"], sk["shade"], depth=3, line=sk["line"], line_w=lw)
    if grip <= 0.5:
        cv.drawPath(smooth_path([(14, 2.5), (22, 3)], close=False), paint(sk["shade"], stroke=lw * 0.7))
    else:
        cv.drawPath(smooth_path([(13, -3), (17, 1), (13, 6)], close=False), paint(sk["shade"], stroke=lw * 0.7))
    cv.restore()


def draw_foot(cv, ankle, ang, st, lw, dim=0.0):
    cv.save()
    cv.translate(*ankle)
    cv.rotate(math.degrees(ang))
    sk = st["skin"]
    base = mix(sk["base"], "#000000", dim)
    shade = mix(sk["shade"], "#000000", dim)
    foot = smooth_path([(-10, -6), (2, -9), (22, -2), (36, 4), (38, 9), (-12, 9), (-13, 2)], tension=0.4)
    cel(cv, foot, base, shade, depth=3, line=sk["line"], line_w=lw)
    sole = poly([(-14, 8), (40, 8), (41, 12.5), (-14, 12.5)])
    cv.drawPath(sole, paint(mix(st["sandal"], "#000000", dim)))
    cv.drawPath(sole, paint(st["sandal_line"], stroke=lw * 0.8))
    strap = capsule((8, -4), (24, 1), 4.2, 4.2)
    cv.drawPath(strap, paint(mix(st["sandal"], "#000000", dim)))
    cv.drawPath(strap, paint(st["sandal_line"], stroke=lw * 0.7))
    cv.restore()


def draw_leg(cv, hip, knee, ankle, foot_ang, st, lw, dim=0.0):
    pc = mix(st["pants"], "#000000", dim)
    ps = mix(st["pants_shade"], "#000000", dim)
    th = capsule(hip, knee, 18, 13.5)
    sh = capsule(knee, (ankle[0], ankle[1] - 6), 13.5, 10.5)
    leg = union(th, sh)
    draw_foot(cv, ankle, foot_ang, st, lw, dim)
    cel(cv, leg, pc, ps, depth=6, rim="#7a6a9a", rim_w=2.2, line=st["pants_line"], line_w=lw)
    # crease at knee
    kx, ky = knee
    cv.drawPath(smooth_path([(kx - 6, ky - 3), (kx + 2, ky + 2), (kx + 7, ky - 1)], close=False), paint(st["pants_line"], 0.6, stroke=lw * 0.7))
    # hem
    a = math.atan2(ankle[1] - knee[1], ankle[0] - knee[0])
    hx, hy = ankle[0] - 8 * math.cos(a), ankle[1] - 8 * math.sin(a)
    cuff = capsule((hx - 3 * math.cos(a), hy - 3 * math.sin(a)), (hx + 1 * math.cos(a), hy + 1 * math.sin(a)), 10.8, 10.8)
    cv.drawPath(cuff, paint(ps))
    cv.drawPath(cuff, paint(st["pants_line"], stroke=lw * 0.8))


def draw_arm(cv, sh, el, wr, hand_ang, grip, st, lw, dim=0.0, far=False):
    sk = st["skin"]
    fore = capsule(el, wr, 9.5, 7.2)
    cel(cv, fore, mix(sk["base"], "#000000", dim), mix(sk["shade"], "#000000", dim), depth=3.5, rim=sk["rim"], rim_w=1.6,
        line=sk["line"], line_w=lw)
    if not far and st.get("watch"):
        a = math.atan2(wr[1] - el[1], wr[0] - el[0])
        wx, wy = wr[0] - 9 * math.cos(a), wr[1] - 9 * math.sin(a)
        band = capsule((wx - 3 * math.cos(a), wy - 3 * math.sin(a)), (wx + 3 * math.cos(a), wy + 3 * math.sin(a)), 8.3, 8.0)
        cv.drawPath(band, paint(st["watch"]))
        cv.drawCircle(wx, wy, 2.0, paint("#c9d2dc", 0.9))
    fa = math.atan2(wr[1] - el[1], wr[0] - el[0])
    draw_hand(cv, wr, fa + hand_ang, grip, {"skin": {k: mix(v, "#000000", dim) for k, v in sk.items()}}, lw)
    upper = capsule(sh, el, 15.5, 12.5)
    a = math.atan2(el[1] - sh[1], el[0] - sh[0])
    cuff = capsule((el[0] - 9 * math.cos(a), el[1] - 9 * math.sin(a)), (el[0] + 1 * math.cos(a), el[1] + 1 * math.sin(a)), 13.5, 13.0)
    sl = union(upper, cuff)
    cel(cv, sl, mix(st["shirt"], "#000000", dim), mix(st["shirt_shade"], "#000000", dim), depth=6, rim="#ffc58c", rim_w=2.2,
        line=st["shirt_line"], line_w=lw)
    cv.drawPath(cuff, paint(st["shirt_line"], 0.8, stroke=lw * 0.8))
    if st.get("shirt_check"):
        cv.save(); cv.clipPath(upper, skia.ClipOp.kIntersect, True)
        for k in range(-3, 4):
            o = k * 11
            n = (-math.sin(a), math.cos(a))
            p0 = (sh[0] + n[0] * o - 40 * math.cos(a), sh[1] + n[1] * o - 40 * math.sin(a))
            p1 = (sh[0] + n[0] * o + 120 * math.cos(a), sh[1] + n[1] * o + 120 * math.sin(a))
            cv.drawLine(*p0, *p1, paint(st["shirt_check"], 0.28, stroke=2.2))
        cv.restore()


def draw_torso(cv, hip, spine, bend, st, lw, breathe=0.0):
    """Torso drawn in a local frame anchored at the pelvis."""
    def T(p):
        x, y = p
        if y < -60:
            x, y = rot((x, y), bend * min(1.0, (-y - 60) / 90.0), (0, -60))
        y *= 1 + breathe * 0.012 * (1 if y < -80 else 0)
        return rot((x, y), spine, (0, 0))[0] + hip[0], rot((x, y), spine, (0, 0))[1] + hip[1]
    pts = [(-35, 18), (-33, -30), (-37, -95), (-35, -134), (-16, -152), (14, -154), (36, -140), (45, -100), (40, -45), (42, 18), (4, 22)]
    body = smooth_path([T(p) for p in pts], tension=0.55)
    cel(cv, body, st["shirt"], st["shirt_shade"], light=(1, -0.5), depth=10, rim="#ffc58c", rim_w=3.0, line=None)
    if st.get("shirt_check"):
        cv.save(); cv.clipPath(body, skia.ClipOp.kIntersect, True)
        for k in range(-4, 5):
            cv.drawLine(*T((k * 12, 30)), *T((k * 12 + 4, -170)), paint(st["shirt_check"], 0.25, stroke=2.4))
        for k in range(0, 17):
            cv.drawLine(*T((-40, 20 - k * 12)), *T((50, 20 - k * 12)), paint(st["shirt_check"], 0.18, stroke=2.0))
        cv.restore()
    # placket & buttons
    cv.drawPath(smooth_path([T((18, -140)), T((24, -80)), T((25, 16))], close=False), paint(st["shirt_line"], 0.7, stroke=lw * 0.8))
    for k in range(4):
        cv.drawCircle(*T((22 + k * 0.6, -118 + k * 34)), 2.2, paint("#f0eee6", 0.9))
    # pocket
    pk = poly([T((-6, -118)), T((12, -118)), T((12, -96)), T((3, -92)), T((-6, -96))])
    cv.drawPath(pk, paint(st["shirt_line"], 0.6, stroke=lw * 0.7))
    # collar
    c1 = smooth_path([T((-12, -151)), T((-3, -134)), T((10, -146)), T((14, -156))], tension=0.4)
    c2 = smooth_path([T((14, -156)), T((22, -133)), T((27, -142))], tension=0.4)
    for c in (c1, c2):
        cel(cv, c, mix(st["shirt"], "#ffffff", 0.12), st["shirt_shade"], depth=2, line=st["shirt_line"], line_w=lw * 0.8)
    cv.drawPath(body, paint(st["shirt_line"], stroke=lw))
    # hem crease
    cv.drawPath(smooth_path([T((-24, 4)), T((0, 8)), T((28, 6))], close=False), paint(st["shirt_line"], 0.4, stroke=lw * 0.7))
    return T


class Hero:
    """Full-body character. pose is a dict produced by the scene timeline."""
    def __init__(self, style=HERO):
        self.st = style

    def draw(self, cv, pose, lw=2.2):
        st = self.st
        hip = pose["hip"]
        spine = pose["spine"]
        bend = pose.get("bend", 0.0)
        # joints in world space (local frame rotated by spine)
        def TR(p):
            x, y = p
            if y < -60:
                x, y = rot((x, y), bend * min(1.0, (-y - 60) / 90.0), (0, -60))
            r = rot((x, y), spine)
            return (r[0] + hip[0], r[1] + hip[1])
        sh_near = TR((-19, -132))
        sh_far = TR((26, -136))
        neck = TR((3, -150))
        hip_near = (hip[0] - 10, hip[1] - 2)
        hip_far = (hip[0] + 12, hip[1] - 4)

        # legs
        fn, ff = pose["foot_near"], pose["foot_far"]
        kn, an = ik2(hip_near, fn[:2], L["thigh"], L["shin"], -1)
        kf, af = ik2(hip_far, ff[:2], L["thigh"], L["shin"], -1)
        # arms
        def arm(shp, target, bend_sign=1):
            return ik2(shp, target, L["upper"], L["fore"], bend_sign)
        hn, hf = pose["hand_near"], pose["hand_far"]
        en, wn = arm(sh_near, hn[:2])
        ef, wf = arm(sh_far, hf[:2])

        # far arm, far leg
        draw_arm(cv, sh_far, ef, wf, hf[2], hf[3], st, lw, dim=0.22, far=True)
        draw_leg(cv, hip_far, kf, af, ff[2], st, lw, dim=0.25)
        draw_leg(cv, hip_near, kn, an, fn[2], st, lw)
        # neck
        hp = pose["head"]
        hx, hy = pose.get("head_pos") or TR((8, -196))
        hx += hp.get("dx", 0); hy += hp.get("dy", 0)
        nk = capsule(neck, (hx - 4, hy + 26), 12, 11)
        cel(cv, nk, st["skin"]["base"], st["skin"]["shade"], depth=7, line=st["skin"]["line"], line_w=lw)
        draw_torso(cv, hip, spine, bend, st, lw, pose.get("breathe", 0.0))
        # back-of-collar shadow on neck
        draw_head(cv, hx, hy, 0.94, hp["yaw"], hp["pitch"], hp["roll"], pose["face"], st, lw)
        if pose.get("wallet_in_hand") and pose.get("wallet_behind"):
            pose["wallet_in_hand"](cv, wn, hn[2])
        draw_arm(cv, sh_near, en, wn, hn[2], hn[3], st, lw)
        if pose.get("wallet_in_hand") and not pose.get("wallet_behind"):
            pose["wallet_in_hand"](cv, wn, hn[2])
        return dict(wrist_near=wn, head=(hx, hy))
