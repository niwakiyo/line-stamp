"""set05 の文字の部品: 書体、1文字ずつの描画(フチ・影)、吹き出しや札などの枠、出し方の動き。

文字は1文字ずつ画像にして、コマごとに位置・大きさ・回転・見える/見えないを変えて置く。
枠や図形は3倍の大きさで描いて縮める(線をなめらかにする)。
1コマ目(i=0)は「できあがり」の形にする(一覧で見える絵)。
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FD = ROOT / "assets/fonts"
FONTS = dict(
    dela="DelaGothicOne-Regular.ttf", dot="DotGothic16-Regular.ttf", hachi="HachiMaruPop-Regular.ttf",
    kaisei="KaiseiDecol-Bold.ttf", kiwi="KiwiMaru-Medium.ttf", klee="KleeOne-SemiBold.ttf",
    mplus="MPLUSRounded1c-ExtraBold.ttf", mochiy="MochiyPopOne-Regular.ttf", rampart="RampartOne-Regular.ttf",
    reggae="ReggaeOne-Regular.ttf", rock="RocknRollOne-Regular.ttf", stick="Stick-Regular.ttf",
    train="TrainOne-Regular.ttf", yomogi="Yomogi-Regular.ttf", yusei="YuseiMagic-Regular.ttf",
    zenkaku="ZenKakuGothicNew-Black.ttf", kure="ZenKurenaido-Regular.ttf", zenmaru="ZenMaruGothic-Black.ttf",
)
CW, CH = 320, 270
INK = "#4A3428"
RED, RED_D, GREEN, GREEN_D, GOLD, NAVY, WHITE = "#E5483F", "#B8322B", "#2F7D5A", "#245F45", "#E8A92B", "#2B3A67", "#FFFFFF"


# ---- 時間 ----------------------------------------------------------------------------

def T(i):
    """コマ i の「出し方の時間」。1コマ目はできあがり(とても大きな時間)。"""
    return 1000 if i == 0 else i


def prog(i, a, b):
    """時間 a から b の間で 0→1(i=0 は 1)。"""
    t = T(i)
    if b <= a:
        return 1.0 if t >= a else 0.0
    return max(0.0, min(1.0, (t - a) / (b - a)))


def eo(u):  # だんだんゆっくり止まる
    return 1 - (1 - u) ** 3


def back(u, s=1.8):  # 少し行きすぎてから戻る
    u = max(0.0, min(1.0, u))
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def bounce(u):  # 着地して小さく2回はねる
    u = max(0.0, min(1.0, u))
    if u < 0.6:
        return (u / 0.6) ** 2
    if u < 0.85:
        v = (u - 0.725) / 0.125
        return 1 - 0.12 * (1 - v * v)
    v = (u - 0.925) / 0.075
    return 1 - 0.04 * (1 - v * v)


# ---- 文字 ----------------------------------------------------------------------------

_F, _G = {}, {}


def font(name, size):
    k = (name, int(round(size)))
    if k not in _F:
        _F[k] = ImageFont.truetype(str(FD / FONTS[name]), k[1])
    return _F[k]


def glyph(ch, name, size, fill, ow=0, ofill=WHITE, rw=0, rfill=INK, sh=0, shfill=None, thick=0):
    """1文字の画像(真ん中に文字)。下から: 影 → こいフチ(rw) → 白いフチ(ow) → 文字。層を分けて重ねる。"""
    key = (ch, name, int(round(size)), fill, ow, ofill, rw, rfill, sh, shfill, thick)
    if key in _G:
        return _G[key]
    f = font(name, size)
    pad = int(ow + rw + sh + thick + 8)
    W = int(size * 1.6) + 2 * pad
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    c = (W / 2, W / 2)

    def lay(fl, sw, sf, off=(0, 0)):
        g = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        sw = int(round(sw))
        ImageDraw.Draw(g).text((c[0] + off[0], c[1] + off[1]), ch, font=f, anchor="mm", fill=fl,
                               stroke_width=sw, stroke_fill=sf if sw else None)
        im.alpha_composite(g)
    if sh:
        lay(shfill or rfill, ow + rw + thick, shfill or rfill, (sh, sh))
    if rw:
        lay(rfill, ow + rw + thick, rfill)
    if ow:
        lay(ofill, ow + thick, ofill)
    lay(fill, thick, fill)
    _G[key] = im
    return im


def comp(layer, im, x, y):
    """はみ出してもよい重ね方(左上 x, y)。"""
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(im.width, CW - x), min(im.height, CH - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    layer.alpha_composite(im.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))


def put(layer, im, cx, cy, s=1.0, rot=0.0, sx=1.0, sy=1.0):
    w, h = im.width * s * sx, im.height * s * sy
    if w < 2 or h < 2:
        return
    if abs(w - im.width) > 0.5 or abs(h - im.height) > 0.5:
        im = im.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
    if abs(rot) > 0.05:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    comp(layer, im, cx - im.width / 2, cy - im.height / 2)


def line(text, name, size, x, y, align="l", sp=1.0, sizes=None):
    """1行の文字の置き場所(文字ごとの中心)。sizes で文字ごとに大きさを変えられる。"""
    sz = [sizes[j] if sizes else size for j in range(len(text))]
    adv = [font(name, sz[j]).getlength(ch) * sp for j, ch in enumerate(text)]
    total = sum(adv)
    x0 = x if align == "l" else (x - total / 2 if align == "c" else x - total)
    out = []
    for j, ch in enumerate(text):
        out.append(dict(ch=ch, x=x0 + adv[j] / 2, y=y, s=sz[j], j=j, w=adv[j]))
        x0 += adv[j]
    return out


def width(chars):
    return sum(c["w"] for c in chars)


def draw(layer, chars, name, style, fx=None):
    """chars を描く。style: glyph のオプション(dict か、文字ごとの関数)。
    fx(c) → None(見せない) か (dx, dy, 大きさ, 回転[, 横の伸び, 縦の伸び])。"""
    for c in chars:
        if c["ch"] == " ":
            continue
        r = fx(c) if fx else (0, 0, 1, 0)
        if r is None:
            continue
        dx, dy, s, rot = r[:4]
        sx, sy = (r[4], r[5]) if len(r) > 5 else (1, 1)
        st = style(c) if callable(style) else style
        put(layer, glyph(c["ch"], name, c["s"], **st), c["x"] + dx, c["y"] + dy, s, rot, sx, sy)


def clip(layer, box):
    """layer の box の外を消す。"""
    m = Image.new("L", layer.size, 0)
    x0, y0, x1, y1 = box
    if x1 > x0 and y1 > y0:
        ImageDraw.Draw(m).rectangle((x0, y0, x1, y1), fill=255)
    a = layer.getchannel("A")
    from PIL import ImageChops
    layer.putalpha(ImageChops.multiply(a, m))
    return layer


def new():
    return Image.new("RGBA", (CW, CH), (0, 0, 0, 0))


# ---- 図形(3倍で描く) ----------------------------------------------------------------

K = 3


def vec(layer, fn):
    big = Image.new("RGBA", (CW * K, CH * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    fn(d)
    layer.alpha_composite(big.resize((CW, CH), Image.LANCZOS))


def P(*v):
    if len(v) == 1:
        v = v[0]
    out = []
    for e in v:
        if isinstance(e, (tuple, list)):
            out.append((e[0] * K, e[1] * K))
        else:
            out.append(e * K)
    return out


def rrect(d, box, r, fill, outline=INK, w=2.5):
    x0, y0, x1, y1 = box
    if x1 - x0 < 1 or y1 - y0 < 1:
        return
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    d.rounded_rectangle(P(box), radius=r * K, fill=fill, outline=outline, width=round(w * K) if outline else 0)


def poly(d, pts, fill, outline=INK, w=2.5):
    d.polygon(P(pts), fill=fill)
    if outline:
        d.line(P(list(pts) + [pts[0]]), fill=outline, width=round(w * K), joint="curve")


def ell(d, box, fill, outline=INK, w=2.5):
    d.ellipse(P(box), fill=fill, outline=outline, width=round(w * K) if outline else 0)


def seg(d, pts, fill, w):
    d.line(P(pts), fill=fill, width=round(w * K), joint="curve")


def spiky(cx, cy, rx, ry, n=16, amp=8, ph=0.0, jit=0.0):
    pts = []
    for k in range(n * 2):
        a = k / (n * 2) * 2 * math.pi + ph
        out = k % 2 == 0
        r = 1.0 if out else 1.0 - amp / max(rx, ry) * 2
        jj = 1 + (jit * math.sin(k * 2.7) if out else 0)
        pts.append((cx + rx * r * jj * math.cos(a), cy + ry * r * jj * math.sin(a)))
    return pts


def cloud(d, cx, cy, rx, ry, fill, outline=INK, w=2.5, n=11, bump=0.32):
    """もこもこの雲(まるいふくらみを輪に並べる)。"""
    circles = []
    for k in range(n):
        a = k / n * 2 * math.pi
        r = min(rx, ry) * bump * (1 + 0.15 * math.sin(k * 1.9))
        circles.append((cx + (rx - r * 0.6) * math.cos(a), cy + (ry - r * 0.6) * math.sin(a), r))
    for x, y, r in circles:
        d.ellipse(P(x - r - w, y - r - w, x + r + w, y + r + w), fill=outline)
    d.ellipse(P(cx - rx + w, cy - ry + w, cx + rx - w, cy + ry - w), fill=outline)
    for x, y, r in circles:
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=fill)
    d.ellipse(P(cx - rx + 2 * w, cy - ry + 2 * w, cx + rx - 2 * w, cy + ry - 2 * w), fill=fill)


def star(cx, cy, r1, r2, n=5, ph=-math.pi / 2):
    return [(cx + (r1 if k % 2 == 0 else r2) * math.cos(ph + k * math.pi / n),
             cy + (r1 if k % 2 == 0 else r2) * math.sin(ph + k * math.pi / n)) for k in range(n * 2)]


def sparkle(d, cx, cy, r, fill="#FFD84D"):
    pts = [(cx + (r if k % 2 == 0 else r * 0.3) * math.cos(-math.pi / 2 + k * math.pi / 4),
            cy + (r if k % 2 == 0 else r * 0.3) * math.sin(-math.pi / 2 + k * math.pi / 4)) for k in range(8)]
    poly(d, pts, fill, INK, 1.6)


def impact(d, cx, cy, r0, r1, n=10, col=INK, w=2.5, ph=0.0):
    for k in range(n):
        a = k / n * 2 * math.pi + ph
        seg(d, [(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], col, w)
