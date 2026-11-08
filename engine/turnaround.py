"""Turnaround-ready character: a pseudo-3D rig drawn flat in 2D.

Every body point is defined in character space (lateral, forward, down) and
projected for a view angle `a` (0 = front, pi/2 = right-facing side, pi = back),
so all views share identical proportions. Limbs use 3D direction FK, so the
same rig produces poses in any view.
"""
import math
import skia
from .draw import paint, poly, smooth_path, ellipse, capsule, union, cel, mix

PAL = dict(
    skin="#f2c39b", skin_sh="#e3a47e", skin_line="#b9785a", blush="#f09a8e",
    hair="#221a2c", hair_sh="#140f1b", hair_hi="#4a3a5e",
    shirt="#f1ecf7", shirt_sh="#d8cdea", collar="#c3b1df",
    pants="#30375a", pants_sh="#232945",
    shoe="#3d2b2b", shoe_sh="#2a1d1d",
    eye="#2a2033", frame="#9d8bb0", lens="#ffffff",
)

# proportions (px at scale 1); ground = 0, y measured downward from crown
H = dict(head_c=102, chin=170, neck=200, shoulder=228, hem=470, hip=455, knee=640, ankle=820, sole=850)
SH_W, HIP_W = 70, 30
UPPER, FORE, THIGH, SHIN = 118, 108, 185, 180


def vec(ab, fw, side):
    x = side * math.sin(ab) * math.cos(fw)
    d = math.sin(fw)
    y = math.cos(ab) * math.cos(fw)
    n = math.sqrt(x * x + d * d + y * y)
    return (x / n, d / n, y / n)


class Proj:
    def __init__(self, cx, top, a, s):
        self.cx, self.top, self.a, self.s = cx, top, a, s
        self.c, self.sn = math.cos(a), math.sin(a)

    def __call__(self, o, d, y):
        return (self.cx + (o * self.c + d * self.sn) * self.s, self.top + y * self.s)

    def depth(self, o, d):
        return d * self.c - o * self.sn


def add(p, v, L):
    return (p[0] + v[0] * L, p[1] + v[1] * L, p[2] + v[2] * L)


# ------------------------------------------------------------------ head
FACES = {
    "neutral": dict(),
    "happy": dict(mouth="big", brow=(0.3, 0.3), eye_open=0.85, cheek=1.3),
    "talking": dict(mouth="talk", brow=(0.15, 0.15)),
    "surprised": dict(mouth="o", brow=(1.0, 1.0), eye_open=1.25, pupil=0.75),
    "sad": dict(mouth="frown", brow=(0.2, 0.2), brow_ang=0.8, lid=0.45, gaze=(0, 0.4)),
    "worried": dict(mouth="wavy", brow=(0.5, 0.5), brow_ang=0.9, sweat=True, gaze=(0.3, 0)),
    "angry": dict(mouth="grit", brow=(-0.3, -0.3), brow_ang=-1.0, lid=0.3),
    "thinking": dict(mouth="side", brow=(0.6, -0.2), gaze=(0.6, -0.6), eye_open=0.9),
}


