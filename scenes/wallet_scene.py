"""12-second test scene: evening tea stall, a young man finds a wallet.

All motion is procedural/keyframed and deterministic in t, so frames can be
rendered in parallel.
"""
import math
import random
import numpy as np
import skia

from engine.core import Track, clamp, lerp, smoothstep, ease_in_out, ease_out, noise, fbm, ease_quint
from engine.draw import (paint, poly, smooth_path, ellipse, capsule, union, intersect, cel, glow,
                         hexc, mix, lin_grad, shifted)
from engine.character import Hero, HERO, KEEPER, draw_head, draw_arm, draw_torso, ik2

W, H = 1920, 1080
FPS = 24
DURATION = 12.0
GROUND = 905.0          # walking line (world, parallax 1.0)
SPEECH_START = 8.30
ANCHOR = (700.0, 560.0)

# ============================================================================ timeline
WALK_V = 232.0
X0 = 120.0
T_DECEL0, T_STOP = 3.50, 4.02

def hip_x(t):
    if t <= T_DECEL0:
        return X0 + WALK_V * t
    d = T_STOP - T_DECEL0
    u = clamp((t - T_DECEL0) / d)
    # velocity falls linearly-eased -> integrate
    dist = WALK_V * d * (u - u * u * u / 3.0 * 1.0 + 0.0) if False else WALK_V * d * (u - 0.5 * u * u * (2 - u) * 0.0)
    # analytic integral of v(u)=V*(1-u)^2  -> V*d*(1-(1-u)^3)/3
    dist = WALK_V * d * (1 - (1 - u) ** 3) / 3.0
    return X0 + WALK_V * T_DECEL0 + dist

X_STOP = hip_x(T_STOP)
WALLET = (X_STOP + 78.0, GROUND + 6.0)

# footstep plan: (land_time, x)
def _plan():
    near, far = [], []
    for k in range(-1, 4):
        tn = -0.25 + k * 1.0 + 1.0
        if tn < 3.5:
            near.append((tn, hip_x(tn + 0.27) - 4))
        tf = 0.25 + k * 1.0
        if tf < 3.5:
            far.append((tf, hip_x(tf + 0.27) + 10))
    near = sorted(set(near))
    near.append((3.70, X_STOP + 24))
    far.append((4.10, X_STOP - 2))
    near.insert(0, (-0.25, hip_x(0.02) - 4))
    return sorted(near), sorted(far)

PLAN_NEAR, PLAN_FAR = _plan()
SWING = 0.38

def foot_state(t, plan, depth):
    gy = GROUND - 12 - depth
    prev = plan[0]
    for i, (tl, x) in enumerate(plan):
        if t < tl:
            nxt = (tl, x)
            lift = max(tl - SWING, prev[0] + 0.3)
            if t >= lift and i > 0:
                s = (t - lift) / (tl - lift)
                e = ease_in_out(s)
                fx = lerp(prev[1], x, e)
                h = 24 * math.sin(math.pi * min(1, s * 1.1)) * (1 if (x - prev[1]) > 30 else 0.5)
                ang = lerp(0.5, -0.28, ease_out(s))
                return (fx, gy - h - 4 * math.sin(math.pi * s), ang)
            # stance on prev
            ang = 0.0
            heel = clamp((t - (lift - 0.16)) / 0.16) if i > 0 else 0
            land = clamp((t - prev[0]) / 0.12)
            ang = -0.28 * (1 - ease_out(land)) + 0.5 * heel * heel
            return (prev[1] + 6 * heel, gy - 9 * heel * heel, ang)
        prev = (tl, x)
    land = clamp((t - prev[0]) / 0.12)
    return (prev[1], gy, -0.28 * (1 - ease_out(land)))

# expression / acting tracks --------------------------------------------------
# head yaw (0.55 = default three-quarter facing right)
YAW = Track([(0, 0.55), (3.42, 0.55), (3.62, 0.70, "out"), (4.55, 0.66), (4.72, -0.05, "io"), (4.95, -0.38, "out"),
             (5.42, -0.36), (5.62, 0.75, "io"), (5.80, 1.02, "out"), (6.10, 1.0), (6.32, 0.62, "io"),
             (8.30, 0.62), (8.85, 0.60), (9.20, 0.22, "io"), (10.4, 0.18), (10.75, 0.30, "io"), (12, 0.30)])
PITCH = Track([(0, 0.0), (3.42, 0.0), (3.62, 0.85, "out"), (4.55, 0.8), (4.75, 0.0), (6.10, 0.0), (6.35, 0.9),
               (7.2, 1.0), (7.75, 0.6), (8.3, 0.45), (8.9, 0.40), (9.2, 0.0, "io"), (10.4, -0.1), (10.9, 0.05), (12, 0.0)])
ROLL = Track([(0, 0.0), (3.6, 0.0), (3.8, 0.10, "out"), (4.4, 0.06), (4.8, -0.08), (5.5, -0.06), (5.85, 0.10), (6.2, 0.05),
              (8.3, 0.04), (8.6, -0.05), (9.3, 0.02), (10.6, 0.02), (11.05, 0.13, "io"), (12, 0.11)])
EYE_OPEN = Track([(0, 1.0), (3.45, 1.0), (3.6, 1.28, "out"), (4.4, 1.2), (4.6, 0.72), (6.1, 0.72), (6.35, 1.05),
                  (7.9, 1.0), (8.3, 1.3, "out"), (8.75, 1.2), (9.4, 1.08), (10.6, 1.15), (12, 1.1)])
SQUINT = Track([(0, 0.0), (4.5, 0.0), (4.7, 0.55), (6.05, 0.55), (6.3, 0.0), (12, 0.0)])
GAZE = Track([(0, (0.25, 0.1)), (3.40, (0.25, 0.1)), (3.48, (0.6, 0.8), "out"), (4.5, (0.5, 0.7)),
              (4.58, (-1.0, 0.0), "out"), (5.35, (-0.95, 0.1)), (5.43, (1.0, 0.0), "out"), (6.05, (0.9, 0.1)),
              (6.15, (0.4, 0.8), "out"), (7.3, (0.4, 0.9)), (7.9, (0.5, 0.6)), (8.3, (0.55, 0.5)),
              (8.95, (0.5, 0.45)), (9.05, (-0.25, 0.0), "out"), (9.9, (-0.2, 0.05)), (9.98, (-0.55, 0.05), "out"),
              (10.5, (-0.5, 0.0)), (10.58, (-0.15, -0.05), "out"), (12, (-0.15, -0.05))])
BROW_L = Track([(0, 0.0), (3.45, 0.0), (3.6, 1.0, "out"), (4.45, 0.9), (4.65, -0.5), (6.05, -0.5), (6.3, 0.2),
                (8.3, 0.4), (8.4, 1.1, "out"), (8.9, 0.8), (9.6, 0.6), (10.2, 0.9), (10.6, 1.0), (12, 0.8)])
BROW_R = Track([(0, 0.0), (3.45, 0.0), (3.6, 1.0, "out"), (4.45, 0.9), (4.65, 0.55), (6.05, 0.55), (6.3, 0.2),
                (8.3, 0.4), (8.4, 1.1, "out"), (8.9, 0.8), (9.6, 0.5), (10.2, 0.9), (10.6, 1.05), (12, 0.85)])
