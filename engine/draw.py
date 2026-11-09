"""Skia drawing helpers: colours, paths, tapered limbs, soft glows."""
import math
import skia

def hexc(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return skia.Color(r, g, b, int(a * 255))

def mix(c1, c2, t):
    """Mix two hex colours -> hex."""
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))

def paint(color, alpha=1.0, stroke=0.0, aa=True, blur=0.0, blend=None):
    p = skia.Paint(AntiAlias=aa)
    p.setColor(hexc(color, alpha) if isinstance(color, str) else color)
    if stroke > 0:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend is not None:
        p.setBlendMode(blend)
    return p

def poly(points, close=True):
    p = skia.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p

def smooth_path(points, close=True, tension=0.5):
    """Catmull-Rom spline through points -> cubic path."""
    n = len(points)
    p = skia.Path()
    if n < 3:
        return poly(points, close)
    p.moveTo(*points[0])
    rng = range(n) if close else range(n - 1)
    for i in rng:
        p0 = points[(i - 1) % n] if (close or i > 0) else points[i]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n] if (close or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        p.cubicTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    if close:
        p.close()
    return p

def ellipse(cx, cy, rx, ry):
    p = skia.Path()
    p.addOval(skia.Rect(cx - rx, cy - ry, cx + rx, cy + ry))
    return p

def capsule(a, b, r1, r2):
    """Tapered limb between points a,b with radii r1,r2."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    d = math.hypot(dx, dy) or 1e-3
    ang = math.atan2(dy, dx)
    # angle offset of tangent points
    s = (r1 - r2) / d
    s = max(-0.99, min(0.99, s))
    phi = math.acos(s)
    p = skia.Path()
    pts = []
    N = 10
    for i in range(N + 1):
        th = ang + phi + (2 * math.pi - 2 * phi) * i / N
        pts.append((ax + r1 * math.cos(th), ay + r1 * math.sin(th)))
    for i in range(N + 1):
        th = ang - phi + (2 * phi) * i / N
        pts.append((bx + r2 * math.cos(th), by + r2 * math.sin(th)))
    return poly(pts)

def union(*paths):
    out = paths[0]
    for q in paths[1:]:
        r = skia.Op(out, q, skia.PathOp.kUnion_PathOp)
        if r is not None:
            out = r
    return out

def intersect(a, b):
    r = skia.Op(a, b, skia.PathOp.kIntersect_PathOp)
    return r if r is not None else skia.Path()

def difference(a, b):
    r = skia.Op(a, b, skia.PathOp.kDifference_PathOp)
    return r if r is not None else a

def shifted(path, dx, dy):
    q = skia.Path(path)
    q.offset(dx, dy)
    return q

def cel(canvas, path, base, shade, light=(1.0, -0.6), depth=6.0, rim=None, rim_dir=(-1, 0),
        rim_w=3.0, line=None, line_w=2.4, hi=None, hi_w=0.0):
    """Fill a shape with cel shading: shadow on side away from light, optional rim
    light, optional outline."""
    canvas.save()
    canvas.clipPath(path, skia.ClipOp.kIntersect, True)
    canvas.drawPath(path, paint(shade))
    lx, ly = light
    canvas.drawPath(shifted(path, lx * depth, ly * depth), paint(base))
    if hi is not None and hi_w > 0:
        q = difference(path, shifted(path, lx * hi_w * -1, ly * hi_w * -1))
        canvas.drawPath(q, paint(hi, 0.55))
    if rim is not None:
        q = difference(path, shifted(path, -rim_dir[0] * rim_w, -rim_dir[1] * rim_w))
        canvas.drawPath(q, paint(rim, 0.85, blur=0.6))
    canvas.restore()
    if line is not None:
        canvas.drawPath(path, paint(line, 1.0, stroke=line_w))

def glow(canvas, x, y, r, color, alpha=0.6):
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeRadial(
        (x, y), r, [hexc(color, alpha), hexc(color, alpha * 0.35), hexc(color, 0.0)], [0.0, 0.35, 1.0]))
    p.setBlendMode(skia.BlendMode.kPlus)
    canvas.drawCircle(x, y, r, p)

def lin_grad(p0, p1, colors, stops=None):
    p = skia.Paint(AntiAlias=True)
    p.setShader(skia.GradientShader.MakeLinear([p0, p1], [hexc(c) if isinstance(c, str) else c for c in colors], stops))
    return p