def draw_head(cv, P, a, face=None, roll=0.0, scale=1.0):
    f = dict(FACES["neutral"]); f.update(face or {})
    hc = P(0, 4, H["head_c"])
    s = P.s * scale * 1.17
    cv.save()
    cv.translate(*hc)
    cv.rotate(math.degrees(roll))
    cv.scale(s, s)
    R = 66.0
    sa = math.sin(a)

    def S(lon, lat, r=R):
        aa = lon + a
        return (r * math.sin(aa) * math.cos(lat), -r * math.sin(lat) * 1.05), math.cos(aa) * math.cos(lat)

    # curls on a sphere (skip face region)
    curls = []
    for i in range(14):
        lat = -0.55 + i * 0.15
        n = max(6, int(26 * math.cos(lat)))
        for k in range(n):
            lon = -math.pi + (k + 0.5 * (i % 2)) * 2 * math.pi / n
            al = abs(math.atan2(math.sin(lon), math.cos(lon)))
            if al < 1.25 and lat < 0.68:
                continue
            if al < 1.95 and lat < 0.32:
                continue
            if lat < -0.1 and al < 2.4:
                continue
            (x, y), dp = S(lon, lat, 80)
            curls.append((dp, x, y - 8, 19 + 3 * math.sin(i * 7.1 + k * 3.3)))
    curls.sort()
    head = union(ellipse(0, 0, 63, 70), ellipse(sa * 12, 26, 50, 50))
    if abs(sa) > 0.3:
        sg = 1 if sa > 0 else -1
        k = min(1, (abs(sa) - 0.3) / 0.5)
        (nx, ny), _ = S(0, 0.02, 66)
        head = union(head, smooth_path([(nx - sg * 6, ny - 12), (nx + sg * 9 * k, ny + 12), (nx - sg * 4, ny + 18)], tension=0.4))

    def curl(x, y, r, front):
        cv.drawCircle(x, y, r, paint(PAL["hair"] if front else PAL["hair_sh"]))
        if front:
            cv.drawPath(smooth_path([(x - r * 0.6, y - r * 0.15), (x - r * 0.2, y - r * 0.6), (x + r * 0.35, y - r * 0.55)], close=False),
                        paint(PAL["hair_hi"], 0.9, stroke=3.2))

    # back hair mass + back curls
    cv.drawPath(ellipse(-sa * 6, -18, 76, 70), paint(PAL["hair_sh"]))
    for dp, x, y, r in curls:
        if dp <= 0:
            curl(x, y, r, False)
    # ears
    ears = []
    for side in (-1, 1):
        (ex, ey), dp = S(side * math.pi / 2, -0.05, 64)
        ears.append((dp, ex, ey))
    for dp, ex, ey in ears:
        if dp < 0.05:
            cv.drawPath(ellipse(ex, ey + 6, 9 + 6 * abs(math.sin(a)), 16), paint(PAL["skin_sh"]))
    # skin
    cel(cv, head, PAL["skin"], PAL["skin_sh"], light=(0.8, -0.6), depth=7)
    for dp, ex, ey in ears:
        if dp >= 0.05 or abs(abs(a) - math.pi) < 0.3:
            ew = 7 + 9 * abs(math.sin(a)) * (1 if dp >= 0.05 else 0.6)
            e = ellipse(ex, ey + 6, ew, 16)
            cel(cv, e, PAL["skin"], PAL["skin_sh"], depth=3)
            cv.drawPath(smooth_path([(ex - 2, ey), (ex + 3, ey + 6), (ex - 1, ey + 13)], close=False), paint(PAL["skin_sh"], stroke=2.5))
    front_face = math.cos(a) > -0.25
    if front_face:
        ex_ = f.get("eye_open", 1.0)
        gx, gy = f.get("gaze", (0, 0))
        bl, br = f.get("brow", (0, 0))
        bang = f.get("brow_ang", 0.0)
        # blush
        for side in (-1, 1):
            (bx, by), dp = S(side * 0.62, -0.32)
            if dp > 0.1:
                cv.drawCircle(bx, by, 13 * dp, paint(PAL["blush"], 0.45 * f.get("cheek", 1.0), blur=6))
        # eyes + glasses
        rings = []
        for side, br_ in ((-1, bl), (1, br)):
            (x, y), dp = S(side * 0.42, 0.0)
            if dp < 0.15:
                continue
            w = 10 * dp ** 0.7
            h = 12 * ex_
            lid = f.get("lid", 0.0)
            cv.drawOval(skia.Rect(x - w, y - h, x + w, y + h), paint("#ffffff"))
            cv.save(); cv.clipRect(skia.Rect(x - w, y - h, x + w, y + h))
            ix, iy = x + gx * 4 * dp, y + gy * 4 + 1
            pr = 8.5 * f.get("pupil", 1.0)
            cv.drawOval(skia.Rect(ix - pr * dp ** 0.6, iy - pr, ix + pr * dp ** 0.6, iy + pr), paint(PAL["eye"]))
            cv.drawCircle(ix - 2.5, iy - 3.5, 2.6, paint("#ffffff"))
            if lid > 0:
                cv.drawRect(skia.Rect(x - w - 2, y - h - 2, x + w + 2, y - h + 2 * h * lid), paint(PAL["skin"]))
            cv.restore()
            cv.drawLine(x - w - 1, y - h + 2 * h * lid, x + w + 1, y - h + 2 * h * lid - side * 0, paint(PAL["eye"], stroke=3))
            # brow
            inner = x - side * w * 0.9
            outer = x + side * w * 1.4
            yb = y - 27 - br_ * 8
            cv.drawPath(smooth_path([(inner, yb + bang * 6), ((inner + outer) / 2, yb - 3), (outer, yb + 2 - bang * 2)], close=False),
                        paint(PAL["hair"], stroke=5.5))
            rings.append((x, y, dp, side))
        # nose
        (nx, ny), _ = S(0.0, -0.18)
        if abs(sa) < 0.45:
            cv.drawPath(smooth_path([(nx + 2, ny - 10), (nx + 4 + sa * 4, ny + 4), (nx - 2, ny + 6)], close=False), paint(PAL["skin_sh"], stroke=3))
        # mouth
        mt = f.get("mouth", "smile")
        (mx, my), _ = S(0.05, -0.45)
        hw = 16 * max(0.45, math.cos(a))
        if mt == "smile":
            cv.drawPath(smooth_path([(mx - hw, my - 2), (mx, my + 6), (mx + hw, my - 2)], close=False), paint("#a2484a", stroke=3.5))
        elif mt == "big":
            m = smooth_path([(mx - hw * 1.2, my - 6), (mx + hw * 1.2, my - 6), (mx, my + 16)], tension=0.6)
            cv.drawPath(m, paint("#7a2630"))
            cv.save(); cv.clipPath(m, skia.ClipOp.kIntersect, True)
            cv.drawRect(skia.Rect(mx - 30, my - 8, mx + 30, my - 1), paint("#ffffff"))
            cv.drawCircle(mx, my + 14, 9, paint("#e0707a")); cv.restore()
        elif mt == "talk":
            m = ellipse(mx, my + 3, hw * 0.8, 10)
            cv.drawPath(m, paint("#7a2630"))
            cv.save(); cv.clipPath(m, skia.ClipOp.kIntersect, True)
            cv.drawRect(skia.Rect(mx - 20, my - 9, mx + 20, my - 3), paint("#ffffff"))
            cv.drawCircle(mx, my + 13, 8, paint("#e0707a")); cv.restore()
        elif mt == "o":
            cv.drawPath(ellipse(mx, my + 4, 7, 10), paint("#7a2630"))
        elif mt == "frown":
            cv.drawPath(smooth_path([(mx - hw * 0.8, my + 6), (mx, my), (mx + hw * 0.8, my + 6)], close=False), paint("#a2484a", stroke=3.5))
        elif mt == "wavy":
            cv.drawPath(smooth_path([(mx - hw * 0.8, my + 4), (mx - hw * 0.3, my), (mx + hw * 0.2, my + 4), (mx + hw * 0.8, my)], close=False), paint("#a2484a", stroke=3.2))
        elif mt == "grit":
            m = poly([(mx - hw, my - 2), (mx + hw, my - 2), (mx + hw * 0.8, my + 9), (mx - hw * 0.8, my + 9)])
            cv.drawPath(m, paint("#ffffff")); cv.drawPath(m, paint("#7a2630", stroke=3))
            cv.drawLine(mx - hw, my + 3.5, mx + hw, my + 3.5, paint("#7a2630", stroke=1.5))
        elif mt == "side":
            cv.drawPath(smooth_path([(mx - hw * 0.5, my + 3), (mx + hw * 0.6, my - 1)], close=False), paint("#a2484a", stroke=3.5))
        # glasses
        for x, y, dp, side in rings:
            r = ellipse(x, y + 1, 21 * dp ** 0.8, 20)
            cv.drawPath(r, paint(PAL["lens"], 0.18))
            cv.drawPath(r, paint(PAL["frame"], stroke=3))
            cv.drawLine(x + 18 * side * dp, y - 3, x + 20 * side * dp + side * 6, y - 4, paint(PAL["frame"], stroke=3)) if len(rings) == 2 else None
        if len(rings) == 2:
            l, r_ = sorted(rings)[0], sorted(rings)[1]
            cv.drawPath(smooth_path([(l[0] + 20 * l[2] ** 0.8, l[1] - 2), ((l[0] + r_[0]) / 2, l[1] - 6), (r_[0] - 20 * r_[2] ** 0.8, r_[1] - 2)], close=False), paint(PAL["frame"], stroke=3))
        for x, y, dp, side in rings:  # temple arm to ear
            (ex, ey), edp = S(side * math.pi / 2 * 0.95, 0.0, 64)
            if edp > -0.05:
                cv.drawLine(x + side * 20 * dp ** 0.8, y - 2, ex, ey, paint(PAL["frame"], stroke=3))
        if f.get("sweat"):
            (sx, sy), _ = S(-0.95, 0.5)
            cv.drawPath(smooth_path([(sx, sy - 12), (sx + 7, sy + 4), (sx, sy + 9), (sx - 7, sy + 4)], tension=0.5), paint("#9fd3f2"))
    # front curls (on top of skin)
    for dp, x, y, r in curls:
        if dp > 0:
            curl(x, y, r, True)
    cv.restore()