BROW_A = Track([(0, 0.0), (4.5, 0.0), (4.65, -0.7), (6.05, -0.7), (6.3, 0.0), (9.6, 0.0), (10.0, 0.5), (12, 0.5)])
SMILE = Track([(0, 0.15), (3.4, 0.15), (3.55, 0.0), (11.2, 0.0), (11.7, 0.15), (12, 0.15)])
SURPRISE_MOUTH = Track([(0, 0.0), (3.5, 0.0), (3.65, 0.35, "out"), (4.3, 0.25), (4.55, 0.0), (12, 0.0)])
BLINKS = [1.55, 4.62, 5.43, 6.12, 7.95, 9.03, 10.95]

def blink(t):
    v = 0.0
    for b in BLINKS:
        d = t - b
        if -0.01 < d < 0.16:
            v = max(v, math.sin(math.pi * clamp(d / 0.15)))
    return v

# body tracks
CROUCH = Track([(0, 0.0), (6.25, 0.0), (6.95, 1.0, "io"), (7.15, 1.0), (7.85, 0.0, "io"), (12, 0.0)])
LURCH = Track([(0, 0.0), (3.5, 0.0), (3.85, 1.0, "out"), (4.15, -0.35), (4.5, 0.0), (12, 0.0)])
REACH = Track([(0, 0.0), (6.30, 0.0), (6.95, 1.0, "io"), (7.12, 1.0), (12, 1.0)])
GRIP = Track([(0, 0.0), (7.02, 0.0), (7.06, 1.0, "lin"), (12, 1.0)])

def walk_amount(t):
    return 1.0 - smoothstep(3.6, 4.2, t)

# ============================================================================ camera
def camera(t):
    # tracking: lead the walker, ease into stop
    track_x = hip_x(min(t, T_STOP + 0.6)) + 260 - 200 * smoothstep(3.2, 4.6, t)
    lag = 0.0
    cx = track_x
    cy = 560.0
    z = 1.0
    # slow push during suspicious look
    zp = smoothstep(4.1, 6.4, t)
    z = lerp(1.0, 1.32, ease_in_out(zp))
    cx = lerp(cx, X_STOP + 40, ease_in_out(zp))
    cy = lerp(cy, 640.0, ease_in_out(zp))
    # follow the bend
    cb = CROUCH(t)
    cy += 40 * cb
    # push-in to close-up during the rise
    cu = ease_quint(clamp((t - 7.45) / 0.95))
    zc = lerp(z, 3.0, cu)
    cx = lerp(cx, X_STOP + 58, cu)
    cy = lerp(cy, GROUND - 452, cu)
    # gentle handheld drift (very subtle)
    cx += 3.0 * fbm(t * 0.35, 3) * zc
    cy += 2.0 * fbm(t * 0.4, 9) * zc
    # slow creep in the close-up
    zc *= 1.0 + 0.035 * smoothstep(8.4, 12.0, t)
    return cx, cy, zc

def layer_matrix(cam, p):
    cx, cy, z = cam
    ax, ay = ANCHOR
    lx = ax + (cx - ax) * p
    ly = ay + (cy - ay) * p
    zp = z ** p
    m = skia.Matrix()
    m.setTranslate(-lx, -ly)
    m.postScale(zp, zp)
    m.postTranslate(W / 2, H / 2)
    return m, zp

# ============================================================================ environment
rng = random.Random(7)
SKY_TOP, SKY_MID, SKY_LOW, SKY_HOR = "#1b1f4a", "#47386f", "#b85a78", "#f29a5a"

CLOUDS = [(rng.uniform(-300, 2400), rng.uniform(160, 420), rng.uniform(140, 320), rng.uniform(18, 34)) for _ in range(9)]

def draw_sky(cv, t, cam):
    m, z = layer_matrix(cam, 0.04)
    cv.save(); cv.concat(m)
    cv.drawRect(skia.Rect(-2000, -1200, 4000, 1400),
                lin_grad((0, -200), (0, 760), [SKY_TOP, SKY_MID, SKY_LOW, SKY_HOR, "#ffcf8a"], [0, 0.35, 0.68, 0.9, 1.0]))
    # sun
    sx, sy = 1330, 610
    glow(cv, sx, sy, 520, "#ff9a55", 0.35)
    glow(cv, sx, sy, 180, "#ffd29a", 0.6)
    cv.drawCircle(sx, sy, 46, paint("#fff0cf", 0.95, blur=3))
    # clouds
    for i, (x, y, w, h) in enumerate(CLOUDS):
        x = (x + t * (6 + i)) % 2700 - 300
        cp = union(ellipse(x, y, w, h), ellipse(x - w * 0.4, y + h * 0.3, w * 0.6, h * 0.8), ellipse(x + w * 0.35, y - h * 0.2, w * 0.5, h * 1.1))
        cv.drawPath(cp, paint("#7a4f86", 0.55, blur=10))
        cv.drawPath(shifted(cp, 0, h * 0.35), paint("#f0907a", 0.35, blur=12))
    cv.restore()

FAR_BLD = []
x = -500
while x < 2600:
    w = rng.uniform(60, 170)
    h = rng.uniform(120, 300)
    FAR_BLD.append((x, w, h, rng.random()))
    x += w * rng.uniform(0.75, 1.0)

def draw_far(cv, t, cam):
    m, z = layer_matrix(cam, 0.18)
    cv.save(); cv.concat(m)
    base = 720
    col = "#4a3a6a"
    for (x, w, h, r) in FAR_BLD:
        cv.drawRect(skia.Rect(x, base - h, x + w, base + 200), paint(col))
        if r > 0.6:
            cv.drawRect(skia.Rect(x + w * 0.2, base - h - 26, x + w * 0.45, base - h), paint(col))  # water tank
        for j in range(int(h / 34)):
            for k in range(int(w / 26)):
                if (hash((int(x), j, k)) % 7) == 0:
                    a = 0.55 + 0.35 * math.sin(t * 0.7 + j + k)
                    cv.drawRect(skia.Rect(x + 8 + k * 26, base - h + 14 + j * 34, x + 18 + k * 26, base - h + 26 + j * 34),
                                paint("#ffcf7a", a * 0.8))
    # mosque silhouette
    mx = 1580
    cv.drawRect(skia.Rect(mx - 90, base - 150, mx + 90, base + 200), paint("#43355f"))
    cv.drawPath(union(ellipse(mx, base - 160, 62, 58), poly([(mx - 6, base - 230), (mx + 6, base - 230), (mx + 2, base - 205), (mx - 2, base - 205)])), paint("#43355f"))
    for dx in (-118, 118):
        cv.drawRect(skia.Rect(mx + dx - 9, base - 330, mx + dx + 9, base + 200), paint("#43355f"))
        cv.drawPath(poly([(mx + dx - 14, base - 330), (mx + dx, base - 380), (mx + dx + 14, base - 330)]), paint("#43355f"))
        cv.drawRect(skia.Rect(mx + dx - 14, base - 270, mx + dx + 14, base - 262), paint("#43355f"))
    # far palms
    for px in (-120, 320, 980, 2050):
        draw_palm(cv, px, base + 40, 1.0, t, "#3b2e58", 260)
    # power lines
    for k in range(3):
        cv.drawPath(smooth_path([(-800, 420 + k * 14), (500, 470 + k * 14), (1700, 430 + k * 14), (3000, 470 + k * 14)], close=False),
                    paint("#2a2142", 0.7, stroke=1.6))
    # birds
    for i in range(5):
        bx = (200 + i * 140 + t * 55) % 2600 - 300
        by = 300 + 30 * math.sin(i * 1.7) + 6 * math.sin(t * 2 + i)
        f = math.sin(t * 9 + i * 1.3) * 7
        cv.drawPath(smooth_path([(bx - 9, by - f), (bx, by), (bx + 9, by - f)], close=False), paint("#2a2142", 0.9, stroke=2))
    cv.restore()

