"""Caption styles (9:16): premium 3D banner with animated shine + normal subtitle pill."""
import os, sys, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = Image.open(os.path.join(ROOT, "assets/caption_purple.png")).convert("RGB")
FB = "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf"
FT = "/usr/share/fonts/truetype/noto/NotoSerifBengali-Bold.ttf"
GOLD = (255, 205, 80)

def _font(p, s): return ImageFont.truetype(p, s, layout_engine=ImageFont.Layout.RAQM)

def _vgrad(w, h, stops):
    ys = np.linspace(0, 1, h)[:, None]
    out = np.zeros((h, 1, 3))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (ys >= p0) & (ys <= p1)
        u = np.clip((ys - p0) / max(p1 - p0, 1e-6), 0, 1)
        out = np.where(m[..., None], np.array(c0) + (np.array(c1) - np.array(c0)) * u[..., None], out)
    return Image.fromarray(np.repeat(out, w, 1).astype(np.uint8))

def premium_banner(img, y, lines, size=66, shine=None):
    """Full-width bevelled banner. shine: 0..1 sweep position (None = off)."""
    W = img.width
    f = _font(FT, size)
    lh = int(size * 1.32)
    h = lh * len(lines) + 46
    # drop shadow (soft, two layers)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    d.rectangle((0, y + 10, W, y + h + 18), fill=(8, 0, 24, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle((0, y + h - 2, W, y + h + 6), fill=(5, 0, 15, 170))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(3)))
    # band: texture + bevel (light top edge, dark bottom), slight inner vignette
    band = TEX.resize((W, h)).convert("RGBA")
    bevel = _vgrad(W, h, [(0, (150, 110, 255)), (0.06, (60, 30, 140)), (0.5, (0, 0, 0)), (0.92, (0, 0, 0)), (1.0, (0, 0, 0))])
    band = Image.blend(band, Image.composite(bevel.convert("RGBA"), band, Image.new("L", (W, h), 90)), 1.0)
    top = Image.new("RGBA", (W, 3), (190, 160, 255, 200)); band.alpha_composite(top, (0, 0))
    dark = _vgrad(W, 18, [(0, (0, 0, 0)), (1, (0, 0, 0))]).convert("RGBA"); dark.putalpha(_vgrad(W, 18, [(0, (0, 0, 0)), (1, (140, 140, 140))]).convert("L"))
    band.alpha_composite(dark, (0, h - 18))
    img.alpha_composite(band, (0, y))
    # text mask
    mask = Image.new("L", img.size, 0); md = ImageDraw.Draw(mask)
    for i, t in enumerate(lines):
        md.text((W // 2, y + 23 + lh * i + lh // 2), t, font=f, anchor="mm", fill=255)
    # text depth: hard extrude + soft shadow
    for dy, col, blur in ((7, (14, 4, 40, 230), 6), (3, (40, 14, 90, 255), 0)):
        l = Image.new("RGBA", img.size, col); a = ImageChops.offset(mask, 0, dy)
        if blur: a = a.filter(ImageFilter.GaussianBlur(blur))
        l.putalpha(a); img.alpha_composite(l)
    # gold gradient fill
    gold = _vgrad(W, img.height, [(0, (255, 236, 160)), (1, (255, 236, 160))]).convert("RGBA")
    ty0, ty1 = y + 23, y + 23 + lh * len(lines)
    g = _vgrad(W, ty1 - ty0, [(0, (255, 240, 175)), (0.5, (250, 206, 92)), (1, (214, 150, 40))]).convert("RGBA")
    gold.paste(g, (0, ty0))
    gold.putalpha(mask); img.alpha_composite(gold)
    # shine sweep: diagonal soft band, masked to text (+ faint on banner)
    if shine is not None:
        sx = int(-300 + (W + 600) * shine)
        s = Image.new("L", img.size, 0); ImageDraw.Draw(s).polygon([(sx, y - 20), (sx + 90, y - 20), (sx - 60, y + h + 20), (sx - 150, y + h + 20)], fill=255)
        s = s.filter(ImageFilter.GaussianBlur(22))
        white = Image.new("RGBA", img.size, (255, 255, 240, 255))
        white.putalpha(ImageChops.multiply(s, mask)); img.alpha_composite(white)
        bandm = Image.new("L", img.size, 0); ImageDraw.Draw(bandm).rectangle((0, y, W, y + h), fill=50)
        white.putalpha(ImageChops.multiply(s, bandm)); img.alpha_composite(white)
    return h

def subtitle(img, cx, y, parts, size=50):
    """parts: [(text, highlight)] - dark purple pill, gold keyword, soft shadow."""
    d = ImageDraw.Draw(img); f = _font(FB, size)
    widths = [d.textlength(t, font=f) for t, _ in parts]
    w, h = int(sum(widths)) + 64, size + 44
    x0 = int(cx - w / 2)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y + 8, x0 + w, y + h + 8), h // 2, fill=(8, 0, 24, 160))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    fill = TEX.resize((w, h)).convert("RGBA")
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=232)
    fill.putalpha(m); img.alpha_composite(fill, (x0, y))
    x = x0 + 32
    for (t, hl), tw in zip(parts, widths):
        d.text((x + 2, y + h // 2 + 3), t, font=f, fill=(10, 0, 30), anchor="lm")
        d.text((x, y + h // 2), t, font=f, fill=GOLD if hl else (255, 255, 255), anchor="lm"); x += tw

def _bg(path):
    bg = Image.open(path).convert("RGB"); W, H = 1080, 1920
    s = H / bg.height; bg = bg.resize((int(bg.width * s), H))
    off = int(bg.width * 0.56 - W / 2)
    return bg.crop((off, 0, off + W, H)).convert("RGBA")

if __name__ == "__main__":
    base = _bg(sys.argv[1])
    TITLE = ["মানিব্যাগটা পেয়েই যে থমকে গেল,", "আজ সে কী করবে?"]
    def frame(sh):
        im = base.copy()
        premium_banner(im, 300, TITLE, shine=sh)
        subtitle(im, 540, 1600, [("আরে! এখানে ", False), ("মানিব্যাগটা", True), (" কার?", False)])
        return im
    out = os.path.join(ROOT, "output")
    frame(0.42).convert("RGB").save(f"{out}/caption_style_purple.png")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x1920", "-r", "30", "-i", "-",
                          "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", f"{out}/caption_shine_preview.mp4"], stdin=subprocess.PIPE)
    for i in range(90):
        u = (i % 45) / 45 * 1.6  # sweep then pause
        p.stdin.write(frame(u if u <= 1 else None).convert("RGB").tobytes())
    p.stdin.close(); p.wait(); print("saved")
