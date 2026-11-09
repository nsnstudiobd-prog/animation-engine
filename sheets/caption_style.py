"""Caption style preview (9:16): premium title tag + normal subtitle, purple theme."""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = Image.open(os.path.join(ROOT, "assets/caption_purple.png")).convert("RGB")
FB = "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf"
FR = "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf"
GOLD, CREAM = (255, 205, 80), (255, 248, 235)

def _font(p, s): return ImageFont.truetype(p, s, layout_engine=ImageFont.Layout.RAQM)

def _box(img, xy, r, shadow=True, alpha=255):
    x0, y0, x1, y1 = xy
    w, h = x1 - x0, y1 - y0
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((x0 + 4, y0 + 10, x1 + 4, y1 + 10), r, fill=(10, 0, 30, 140))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    fill = TEX.resize((max(w, 1), max(h, 1))).convert("RGBA")
    fill.putalpha(alpha)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); layer.paste(fill, (x0, y0), m)
    img.alpha_composite(layer)

def premium_tag(img, cx, y, text, size=64):
    d = ImageDraw.Draw(img); f = _font(FB, size)
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    w, h = r - l + 90, b - t + 60
    x0 = cx - w // 2
    _box(img, (x0, y, x0 + w, y + h), 14)
    d.rounded_rectangle((x0 + 9, y + 9, x0 + w - 9, y + h - 9), 9, outline=(255, 255, 255, 170), width=3)   # white inset line
    d.polygon([(x0 + 26, y + h - 2), (x0 + 46, y + h - 2), (x0 + 46, y + h + 30), (x0 + 36, y + h + 20), (x0 + 26, y + h + 30)], fill=GOLD)  # ribbon
    d.text((cx, y + h // 2), text, font=f, fill=CREAM, anchor="mm")

def subtitle(img, cx, y, parts, size=50):
    """parts: [(text, highlight_bool)]"""
    d = ImageDraw.Draw(img); f = _font(FB, size)
    widths = [d.textlength(t, font=f) for t, _ in parts]
    w, h = int(sum(widths)) + 60, size + 44
    x0 = int(cx - w / 2)
    _box(img, (x0, y, x0 + w, y + h), h // 2, alpha=235)
    x = x0 + 30
    for (t, hl), tw in zip(parts, widths):
        d.text((x, y + h // 2), t, font=f, fill=GOLD if hl else (255, 255, 255), anchor="lm"); x += tw

if __name__ == "__main__":
    bg_path = sys.argv[1]
    bg = Image.open(bg_path).convert("RGB")
    W, H = 1080, 1920
    s = H / bg.height; bg = bg.resize((int(bg.width * s), H))
    off = int(bg.width * 0.56 - W / 2)
    img = bg.crop((off, 0, off + W, H)).convert("RGBA")
    premium_tag(img, W // 2, 190, "রাফির সেই 'ধন্যবাদ'")
    premium_tag(img, W // 2, 420, "সেদিন সন্ধ্যায়", size=46)
    subtitle(img, W // 2, 1560, [("আরে! এখানে ", False), ("মানিব্যাগটা", True), (" কার?", False)])
    subtitle(img, W // 2, 1690, [("রাফি দেখছে...", False)], size=44)
    img.convert("RGB").save(os.path.join(ROOT, "output/caption_style_purple.png"))
    print("saved")