def draw_palm(cv, x, y, s, t, col, height, sway=1.0):
    top = (x + 18 * s, y - height * s)
    trunk = smooth_path([(x - 7 * s, y), (x + 4 * s, y - height * 0.5 * s), (top[0] - 4 * s, top[1]), (top[0] + 4 * s, top[1]),
                         (x + 12 * s, y - height * 0.5 * s), (x + 7 * s, y)], tension=0.5)
    cv.drawPath(trunk, paint(col))
    for i in range(9):
        a = -math.pi / 2 + (i - 4) * 0.42 + 0.06 * math.sin(t * 1.3 + i + x * 0.01) * sway
        ln = (95 + 15 * math.sin(i * 2.3)) * s
        droop = 0.55 + 0.25 * abs(i - 4) / 4
        p1 = (top[0] + math.cos(a) * ln * 0.5, top[1] + math.sin(a) * ln * 0.5 - 10 * s)
        p2 = (top[0] + math.cos(a) * ln, top[1] + math.sin(a) * ln + ln * droop * 0.6)
        leaf = smooth_path([top, (p1[0], p1[1] - 6 * s), p2, (p1[0], p1[1] + 6 * s)], tension=0.6)
        cv.drawPath(leaf, paint(col))

MID_BLD = [(-420, 260, 330, "#6a4d6e"), (-150, 300, 380, "#5e4a74"), (170, 240, 300, "#735068"), (430, 330, 420, "#5a4970"),
           (780, 260, 340, "#6b4f72"), (1060, 300, 390, "#5d4767"), (1380, 260, 330, "#6e5270"), (1660, 330, 410, "#584872"),
           (2010, 280, 350, "#6a4d6e")]

def draw_mid(cv, t, cam):
    m, z = layer_matrix(cam, 0.45)
    cv.save(); cv.concat(m)
    base = 860
    for i, (x, w, h, c) in enumerate(MID_BLD):
        top = base - h
        bp = poly([(x, base + 100), (x, top), (x + w, top), (x + w, base + 100)])
        cv.drawPath(bp, paint(c))
        cv.drawRect(skia.Rect(x - 6, top - 10, x + w + 6, top + 4), paint(mix(c, "#000000", 0.25)))
        # windows
        for j in range(2):
            for k in range(3):
                wx = x + 30 + k * (w - 60) / 2.6
                wy = top + 40 + j * 110
                lit = (i + j + k) % 3 != 0
                cv.drawRect(skia.Rect(wx, wy, wx + 46, wy + 62), paint("#2b2238"))
                if lit:
                    fl = 0.85 + 0.15 * noise(t * 2 + i * 3 + k, 5)
                    cv.drawRect(skia.Rect(wx + 4, wy + 4, wx + 42, wy + 58), lin_grad((wx, wy), (wx, wy + 60), ["#ffd98a", "#f0a050"]))
                    glow(cv, wx + 23, wy + 30, 70, "#ffb060", 0.18 * fl)
                cv.drawRect(skia.Rect(wx - 4, wy + 62, wx + 50, wy + 68), paint(mix(c, "#000000", 0.35)))
        # ground floor shop shutter
        cv.drawRect(skia.Rect(x + 16, base - 120, x + w - 16, base), paint(mix(c, "#000000", 0.3)))
        for k in range(10):
            cv.drawLine(x + 16, base - 120 + k * 12, x + w - 16, base - 120 + k * 12, paint(mix(c, "#000000", 0.45), stroke=1.5))
        # signboard
        sc = ["#c8463c", "#2f7f6f", "#d9a038", "#3a5fa0"][i % 4]
        cv.drawRect(skia.Rect(x + 20, base - 160, x + w - 20, base - 128), paint(sc))
        for k in range(4):
            cv.drawRect(skia.Rect(x + 34 + k * (w - 80) / 4, base - 151, x + 34 + k * (w - 80) / 4 + (w - 80) / 6, base - 137), paint("#f6ead2", 0.85))
    # palms & pole
    for px, s in ((90, 1.35), (1250, 1.5), (2150, 1.3)):
        draw_palm(cv, px, base, s, t, "#3d3050", 300)
    cv.drawRect(skia.Rect(640, 250, 652, base), paint("#3a2f45"))
    cv.drawRect(skia.Rect(610, 290, 682, 298), paint("#3a2f45"))
    for k in range(4):
        cv.drawPath(smooth_path([(-600, 300 + k * 9), (646, 294 + k * 2), (1800, 330 + k * 10), (2800, 300 + k * 9)], close=False), paint("#2a2238", 0.8, stroke=1.8))
    # streetlamp
    cv.drawRect(skia.Rect(1520, 420, 1530, base), paint("#2f2838"))
    cv.drawPath(smooth_path([(1525, 425), (1560, 405), (1600, 412)], close=False), paint("#2f2838", stroke=6))
    cv.drawRect(skia.Rect(1588, 410, 1616, 420), paint("#fff1c4"))
    glow(cv, 1602, 420, 160, "#ffd28a", 0.45)
    cv.restore()

# ------------------------------------------------------------------ the tea stall
STALL_P = 0.86

def draw_kettle(cv, x, y, t):
    body = smooth_path([(x - 40, y), (x - 46, y - 40), (x - 30, y - 70), (x + 30, y - 70), (x + 46, y - 40), (x + 40, y)], tension=0.5)
    cel(cv, body, "#b9b3ad", "#7d7670", light=(1, -0.6), depth=8, rim="#ffd1a0", rim_w=3, line="#3f3a36", line_w=2.2)
    cv.drawPath(smooth_path([(x - 26, y - 68), (x - 18, y - 84), (x + 18, y - 84), (x + 26, y - 68)], tension=0.5), paint("#9a948e"))
    cv.drawCircle(x, y - 88, 7, paint("#3f3a36"))
    spout = smooth_path([(x + 40, y - 30), (x + 74, y - 64), (x + 82, y - 66), (x + 46, y - 18)], tension=0.4)
    cv.drawPath(spout, paint("#a7a19b")); cv.drawPath(spout, paint("#3f3a36", stroke=2))
    cv.drawPath(smooth_path([(x - 30, y - 70), (x - 10, y - 118), (x + 18, y - 116), (x + 30, y - 70)], close=False), paint("#3f3a36", stroke=5))
    cv.drawPath(smooth_path([(x - 30, y - 52), (x + 6, y - 60), (x + 34, y - 54)], close=False), paint("#ffffff", 0.35, stroke=3))

def draw_stove(cv, x, y, t):
    st = poly([(x - 58, y + 40), (x - 50, y - 6), (x + 50, y - 6), (x + 58, y + 40)])
    cel(cv, st, "#9c5a3a", "#6e3a22", depth=6, line="#3a1d10", line_w=2)
    fl = 0.75 + 0.25 * noise(t * 7, 1) + 0.1 * noise(t * 17, 2)
    cv.drawOval(skia.Rect(x - 26, y + 6, x + 26, y + 30), paint("#2a0f06"))
    for k in range(5):
        fx = x - 16 + k * 8
        hh = 14 + 10 * (0.5 + 0.5 * noise(t * 9 + k * 3, 4))
        fp = smooth_path([(fx - 6, y + 26), (fx + 2 * noise(t * 6 + k, 8), y + 26 - hh), (fx + 6, y + 26)], tension=0.5)
        cv.drawPath(fp, paint("#ffb030", 0.9))
        cv.drawPath(shifted(fp, 0, 4), paint("#ff6a1a", 0.8))
    glow(cv, x, y + 18, 120 * fl, "#ff8a30", 0.55 * fl)
    return fl

