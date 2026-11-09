"""Model sheet for the 'Home' main character: turnaround, expressions, poses, palette."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import skia
from engine.draw import paint, poly
from engine.turnaround import draw_character, draw_head, Proj, FACES, PAL, H

W, Hh = 3200, 2050
BG, INK, SUB = "#f6efe4", "#4a3528", "#8a7464"
font = lambda sz, bold=False: skia.Font(skia.Typeface("DejaVu Sans", skia.FontStyle.Bold() if bold else skia.FontStyle.Normal()), sz)

def text(cv, s, x, y, sz, col=INK, bold=False, center=False):
    f = font(sz, bold)
    if center:
        x -= f.measureText(s) / 2
    cv.drawString(s, x, y, f, paint(col))

def card(cv, x, y, w, h):
    r = skia.RRect.MakeRectXY(skia.Rect(x, y, x + w, y + h), 22, 22)
    cv.drawRRect(r, paint("#fffaf2")); cv.drawRRect(r, paint("#e4d6c4", stroke=3))

surf = skia.Surface(W, Hh); cv = surf.getCanvas(); cv.clear(skia.Color4f(0.965, 0.937, 0.894, 1))
text(cv, "Main Character - Home (T-Shirt & Trousers)", 60, 90, 58, bold=True)
text(cv, "Production model sheet v3  |  age 20-25  |  soft-shaded flat 2D  |  height = 5 heads  |  identical rig in every view", 62, 140, 28, SUB)

# ---------------- turnaround
G, S = 1150, 1.08
views = [("Front", 0.0), ("3/4", 0.62), ("Side (profile)", math.pi / 2), ("Back", math.pi)]
xs = [330, 900, 1460, 2000]
# head-unit guide lines
unit = 170 * S
top = G - H["sole"] * S
for k in range(6):
    yy = top + k * unit
    pp = paint("#d9c9b5", stroke=2); pp.setPathEffect(skia.DashPathEffect.Make([14.0, 10.0], 0))
    cv.drawLine(120, yy, 2280, yy, pp)
    text(cv, f"{k}", 80, yy + 10, 26, SUB)
for (name, a), x in zip(views, xs):
    cv.drawOval(skia.Rect(x - 130, G - 14, x + 130, G + 18), paint("#d8cbb9"))
    draw_character(cv, x, G, a, S)
    text(cv, name, x, G + 70, 34, INK, center=True)

# ---------------- palette
px, py = 2420, 220
card(cv, px - 30, py - 50, 740, 930)
text(cv, "Colour palette", px, py, 36, bold=True)
sw = [("Skin", PAL["skin"]), ("Skin shadow", PAL["skin_sh"]), ("Hair", PAL["hair"]), ("Hair highlight", PAL["hair_hi"]),
      ("T-shirt", PAL["shirt"]), ("T-shirt shadow", PAL["shirt_sh"]), ("Stripes & collar", PAL["stripe"]), ("Trousers", PAL["pants"]),
      ("Trousers shadow", PAL["pants_sh"]), ("Shoes", PAL["shoe"]), ("Glasses frame", PAL["frame"]), ("Blush", PAL["blush"])]
for i, (n, c) in enumerate(sw):
    yy = py + 40 + i * 68
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(px, yy, px + 90, yy + 52), 10, 10), paint(c))
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(px, yy, px + 90, yy + 52), 10, 10), paint("#00000022" if False else "#cbbba8", stroke=2))
    text(cv, n, px + 115, yy + 24, 26)
    text(cv, c.upper(), px + 115, yy + 50, 22, SUB)

# ---------------- expressions
text(cv, "Expressions", 60, 1320, 40, bold=True)
names = ["neutral", "happy", "talking", "surprised", "sad", "worried", "angry", "thinking"]
for i, n in enumerate(names):
    cx = 70 + (i % 4) * 330; cy = 1350 + (i // 4) * 345
    card(cv, cx, cy, 300, 320)
    P = Proj(cx + 150, cy + 30 - 0, 0.18 if n != "thinking" else 0.35, 1.0)
    P.top = cy + 175 - H["head_c"] * 1.0
    cv.save(); cv.clipRect(skia.Rect(cx + 4, cy + 4, cx + 296, cy + 316))
    draw_head(cv, P, P.a, FACES[n])
    cv.restore()
    text(cv, n.capitalize(), cx + 150, cy + 300, 28, SUB, center=True)

# ---------------- poses
text(cv, "Basic poses", 1420, 1320, 40, bold=True)
poses = [
    ("Wave", 0.35, dict(face="happy", arm_l=((2.2, 0.3), (2.9, 0.2)), hand_l="open", roll=0.05)),
    ("Walk", math.pi / 2, dict(face="neutral", arm_r=((0.05, 0.45), (0.05, 0.75)), arm_l=((0.05, -0.4), (0.05, -0.15)),
                               leg_r=(0.0, 0.42, 0.1), leg_l=(0.0, -0.35, -0.75))),
    ("Thinking", 0.45, dict(face="thinking", arm_l=((0.1, 0.8), (0.75, 2.5)), arm_r=((0.1, 0.45), (-1.2, 0.3)), roll=-0.06)),
    ("Point", 0.5, dict(face="talking", arm_l=((1.25, 0.6), (1.25, 0.75)), hand_l="open")),
]
for i, (n, a, pz) in enumerate(poses):
    cx = 1440 + i * 435
    card(cv, cx, 1350, 410, 665)
    draw_character(cv, cx + 205, 1945, a, 0.66, pz)
    text(cv, n, cx + 205, 1995, 28, SUB, center=True)

os.makedirs("output", exist_ok=True)
surf.makeImageSnapshot().save("output/model_sheet_home.png")
print("saved")