# ------------------------------------------------------------------ body
DEFAULT_POSE = dict(
    arm_l=((0.07, 0.0), (0.03, 0.10)), arm_r=((0.07, 0.0), (0.03, 0.10)),   # (upper ab,fw), (fore ab,fw)
    leg_l=(0.03, 0.0, 0.0), leg_r=(0.03, 0.0, 0.0),                          # (ab, thigh fw, shin fw)
    face="neutral", roll=0.0, hand_l="relaxed", hand_r="relaxed",
)


def draw_character(cv, cx, ground, a, s=1.0, pose=None):
    p = dict(DEFAULT_POSE); p.update(pose or {})
    P = Proj(cx, ground - H["sole"] * s, a, s)
    items = []
    lw = 0

    # legs
    def leg(side, spec):
        ab, fw1, fw2 = spec
        hip = (side * HIP_W, 0, H["hip"])
        knee = add(hip, vec(ab, fw1, side), THIGH)
        ank = add(knee, vec(ab * 0.5, fw2, side), SHIN)
        toe_dir = (0, 1, 0)
        def fn():
            th = capsule(P(*hip), P(*knee), 29 * s, 23 * s)
            sh = capsule(P(*knee), P(*ank), 23 * s, 19 * s)
            lg = union(th, sh)
            heel = P(ank[0], ank[1] - 10, ank[2] + 18)
            toe = P(ank[0], ank[1] + 34, ank[2] + 22)
            mid = P(ank[0], ank[1] + 12, ank[2] + 22)
            shoe = union(capsule(heel, toe, 17 * s, 15 * s), ellipse(mid[0], mid[1] + 2 * s, (16 + 8 * abs(math.cos(a))) * s, 14 * s))
            cel(cv, lg, PAL["pants"], PAL["pants_sh"], light=(0.9 * -side if abs(math.sin(a)) < 0.5 else 1, -0.3), depth=9 * s)
            cv.drawPath(shoe, paint(PAL["shoe"]))
            cv.drawPath(shifted_rect(heel, toe, s), paint(PAL["shoe_sh"]))
        items.append((P.depth(side * HIP_W, 0) * 0.3 - 40, fn))

    def arm(side, spec, hand):
        (ab1, fw1), (ab2, fw2) = spec
        sh = (side * SH_W, 0, H["shoulder"] + 12)
        el = add(sh, vec(ab1, fw1, side), UPPER)
        wr = add(el, vec(ab2, fw2, side), FORE)
        def fn():
            fore = union(capsule(P(*sh), P(*el), 18 * s, 15 * s), capsule(P(*el), P(*wr), 15 * s, 13 * s))
            cel(cv, fore, PAL["skin"], PAL["skin_sh"], light=(-side * 0.8, -0.3), depth=6 * s)
            hv = vec(ab2, fw2, side)
            hp = P(*add(wr, hv, 14))
            hd = ellipse(hp[0], hp[1], 17 * s, 19 * s)
            if hand == "open":
                hd = union(hd, capsule(hp, P(*add(wr, hv, 34)), 15 * s, 13 * s))
            cel(cv, hd, PAL["skin"], PAL["skin_sh"], depth=4 * s)
            thumb_side = P(*add(add(wr, hv, 10), (0, 1, 0), 12))
            cv.drawCircle(thumb_side[0], thumb_side[1], 7 * s, paint(PAL["skin_sh"], 0.8))
            sl_end = add(sh, vec(ab1, fw1, side), UPPER * 0.55)
            sleeve = capsule(P(*sh), P(*sl_end), 25 * s, 22 * s)
            cel(cv, sleeve, PAL["shirt"], PAL["shirt_sh"], light=(-side * 0.8, -0.3), depth=7 * s)
        items.append((P.depth(side * SH_W, 0) + 1, fn))

    def torso():
        hw_sh = math.hypot(SH_W * math.cos(a), 40 * math.sin(a))
        hw_w = math.hypot(60 * math.cos(a), 38 * math.sin(a))
        hw_h = math.hypot(64 * math.cos(a), 40 * math.sin(a))
        fx = 5 * math.sin(a) * s
        x0 = P(0, 0, 0)[0] + fx
        top = P.top
        y = lambda v: top + v * s
        pts = [(x0 - hw_h * s, y(H["hem"])), (x0 - hw_w * s, y(360)), (x0 - hw_sh * s, y(H["shoulder"] + 16)),
               (x0 - hw_sh * 0.55 * s, y(H["shoulder"])), (x0 + hw_sh * 0.55 * s, y(H["shoulder"])),
               (x0 + hw_sh * s, y(H["shoulder"] + 16)), (x0 + hw_w * s, y(360)), (x0 + hw_h * s, y(H["hem"]))]
        body = smooth_path(pts, tension=0.35)
        cel(cv, body, PAL["shirt"], PAL["shirt_sh"], light=(-0.9 if math.cos(a) > 0 else 0.9, -0.2), depth=26 * s)
        cv.drawPath(smooth_path([(x0 - hw_h * s * 0.9, y(H["hem"] - 6)), (x0, y(H["hem"] - 3)), (x0 + hw_h * s * 0.9, y(H["hem"] - 6))], close=False),
                    paint(PAL["shirt_sh"], stroke=3 * s))
        # neck + collar ring
        nk = capsule(P(0, 2, H["chin"] - 10), P(0, 2, H["shoulder"] + 4), 22 * s, 24 * s)
        cel(cv, nk, PAL["skin"], PAL["skin_sh"], depth=8 * s)
        ring = []
        for k in range(41):
            ph = 2 * math.pi * k / 40
            o, d = 28 * math.cos(ph), 22 * math.sin(ph)
            if P.depth(o, d) > -2:
                ring.append(P(o, d, H["shoulder"] + 6 + 6 * max(0, math.sin(ph))))
            elif len(ring) > 1:
                cv.drawPath(poly(ring, close=False), paint(PAL["collar"], stroke=9 * s)); ring = []
        if len(ring) > 1:
            cv.drawPath(poly(ring, close=False), paint(PAL["collar"], stroke=9 * s))
    items.append((0, torso))
    leg(-1, p["leg_r"]); leg(1, p["leg_l"])
    arm(-1, p["arm_r"], p["hand_r"]); arm(1, p["arm_l"], p["hand_l"])
    items.sort(key=lambda it: it[0])
    for _, fn in items:
        fn()
    draw_head(cv, P, a, FACES[p["face"]] if isinstance(p["face"], str) else p["face"], roll=p["roll"])
    return P


def shifted_rect(heel, toe, s):
    return capsule((heel[0], heel[1] + 9 * s), (toe[0], toe[1] + 9 * s), 8 * s, 7 * s)