def steam_particles(cv, ox, oy, t, n=26, life=2.6, rate=0.11, seed=0, spread=1.0, alpha=0.32, rise=70, scale=1.0):
    for i in range(n * 4):
        birth = i * rate - (seed * 0.37) % rate
        age = t - birth
        if age < 0 or age > life:
            continue
        u = age / life
        r = random.Random(i * 13 + seed)
        dx = r.uniform(-6, 6) * spread + age * (12 + r.uniform(-6, 10)) * spread
        wob = math.sin(age * 2.2 + r.uniform(0, 6)) * 10 * u * spread
        x = ox + dx + wob
        y = oy - age * rise * (1 - 0.25 * u)
        rad = (5 + 26 * u) * scale
        a = alpha * math.sin(math.pi * min(1, u * 1.15)) * (1 - u) ** 0.5
        cv.drawCircle(x, y, rad, paint("#f3e9e6", a, blur=rad * 0.6 + 2))

def draw_glass_cups(cv, x, y, n=5):
    for i in range(n):
        cx = x + i * 22
        cup = poly([(cx - 8, y - 28), (cx + 8, y - 28), (cx + 6, y), (cx - 6, y)])
        cv.drawPath(cup, paint("#e9d8c8", 0.35))
        cv.drawPath(poly([(cx - 7.2, y - 18), (cx + 7.2, y - 18), (cx + 6, y), (cx - 6, y)]), paint("#b46a2c", 0.9))
        cv.drawPath(cup, paint("#fff4e6", 0.7, stroke=1.4))
        cv.drawLine(cx - 4, y - 25, cx - 3.5, y - 4, paint("#ffffff", 0.6, stroke=1.5))

def draw_jar(cv, x, y, fill, lid):
    jar = smooth_path([(x - 26, y), (x - 30, y - 50), (x - 22, y - 64), (x + 22, y - 64), (x + 30, y - 50), (x + 26, y)], tension=0.4)
    cv.drawPath(jar, paint("#d8ecf0", 0.25))
    cv.save(); cv.clipPath(jar, skia.ClipOp.kIntersect, True)
    for k in range(10):
        cv.drawCircle(x - 20 + (k % 4) * 13, y - 8 - (k // 4) * 13, 8, paint(fill))
        cv.drawCircle(x - 20 + (k % 4) * 13, y - 8 - (k // 4) * 13, 8, paint(mix(fill, "#000000", 0.35), stroke=1.2))
    cv.restore()
    cv.drawPath(jar, paint("#ffffff", 0.55, stroke=1.6))
    cv.drawLine(x - 18, y - 52, x - 20, y - 10, paint("#ffffff", 0.6, stroke=3))
    cv.drawRect(skia.Rect(x - 22, y - 74, x + 22, y - 63), paint(lid))

BULBS = [(640, 410), (820, 436), (1000, 418), (1180, 440)]

def draw_stall(cv, t, cam, keeper_look):
    m, z = layer_matrix(cam, STALL_P)
    cv.save(); cv.concat(m)
    g = 880
    # back wall & interior
    cv.drawRect(skia.Rect(560, 400, 1250, g), lin_grad((0, 400), (0, g), ["#3a2620", "#5a3a2a"]))
    for k in range(9):
        cv.drawLine(560 + k * 80, 400, 560 + k * 80, g, paint("#2a1a14", 0.6, stroke=3))
    # shelf with packets & poster
    cv.drawRect(skia.Rect(600, 500, 1210, 510), paint("#7a4e2e"))
    cols = ["#e8423c", "#f2c230", "#3aa0d8", "#5bbf5a", "#e86fa8", "#f28a2a"]
    for k in range(18):
        cv.drawRect(skia.Rect(612 + k * 33, 470, 638 + k * 33, 500), paint(cols[k % 6]))
        cv.drawRect(skia.Rect(612 + k * 33, 476, 638 + k * 33, 482), paint("#ffffff", 0.6))
    # hanging chips strips
    for k in range(4):
        hx = 1150 + (k % 2) * 34
        for j in range(5):
            sw = 2 * math.sin(t * 1.6 + k + j * 0.4)
            cv.drawRect(skia.Rect(hx + sw - 12, 430 + j * 30 + (k // 2) * 0, hx + sw + 12, 456 + j * 30), paint(cols[(j + k) % 6]))
    # posts
    for px in (560, 1240):
        cv.drawRect(skia.Rect(px - 10, 360, px + 10, g + 10), paint("#5c3a22"))
        cv.drawRect(skia.Rect(px - 10, 360, px - 4, g + 10), paint("#7b5032"))
    # roof (corrugated tin)
    roof = poly([(500, 395), (1300, 385), (1280, 340), (520, 352)])
    cel(cv, roof, "#8f8a8c", "#5d585c", light=(0, -1), depth=6, line="#2c282c", line_w=2.2)
    cv.save(); cv.clipPath(roof, skia.ClipOp.kIntersect, True)
    for k in range(40):
        xx = 500 + k * 21
        cv.drawLine(xx, 330, xx - 4, 400, paint("#6e6a6e", stroke=3))
        cv.drawLine(xx + 6, 330, xx + 2, 400, paint("#b7b2b2", 0.6, stroke=2))
    cv.drawRect(skia.Rect(700, 330, 860, 400), paint("#a85a3a", 0.45))  # rust patch
    cv.restore()
    # tarp extension left (over bench)
    tarp = smooth_path([(370, 420), (520, 398), (560, 404), (420, 432)], tension=0.3)
    sag = 4 * math.sin(t * 1.2)
    tarp = poly([(330, 430 + sag), (520, 395), (560, 405), (360, 445 + sag)])
    cel(cv, tarp, "#2f6aa0", "#214c75", depth=4, line="#132c45", line_w=2)
    # bananas hanging
    bx, by = 1080, 400 + 3 * math.sin(t * 1.4)
    cv.drawLine(bx, 392, bx, by + 10, paint("#3a2a1a", stroke=2))
    for k in range(7):
        a = -1.2 + k * 0.4
        b = smooth_path([(bx, by + 14), (bx + math.cos(a) * 18, by + 40 + abs(k - 3) * 2), (bx + math.cos(a) * 22, by + 66 - abs(k - 3) * 4)], close=False)
        cv.drawPath(b, paint("#e8c43a", stroke=11))
        cv.drawPath(b, paint("#9a7a1a", 0.6, stroke=1.5))
    # keeper (behind counter)
    draw_keeper(cv, 925, g, t, keeper_look)
    # counter
    ctr = poly([(600, g), (600, 640), (1200, 640), (1200, g)])
    cel(cv, ctr, "#3f8a6a", "#2c644c", light=(1, 0), depth=14, line="#173829", line_w=2.4)
    for k in range(1, 7):
        cv.drawLine(600, 640 + k * 34, 1200, 640 + k * 34, paint("#1f4a37", 0.7, stroke=2))
    # painted motif strip
    cv.drawRect(skia.Rect(600, 650, 1200, 676), paint("#c8463c"))
    for k in range(20):
        cx = 615 + k * 30
        cv.drawPath(poly([(cx, 663), (cx + 8, 655), (cx + 16, 663), (cx + 8, 671)]), paint("#f2c230"))
    cv.drawRect(skia.Rect(588, 626, 1212, 642), paint("#6b4426"))
    cv.drawRect(skia.Rect(588, 626, 1212, 630), paint("#9a6a3c"))
    # counter-top items
    fl = draw_stove(cv, 720, 590, t)
    draw_kettle(cv, 720, 590, t)
    glow(cv, 720, 560, 160, "#ff9a40", 0.18 * fl)
    draw_jar(cv, 860, 626, "#d89a4a", "#c8463c")
    draw_jar(cv, 930, 626, "#e8c86a", "#3a7fd0")
    draw_jar(cv, 1000, 626, "#b8632e", "#5bbf5a")
    draw_glass_cups(cv, 1070, 626)
    # bench with customer (left)
    draw_customer(cv, 470, g, t)
    # bulbs + wires
    cv.drawPath(smooth_path([(560, 395), (640, 404), (820, 430), (1000, 412), (1180, 434), (1240, 392)], close=False, tension=0.4), paint("#1a1414", stroke=2))
    for i, (x, y) in enumerate(BULBS):
        y += 2 * math.sin(t * 1.1 + i)
        cv.drawLine(x, y - 22, x, y - 8, paint("#1a1414", stroke=2))
        cv.drawCircle(x, y, 9, paint("#fff3c8"))
    cv.restore()
    return fl

def draw_keeper(cv, x, g, t, look):
    st = KEEPER
    torso_hip = (x, 700)
    breathe = math.sin(t * 1.8) * 0.5
    # stirring hand motion (spoon in glass)
    stir = t * 5.0
    # body
    def T(p):
        return (torso_hip[0] + p[0], torso_hip[1] + p[1] + breathe)
    body = smooth_path([T((-46, 40)), T((-50, -60)), T((-36, -110)), T((-10, -122)), T((14, -122)), T((40, -110)), T((52, -60)), T((48, 40))], tension=0.5)
    cel(cv, body, st["shirt"], st["shirt_shade"], depth=8, line=st["shirt_line"], line_w=2)
    # gamchha towel on shoulder (red/green check)
    towel = smooth_path([T((-40, -112)), T((-10, -124)), T((-22, -60)), T((-42, -30)), T((-50, -70))], tension=0.5)
    cv.drawPath(towel, paint("#c23a3a"))
    cv.save(); cv.clipPath(towel, skia.ClipOp.kIntersect, True)
    for k in range(-6, 6):
        cv.drawLine(*T((-60 + k * 9, -130)), *T((-60 + k * 9 + 20, -20)), paint("#2f8a4a", 0.8, stroke=3))
    cv.restore()
    cv.drawPath(towel, paint("#5a1414", stroke=1.8))
    # head
    yaw = lerp(0.15 + 0.08 * math.sin(t * 0.6), -0.55, look)
    face = dict(eye_open=1.0, blink=1.0 if (t % 3.1) < 0.12 else 0.0, gaze=(lerp(0.2, -0.7, look), lerp(0.6, 0.1, look)),
                brow=(0.1 + 0.4 * look, 0.1 + 0.4 * look), brow_ang=(0, 0), mouth=(0, 0.2, 0, 0.1))
    nk = capsule(T((0, -118)), T((2, -136)), 13, 12)
    cv.drawPath(nk, paint(st["skin"]["base"]))
    draw_head(cv, *T((4, -168)), 0.95, yaw, lerp(0.5, 0.1, look), 0.03 * math.sin(t), face, st, 2.2)
    # arms: one holds glass on counter, other stirs with spoon
    sh_r = T((36, -100)); sh_l = T((-34, -100))
    gx, gy = x + 40, 618
    tgt = (gx - 4 + 6 * math.cos(stir), gy - 40 + 3 * math.sin(stir))
    e, w_ = ik2(sh_r, tgt, 66, 62, 1)
    e2, w2 = ik2(sh_l, (x - 10, 622), 66, 62, 1)
    keeper_arm_style = dict(st, watch=None)
    keeper_arm_style["shirt_check"] = None
    draw_arm(cv, sh_l, e2, w2, 0.0, 1, keeper_arm_style, 2.0)
    # glass
    cup = poly([(gx - 10, gy - 34), (gx + 10, gy - 34), (gx + 8, gy + 2), (gx - 8, gy + 2)])
    cv.drawPath(cup, paint("#e9d8c8", 0.4))
    cv.drawPath(poly([(gx - 9, gy - 22), (gx + 9, gy - 22), (gx + 8, gy + 2), (gx - 8, gy + 2)]), paint("#b46a2c"))
    cv.drawPath(cup, paint("#fff4e6", 0.8, stroke=1.5))
    cv.drawLine(gx - 1 + 3 * math.cos(stir), gy - 16, tgt[0] + 10, tgt[1] - 8, paint("#d8d8d8", stroke=2.5))
    draw_arm(cv, sh_r, e, w_, 0.0, 1, keeper_arm_style, 2.0)
    steam_particles(cv, gx, gy - 36, t, n=10, life=1.6, rate=0.3, seed=11, spread=0.4, alpha=0.18, rise=40, scale=0.5)

CUSTOMER = dict(HERO, shirt="#8a3048", shirt_shade="#5f1f32", shirt_line="#2e0e18", shirt_check=None,
                pants="#5c5a56", pants_shade="#403e3b", pants_line="#1e1d1b", style="quiff", stubble=True, watch=None,
                hair="#1a1414", skin=dict(base="#a8693f", shade="#7a4627", rim="#ffb877", line="#33190d", hi="#c4875c"))
_cust = Hero(CUSTOMER)

def draw_customer(cv, x, g, t):
    # bench
    cv.drawRect(skia.Rect(x - 120, g - 112, x + 120, g - 98), paint("#7a4e2e"))
    cv.drawRect(skia.Rect(x - 120, g - 112, x + 120, g - 108), paint("#a8743f"))
    for lx in (x - 105, x + 95):
        cv.drawRect(skia.Rect(lx, g - 100, lx + 10, g), paint("#5a3820"))
    sip = smoothstep(0.0, 0.5, (math.sin(t * 0.9 - 1.0) + 0.2))  # periodic sipping
    hip = (x - 10, g - 128)
    face = dict(eye_open=0.85 + 0.15 * (1 - sip), blink=1.0 if (t % 3.7) < 0.12 else 0.0, gaze=(0.4, 0.2 - 0.3 * sip),
                brow=(0.0, 0.0), brow_ang=(0, 0), mouth=(0.0, 0.2, 0.3 * sip, 0.1))
    cup_pos = (lerp(x + 52, x + 46, sip), lerp(g - 150, g - 268, sip))
    pose = dict(hip=hip, spine=lerp(0.12, -0.08, sip), bend=0.0, foot_near=(x + 60, g - 12, 0.0), foot_far=(x + 80, g - 16, 0.0),
                hand_near=(cup_pos[0] - 14, cup_pos[1] + 8, -1.2, 1), hand_far=(x + 60, g - 140, 0.0, 1),
                head=dict(yaw=0.7, pitch=lerp(0.3, -0.5, sip), roll=lerp(0.0, -0.18, sip)), face=face)
    def cup(cv2, wr, ang):
        cx, cy = cup_pos
        c = poly([(cx - 9, cy - 26), (cx + 9, cy - 26), (cx + 7, cy + 2), (cx - 7, cy + 2)])
        cv2.drawPath(c, paint("#e9d8c8", 0.45))
        cv2.drawPath(poly([(cx - 8, cy - 16), (cx + 8, cy - 16), (cx + 7, cy + 2), (cx - 7, cy + 2)]), paint("#b46a2c"))
        cv2.drawPath(c, paint("#fff4e6", 0.8, stroke=1.4))
    pose["wallet_in_hand"] = cup
    pose["wallet_behind"] = True
    _cust.draw(cv, pose, 2.2)
    if sip < 0.3:
        steam_particles(cv, cup_pos[0], cup_pos[1] - 28, t, n=8, life=1.4, rate=0.35, seed=21, spread=0.3, alpha=0.15, rise=35, scale=0.45)

# ------------------------------------------------------------------ ground & hero layer
def draw_ground(cv, t, cam):
    m, z = layer_matrix(cam, 1.0)
    cv.save(); cv.concat(m)
    # sidewalk
    cv.drawRect(skia.Rect(-1500, 870, 3600, 975), lin_grad((0, 870), (0, 975), ["#7c6670", "#9a7f80"]))
    for k in range(-30, 60):
        xx = k * 90
        cv.drawLine(xx, 872, xx - 30, 973, paint("#5e4c58", 0.6, stroke=2))
    cv.drawLine(-1500, 920, 3600, 920, paint("#5e4c58", 0.35, stroke=2))
    # warm light pool from stall
    glow(cv, 900, 900, 520, "#ff9a50", 0.22)
    # curb
    cv.drawRect(skia.Rect(-1500, 972, 3600, 990), paint("#b9a6a2"))
    cv.drawRect(skia.Rect(-1500, 988, 3600, 1000), paint("#5a4752"))
    # road
    cv.drawRect(skia.Rect(-1500, 1000, 3600, 1500), lin_grad((0, 1000), (0, 1300), ["#3b3346", "#2b2535"]))
    for k in range(-20, 40):
        cv.drawRect(skia.Rect(k * 260, 1100, k * 260 + 140, 1112), paint("#d8cfc0", 0.5))
    # puddle with sky reflection
    pud = ellipse(1500, 1045, 170, 22)
    cv.drawPath(pud, lin_grad((0, 1025), (0, 1065), ["#f29a5a", "#7a4f86"]))
    cv.drawPath(pud, paint("#ffffff", 0.25, stroke=2))
    # crate near stall right
    cr = poly([(1250, 905), (1250, 830), (1350, 830), (1350, 905)])
    cel(cv, cr, "#a87a48", "#7a5430", depth=8, line="#3a2410", line_w=2)
    for k in range(3):
        cv.drawLine(1250, 845 + k * 22, 1350, 845 + k * 22, paint("#5a3a1a", stroke=3))
    cv.restore()

def wallet_draw(cv, x, y, flat, ang=0.0, s=1.0, sparkle=0.0, lw=2.0):
    cv.save()
    cv.translate(x, y)
    cv.rotate(math.degrees(ang))
    cv.scale(s, s)
    w, h = 40, lerp(28, 9, flat)
    sk = lerp(0, 10, flat)
    body = poly([(-w / 2 + sk, -h), (w / 2 + sk, -h), (w / 2, 0), (-w / 2, 0)])
    if flat > 0.5:
        cv.drawOval(skia.Rect(-w / 2 - 6, -4, w / 2 + 14, 6), paint("#000000", 0.35, blur=3))
    cel(cv, body, "#7a4425", "#4e2914", light=(0.6, -1), depth=4, line="#2a1308", line_w=lw)
    # stitching & flap
    inner = poly([(-w / 2 + sk + 4, -h + 3), (w / 2 + sk - 4, -h + 3), (w / 2 - 4, -3), (-w / 2 + 4, -3)])
    st = paint("#c9915a", 0.8, stroke=1.0)
    st.setPathEffect(skia.DashPathEffect.Make([3.0, 2.5], 0))
    cv.drawPath(inner, st)
    if flat < 0.6:
        cv.drawPath(poly([(w / 2 - 14, -h * 0.62), (w / 2, -h * 0.62), (w / 2, -h * 0.32), (w / 2 - 14, -h * 0.32)]), paint("#5e321a"))
        cv.drawCircle(w / 2 - 8, -h * 0.47, 2.0, paint("#e8c07a"))
        # banknote peeking
        cv.drawPath(poly([(-w / 2 + 6, -h), (-w / 2 + 6, -h - 5), (-w / 2 + 22, -h - 6), (-w / 2 + 22, -h)]), paint("#7fb07a"))
    cv.drawLine(-w / 2 + sk + 3, -h + 1.5, w / 2 + sk - 3, -h + 1.5, paint("#c27a48", 0.8, stroke=1.4))
    cv.restore()
    if sparkle > 0:
        sx, sy = x + 14, y - 6
        r = 26 * sparkle
        sp = poly([(sx, sy - r), (sx + r * 0.12, sy - r * 0.12), (sx + r, sy), (sx + r * 0.12, sy + r * 0.12),
                   (sx, sy + r), (sx - r * 0.12, sy + r * 0.12), (sx - r, sy), (sx - r * 0.12, sy - r * 0.12)])
        p = paint("#fff6dc", 0.95 * sparkle)
        p.setBlendMode(skia.BlendMode.kPlus)
        cv.drawPath(sp, p)
        glow(cv, sx, sy, 40 * sparkle, "#ffe0a0", 0.7 * sparkle)

def sparkle(t):
    v = 0.0
    for c, d in ((3.32, 0.55), (6.05, 0.4)):
        u = (t - c) / d
        if 0 <= u <= 1:
            v = max(v, math.sin(math.pi * u) * (1 if c < 5 else 0.6))
    return v

hero = Hero(HERO)

def hero_pose(t, lipsync):
    wa = walk_amount(t)
    hx = hip_x(t)
    cr = CROUCH(t)
    lur = LURCH(t)
    fn = foot_state(t, PLAN_NEAR, 0)
    ff = foot_state(t, PLAN_FAR, 6)
    # hip height: bob while walking, crouch to pick up
    ph = 2 * math.pi * (t - 0.25) / 0.5
    bob = -4.5 * math.cos(ph) * wa
    hh = lerp(229.0, 219.0, wa) + bob
    hh = lerp(hh, 112.0, ease_in_out(cr))
    hxx = hx - 4 * lur - 30 * cr + 2.5 * math.sin(ph / 2) * wa * 0.0
    hip = (hxx, GROUND - hh)
    spine = 0.07 * wa + 0.02 * math.sin(ph) * wa + 0.16 * lur + 0.95 * ease_in_out(cr)
    spine += -0.04 * smoothstep(8.2, 8.5, t) + 0.015 * math.sin(t * 1.6) * (1 - wa)
    bend = 0.32 * ease_in_out(cr)
    breathe = math.sin(t * 2.0) * (1 - wa)
    # arms
    def TR(p):
        x, y = p
        c, s = math.cos(spine), math.sin(spine)
        return (hip[0] + x * c - y * s, hip[1] + x * s + y * c)
    shn = TR((-19, -132)); shf = TR((26, -136))
    swing = 0.42 * math.cos(2 * math.pi * (t + 0.25) / 1.0) * wa
    def fk(sh, a, ln=146):
        return (sh[0] + math.sin(a) * ln + 6, sh[1] + math.cos(a) * ln)
    rest_n = fk(shn, 0.10 + 0.3 * lur, 145)
    rest_f = fk(shf, 0.05, 145)
    hn = fk(shn, -swing + 0.08)
    hf = fk(shf, swing + 0.05)
    hn = (lerp(rest_n[0], hn[0], wa), lerp(rest_n[1], hn[1], wa))
    hf = (lerp(rest_f[0], hf[0], wa), lerp(rest_f[1], hf[1], wa))
    # far hand rests on knee while crouched
    knee_far = (hip[0] + 70 * cr, GROUND - 120)
    hf = (lerp(hf[0], knee_far[0] + 10, cr), lerp(hf[1], knee_far[1] - 10, cr))
    # reach / hold
    rch = REACH(t)
    wall_grab = (WALLET[0] - 22, WALLET[1] - 18)
    # after grab: lift to chest, then present near face
    lift = smoothstep(7.15, 7.85, t)
    present = ease_in_out(clamp((t - 7.75) / 0.6))
    head_guess = TR((8, -196))
    chest_hold = (hip[0] + 62, hip[1] - 120)
    face_hold = (head_guess[0] + 38, head_guess[1] + 74)
    if t < 7.12:
        target = wall_grab
    else:
        target = (lerp(wall_grab[0], chest_hold[0], lift), lerp(wall_grab[1], chest_hold[1], lift))
        target = (lerp(target[0], face_hold[0], present), lerp(target[1], face_hold[1], present))
    # dialogue gestures: small shake on "আরে", lift on "কার"
    ts = t - SPEECH_START
    target = (target[0] + 3 * math.sin(ts * 30) * math.exp(-((ts - 0.15) / 0.12) ** 2), target[1] - 10 * math.exp(-((ts - 2.25) / 0.35) ** 2))
    target = (target[0] + 1.5 * math.sin(t * 1.3), target[1] + 1.5 * math.sin(t * 1.9))
    hn = (lerp(hn[0], target[0], rch), lerp(hn[1], target[1], rch))
    grip = GRIP(t)
    hand_rel = lerp(0.0, -0.35, rch) + lerp(0, -0.6, present)
    # face
    m = lipsync(t)
    sm = SURPRISE_MOUTH(t)
    mouth = (max(m[0], sm), m[1], max(m[2], sm * 1.5), SMILE(t) * (1 - min(1, m[0] * 3)))
    face = dict(eye_open=EYE_OPEN(t), blink=blink(t), gaze=GAZE(t), brow=(BROW_L(t), BROW_R(t)),
                brow_ang=(BROW_A(t), -BROW_A(t) * 0.6), squint=SQUINT(t), mouth=mouth)
    head = dict(yaw=YAW(t) + 0.02 * noise(t * 1.5, 4), pitch=PITCH(t), roll=ROLL(t) + spine * 0.45 * cr + 0.02 * math.sin(ph) * wa,
                dx=0, dy=-2 * math.cos(ph) * wa)
    walleted = t >= 7.06
    pose = dict(hip=hip, spine=spine, bend=bend, foot_near=fn, foot_far=ff, hand_near=(hn[0], hn[1], hand_rel, grip),
                hand_far=(hf[0], hf[1], 0.0, 0.3 if cr < 0.5 else 0.0), head=head, face=face, breathe=breathe)
    if walleted:
        flat = 1 - smoothstep(7.06, 7.5, t)
        def wd(cv, wr, ang, flat=flat, present=present):
            wallet_draw(cv, wr[0] + 14, wr[1] + 16 - 6 * present, flat, ang=lerp(0.0, -0.25, present), s=1.0, lw=1.8)
        pose["wallet_in_hand"] = wd
        pose["wallet_behind"] = False
    return pose, walleted

def draw_hero_layer(cv, t, cam, lipsync):
    m, z = layer_matrix(cam, 1.0)
    cv.save(); cv.concat(m)
    pose, walleted = hero_pose(t, lipsync)
    lw = 2.4 / (z ** 0.45)
    # contact shadows
    for f in (pose["foot_near"], pose["foot_far"]):
        hgt = clamp((GROUND - 12 - f[1]) / 30)
        cv.drawOval(skia.Rect(f[0] - 24, GROUND + 2, f[0] + 46, GROUND + 14), paint("#1a0e18", 0.45 * (1 - 0.6 * hgt), blur=4))
    hx = pose["hip"][0]
    cv.drawOval(skia.Rect(hx - 90, GROUND - 2, hx + 110, GROUND + 18), paint("#1a0e18", 0.25, blur=12))
    if not walleted:
        wallet_draw(cv, WALLET[0], WALLET[1], 1.0, sparkle=sparkle(t), lw=lw * 0.9)
    hero.draw(cv, pose, lw)
    cv.restore()
    return pose

# ------------------------------------------------------------------ foreground
FG_DUST = [(random.Random(i).uniform(-200, 2600), random.Random(i + 99).uniform(200, 1000), random.Random(i + 7).uniform(1.5, 4.5)) for i in range(70)]

def draw_fg(cv, t, cam):
    m, z = layer_matrix(cam, 1.55)
    cv.save(); cv.concat(m)
    # big banana leaves (bottom left) and potted plant (right)
    for k, (bx, by, ang, ln) in enumerate(((-260, 1180, -1.05, 420), (-200, 1220, -0.65, 380), (-330, 1150, -1.4, 360))):
        a = ang + 0.05 * math.sin(t * 1.1 + k * 1.7) + 0.02 * math.sin(t * 2.7 + k)
        tip = (bx + math.cos(a) * ln, by + math.sin(a) * ln)
        nrm = (-math.sin(a), math.cos(a))
        mid = (bx + math.cos(a) * ln * 0.5, by + math.sin(a) * ln * 0.5)
        leaf = smooth_path([(bx, by), (mid[0] + nrm[0] * 70, mid[1] + nrm[1] * 70), tip, (mid[0] - nrm[0] * 60, mid[1] - nrm[1] * 60)], tension=0.6)
        cv.drawPath(leaf, paint("#1f3a2a"))
        cv.drawPath(smooth_path([(bx, by), mid, tip], close=False), paint("#33573f", stroke=6))
    # right: post + plant
    cv.drawRect(skia.Rect(2010, 300, 2060, 1400), paint("#2a1e24"))
    cv.drawRect(skia.Rect(2010, 300, 2020, 1400), paint("#4a3438"))
    for k in range(6):
        a = -1.9 + k * 0.32 + 0.06 * math.sin(t * 1.4 + k)
        p0 = (1960, 1150)
        tip = (p0[0] + math.cos(a) * 300, p0[1] + math.sin(a) * 300)
        leaf = smooth_path([p0, (p0[0] + math.cos(a + 0.15) * 160, p0[1] + math.sin(a + 0.15) * 160), tip, (p0[0] + math.cos(a - 0.15) * 160, p0[1] + math.sin(a - 0.15) * 160)], tension=0.6)
        cv.drawPath(leaf, paint("#203a2c"))
    cv.restore()

def draw_particles(cv, t, cam):
    """Floating dust / embers lit by the stall, drawn in screen space with depth."""
    m, z = layer_matrix(cam, 1.2)
    cv.save(); cv.concat(m)
    for i, (x, y, r) in enumerate(FG_DUST):
        xx = x + 25 * fbm(t * 0.25 + i, i) + t * 8
        yy = y + 30 * fbm(t * 0.2 + i * 3, i + 50) - t * 6
        a = 0.35 + 0.35 * math.sin(t * 1.3 + i)
        p = paint("#ffd9a0", a * 0.6, blur=r)
        p.setBlendMode(skia.BlendMode.kPlus)
        cv.drawCircle(xx, yy, r * 1.4, p)
    cv.restore()

# ------------------------------------------------------------------ falling leaves
def draw_falling_leaves(cv, t, cam):
    m, z = layer_matrix(cam, 1.0)
    cv.save(); cv.concat(m)
    for i in range(5):
        r = random.Random(100 + i)
        t0 = r.uniform(-3, 9)
        age = t - t0
        if not (0 <= age <= 5):
            continue
        x = r.uniform(400, 1500) + age * 40 + 40 * math.sin(age * 1.8 + i)
        y = 360 + age * 110
        if y > GROUND + 5:
            y = GROUND + 5
        a = math.sin(age * 3 + i) * 1.2
        cv.save(); cv.translate(x, y); cv.rotate(math.degrees(a))
        lf = smooth_path([(-9, 0), (0, -4), (9, 0), (0, 4)], tension=0.6)
        cv.drawPath(lf, paint(["#c8742a", "#9aa03a", "#d8a03a"][i % 3]))
        cv.restore()
    cv.restore()

# ============================================================================ frame
def blur_layer(cv, sigma, fn):
    if sigma < 0.3:
        fn(); return
    p = skia.Paint()
    p.setImageFilter(skia.ImageFilters.Blur(sigma, sigma, skia.TileMode.kClamp))
    cv.saveLayer(None, p)
    fn()
    cv.restore()

def haze(cv, color, a0, a1, y0=0, y1=H):
    cv.drawRect(skia.Rect(0, 0, W, H), lin_grad((0, y0), (0, y1), [hexc(color, a0), hexc(color, a1)]))

_GRAIN = None

def grain(cv, t):
    global _GRAIN
    if _GRAIN is None:
        imgs = []
        for k in range(6):
            n = (np.random.default_rng(k).normal(128, 40, (H // 2, W // 2))).clip(0, 255).astype(np.uint8)
            rgba = np.dstack([n, n, n, np.full_like(n, 255)])
            imgs.append(skia.Image.fromarray(rgba))
        _GRAIN = imgs
    img = _GRAIN[int(t * FPS) % len(_GRAIN)]
    p = skia.Paint(); p.setBlendMode(skia.BlendMode.kOverlay); p.setAlphaf(0.10)
    cv.drawImageRect(img, skia.Rect(0, 0, W, H), skia.SamplingOptions(), p)

def render_frame(t, lipsync):
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    cam = camera(t)
    z = cam[2]
    dof = clamp((z - 1.0) / 2.0)   # 0 wide -> 1 close-up
    # looking around: keeper glances at the hero when he stops & talks
    keeper_look = smoothstep(4.3, 4.9, t) * (1 - smoothstep(6.2, 6.8, t)) + smoothstep(8.6, 9.3, t)
    keeper_look = clamp(keeper_look)

    blur_layer(cv, 0.0 + 6 * dof, lambda: draw_sky(cv, t, cam))
    blur_layer(cv, 1.4 + 9 * dof, lambda: draw_far(cv, t, cam))
    haze(cv, "#c87a8a", 0.05, 0.28, 300, 900)
    blur_layer(cv, 1.0 + 8 * dof, lambda: draw_mid(cv, t, cam))
    haze(cv, "#b0607a", 0.04, 0.16, 200, 1000)
    # sun rays
    m, zz = layer_matrix(cam, 0.1)
    sx, sy = m.mapXY(1330, 610)
    cv.save()
    for k in range(7):
        a = -2.6 + k * 0.28 + 0.03 * math.sin(t * 0.5 + k)
        ray = poly([(sx, sy), (sx + math.cos(a - 0.05) * 2200, sy + math.sin(a - 0.05) * 2200), (sx + math.cos(a + 0.05) * 2200, sy + math.sin(a + 0.05) * 2200)])
        p = paint("#ffc890", 0.05, blur=30); p.setBlendMode(skia.BlendMode.kPlus)
        cv.drawPath(ray, p)
    cv.restore()
    fl = [1.0]
    def stall():
        fl[0] = draw_stall(cv, t, cam, keeper_look)
        mm, zs = layer_matrix(cam, STALL_P)
        cv.save(); cv.concat(mm)
        steam_particles(cv, 795, 528, t, n=30, life=2.8, rate=0.09, seed=1, spread=1.0, alpha=0.30, rise=72)
        steam_particles(cv, 720, 485, t, n=20, life=3.6, rate=0.18, seed=5, spread=1.6, alpha=0.12, rise=55, scale=1.6)  # stove smoke
        cv.restore()
    blur_layer(cv, 0.0 + 5.5 * dof, stall)
    # bulb glows (bokeh grows in close-up)
    mm, zs = layer_matrix(cam, STALL_P)
    for i, (bx, by) in enumerate(BULBS):
        x, y = mm.mapXY(bx, by)
        f = 0.9 + 0.1 * noise(t * 3 + i * 5, 3)
        glow(cv, x, y, (90 + 120 * dof) * zs ** 0.5, "#ffc070", 0.55 * f)
        if dof > 0.05:
            p = paint("#ffd9a0", 0.25 * dof, blur=2); p.setBlendMode(skia.BlendMode.kPlus)
            cv.drawCircle(x, y, 26 * zs * 0.6 * dof + 4, p)
    blur_layer(cv, 0.0 + 1.5 * dof, lambda: draw_ground(cv, t, cam))
    draw_falling_leaves(cv, t, cam)
    pose = draw_hero_layer(cv, t, cam, lipsync)
    # warm key light wrap from the stall (screen-blend radial)
    m1, _ = layer_matrix(cam, 1.0)
    kx, ky = m1.mapXY(900, 600)
    p = skia.Paint()
    p.setShader(skia.GradientShader.MakeRadial((kx, ky), 900 * z ** 0.5, [hexc("#ff9a50", 0.18), hexc("#ff9a50", 0.0)]))
    p.setBlendMode(skia.BlendMode.kScreen)
    cv.drawRect(skia.Rect(0, 0, W, H), p)
    blur_layer(cv, 9 + 6 * dof, lambda: draw_fg(cv, t, cam))
    blur_layer(cv, 0.0, lambda: draw_particles(cv, t, cam))
    # grade: cool top, warm bottom (soft light)
    p = lin_grad((0, 0), (0, H), [hexc("#3a3a8a", 0.35), hexc("#000000", 0.0), hexc("#ff8a40", 0.25)], [0, 0.5, 1])
    p.setBlendMode(skia.BlendMode.kSoftLight)
    cv.drawRect(skia.Rect(0, 0, W, H), p)
    # vignette
    p = skia.Paint()
    p.setShader(skia.GradientShader.MakeRadial((W / 2, H / 2), W * 0.72, [hexc("#000000", 0.0), hexc("#000000", 0.0), hexc("#0a0410", 0.62)], [0, 0.55, 1]))
    cv.drawRect(skia.Rect(0, 0, W, H), p)
    grain(cv, t)
    # fades
    fade = max(1 - smoothstep(0.0, 0.5, t), smoothstep(11.6, 12.0, t))
    if fade > 0:
        cv.drawRect(skia.Rect(0, 0, W, H), paint("#000000", fade))
    img = surf.makeImageSnapshot()
    return img
