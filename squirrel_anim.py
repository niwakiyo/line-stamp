"""秋のリスの動くスタンプ。

画像の上に縁取り文字のセリフ、下にドット絵のリス。セリフは 1 個につき 3 段階で切り替わる。
リスは 80x55 ドットのキャンバスにパーツ (しっぽ・胴・頭・腕・マフラー) を組み立てて描き、4 倍に拡大する。
顔を崩さないように回転や拡大縮小はせず、頭や胴の位置をずらして動きをつける。

    python3 squirrel_anim.py   # → output_squirrel/ と squirrel_anim_stamp.zip
"""
import argparse
import json
import math
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import anim_stamps as an
import pixel_stamps as ps
from make_stamps import MAIN_SIZE, TAB_SIZE

GW, GH, K = 80, 55, 4        # キャラのキャンバス (ドット) と拡大率
TOP = 270 - GH * K           # キャラのキャンバスを置く高さ (上は文字の場所)
GROUND = 53
SCENE_MS = (1300, 1300, 1400)  # セリフ 3 段階の表示時間 (合計 4 秒・1 回再生)

INK = "#4A2410"      # 輪郭
FUR = "#D9822B"
FUR_D = "#A0521A"
TAIL = "#E39A4A"
CREAM = "#F6DDB0"
PINK = "#E8909A"
BLUSH = "#F07A7A"
EYE = "#2A160A"
RED = "#D6332A"
ORANGE = "#F08A1E"
TEAR = "#5AA8E8"

PATTERNS = {
    "acorn": (["..ddd..", ".dDdDd.", "dDdDdDd", "ccccccc", ".bbbbb.", ".bhbbb.", ".bhbbb.", "..bbb..", "...b..."],
              {"d": "#7A4A22", "D": "#9A6532", "c": "#5E3416", "b": "#B8662A", "h": "#E8A868"}),
    "potato": (["..pppppp..", ".pPpppppy.", "ppppppyyyy", ".pppppyyy.", "..ppppp..."],
               {"p": "#8A3A6E", "P": "#B4609A", "y": "#F2C230"}),
    "chestnut": (["...k...", "..kkk..", ".kkhkk.", "kkhkkkk", "kkkkkkk", "ccccccc", ".ccccc."],
                 {"k": "#7A3A16", "h": "#C07040", "c": "#F0D29A"}),
    "maple": (["..X..", "X.X.X", "XXXXX", ".XXX.", "..X.."], {}),
    "ginkgo": (["XXXXX", "XXXXX", ".XXX.", "..X.."], {}),
    "leaf": (["..XX", ".XXX", "XXX.", "X..."], {}),
    "mush": ([".rrr.", "rwrrr", "rrrwr", ".ccc.", ".ccc."], {"r": "#C8402A", "w": "#FFF4E0", "c": "#F0DCC0"}),
    "heart": ([".X.X.", "XXXXX", "XXXXX", ".XXX.", "..X.."], {"X": "#F0506E"}),
    "spark": (["..X..", ".XXX.", "XXXXX", ".XXX.", "..X.."], {"X": "#FFD84A"}),
    "dot": ([".X.", "XXX", ".X."], {"X": "#FFD84A"}),
    "note": ([".XXX", ".X.X", ".X.X", "XX.X", "XX.."], {"X": "#C8402A"}),
    "drop": ([".X.", "XXX", "XXX"], {"X": TEAR}),
    "sweat": (["X.", "XX", "XX"], {"X": TEAR}),
    "z": (["XXX", "..X", ".X.", "X..", "XXX"], {"X": "#6A7AD0"}),
    "steam": (["X.", ".X", "X.", ".X", "X."], {"X": "#C8BEB4"}),
    "stick": (["X", "X", "X", "X", "X", "X"], {"X": "#FFD84A"}),
    "cup": (["wwwww.", "cccccX", "cccc.X", "cccccX", ".ccc.."], {"w": "#FFF4E0", "c": "#C8402A", "X": "#C8402A"}),
    "pile": (["...a...", "..aaa..", ".aaaaa.", "aaaaaaa"], {"a": "#9A5A26"}),
}
LEAF_COLORS = ["#D6332A", "#F08A1E", "#F2C230", "#B8401E"]


# --- ポーズ ------------------------------------------------------------------
BASE = dict(x=0, y=0, lean=0, hx=0, hy=0, bw=0, bh=0, la=(-5, 0), ra=(5, 0), fl=0, fr=0,
            tail=0, tside=1, tsize=1.0, expr="normal", mouth="w", cheek=0, ears=0, wind=0,
            item=None, fx=(), flip=False)


def P(**kw):
    p = dict(BASE)
    p.update(kw)
    return p


def hold(item, **kw):
    """両手で胸の前に持つ。"""
    kw.setdefault("la", (-4, 0))
    kw.setdefault("ra", (4, 0))
    return P(item=(item, "hands", 1 if item == "acorn" else 2), **kw)


def lift(item, **kw):
    """右手で高く持ち上げる。"""
    kw.setdefault("ra", (8, -12))
    return P(item=(item, "r", 1 if item == "acorn" else 2), **kw)


def leaves(seed, n=6, dy=0, area=(2, 2, 78, 40)):
    out = []
    for i in range(n):
        x = area[0] + (seed * 17 + i * 23) % (area[2] - area[0])
        y = area[1] + (seed * 7 + i * 13 + dy) % (area[3] - area[1])
        if 22 < x < 60 and y < 46:  # 顔や体にかぶらないよう左右へよける
            x = x - 20 if x < 41 else x + 20
        out.append(("maple" if i % 3 else "ginkgo" if i % 2 else "leaf", x, y, LEAF_COLORS[(i + seed) % 4]))
    return out


def fall(i, n=6):
    """落ち葉がひらひら降る (コマ i)。"""
    return leaves(1, n, dy=i * 4, area=(2, 0, 78, 46))


def burst(r, n=8, cx=40, cy=24):
    return [("maple" if i % 2 else "ginkgo", round(cx + math.cos(i * 6.283 / n) * r * 1.4),
             round(cy + math.sin(i * 6.283 / n) * r), LEAF_COLORS[i % 4]) for i in range(n)]


def fx(kind, x, y, color=None, s=1):
    return (kind, x, y, color, s)


# --- 描画 --------------------------------------------------------------------
def pattern_image(kind, color=None, s=1, ink=INK):
    rows, colors = PATTERNS[kind]
    w, h = len(rows[0]), len(rows)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != ".":
                img.putpixel((x, y), ps.rgba(colors.get(c, color or "#D6332A")))
    if s > 1:
        img = ps.scaled(img, s)
    return img if kind == "steam" else outlined(img, ink)


def outlined(img, ink):
    pad = Image.new("RGBA", (img.width + 2, img.height + 2), (0, 0, 0, 0))
    pad.alpha_composite(img, (1, 1))
    mask = pad.getchannel("A").point(lambda v: 255 if v else 0).filter(ImageFilter.MaxFilter(3))
    out = Image.new("RGBA", pad.size, (0, 0, 0, 0))
    out.paste(Image.new("RGBA", pad.size, ps.rgba(ink)), (0, 0), mask)
    out.alpha_composite(pad)
    return out


def put(img, kind, cx, cy, color=None, s=1):
    pi = pattern_image(kind, color, s, ink=INK)
    img.alpha_composite(pi, (round(cx - pi.width / 2), round(cy - pi.height / 2)))


def oval(d, cx, cy, rx, ry, fill, ink=INK):
    d.ellipse((round(cx - rx), round(cy - ry), round(cx + rx), round(cy + ry)), fill=fill, outline=ink)


TAIL_PATH = [(0, 0, 4), (6, -2, 5), (11, -8, 6), (13, -16, 6), (11, -23, 6), (6, -26, 5),
             (2, -24, 4), (2, -20, 3), (5, -19, 2)]


def tail_points(p, bx, by):
    pts = []
    a = math.radians(p["tail"])
    for i in range(len(TAIL_PATH) - 1):
        (x0, y0, r0), (x1, y1, r1) = TAIL_PATH[i], TAIL_PATH[i + 1]
        for t in (0, 0.25, 0.5, 0.75):
            x, y, r = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t
            x, y = x * p["tsize"], y * p["tsize"]
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            pts.append((bx + x * p["tside"], by + y, r * p["tsize"]))
    return pts


def draw_tail(d, p, bx, by):
    pts = tail_points(p, bx, by)
    for x, y, r in pts:
        oval(d, x, y, r + 1, r + 1, INK, INK)
    for x, y, r in pts:
        oval(d, x, y, r, r, TAIL, TAIL)
    for x, y, r in pts[2:-3]:
        oval(d, x, y, r * 0.35, r * 0.35, FUR_D, FUR_D)


def draw_eyes(d, p, hcx, hcy):
    e = p["expr"]
    for side, ex in ((-1, hcx - 5), (1, hcx + 4)):
        ey = hcy - 1
        kind = e
        if e == "wink":
            kind = "normal" if side < 0 else "happy"
        if kind in ("normal", "teary"):
            d.rectangle((ex, ey, ex + 1, ey + 2), fill=EYE)
            d.point((ex, ey), fill="#FFFFFF")
            if kind == "teary":
                d.line((ex - 1, ey + 3, ex + 2, ey + 3), fill=TEAR)
        elif kind == "sparkle":
            d.rectangle((ex - 1, ey - 1, ex + 2, ey + 2), fill=EYE)
            d.point((ex, ey), fill="#FFFFFF")
            d.point((ex + 1, ey + 1), fill="#FFFFFF")
        elif kind == "happy":
            d.line((ex - 1, ey + 2, ex, ey + 1), fill=EYE)
            d.line((ex + 1, ey + 1, ex + 2, ey + 2), fill=EYE)
        elif kind in ("closed", "sleep"):
            d.line((ex - 1, ey + 1, ex + 2, ey + 1), fill=EYE)
        elif kind == "cry":
            d.line((ex - 1, ey, ex + 2, ey + 1) if side < 0 else (ex - 1, ey + 1, ex + 2, ey), fill=EYE)
            d.line((ex - 1, ey + 2, ex + 2, ey + 1) if side < 0 else (ex - 1, ey + 1, ex + 2, ey + 2), fill=EYE)
            d.line((ex, ey + 3, ex, ey + 7), fill=TEAR, width=2)
        elif kind == "wide":
            d.rectangle((ex - 1, ey - 1, ex + 2, ey + 2), fill="#FFFFFF", outline=EYE)
            d.point((ex, ey + 1), fill=EYE)
            d.point((ex + 1, ey + 1), fill=EYE)
        elif kind == "heart":
            d.point((ex - 1, ey), fill="#F0506E")
            d.point((ex + 2, ey), fill="#F0506E")
            d.line((ex - 1, ey + 1, ex + 2, ey + 1), fill="#F0506E")
            d.line((ex, ey + 2, ex + 1, ey + 2), fill="#F0506E")


def draw_mouth(d, p, mx, my):
    m = p["mouth"]
    if m == "w":
        d.point((mx - 1, my), fill=EYE)
        d.point((mx, my + 1), fill=EYE)
        d.point((mx + 1, my), fill=EYE)
    elif m == "open":
        d.rectangle((mx - 1, my, mx + 1, my + 2), fill="#8A2A20")
        d.point((mx, my + 2), fill="#F07A7A")
    elif m == "big":
        d.rectangle((mx - 2, my, mx + 2, my + 3), fill="#8A2A20")
        d.line((mx - 1, my + 3, mx + 1, my + 3), fill="#F07A7A")
    elif m == "o":
        d.rectangle((mx - 1, my, mx, my + 1), fill="#8A2A20")
    elif m == "wavy":
        d.line((mx - 2, my + 1, mx - 1, my), fill=EYE)
        d.line((mx, my + 1, mx + 1, my), fill=EYE)
    elif m == "munch":
        d.line((mx - 2, my + 1, mx + 2, my + 1), fill=EYE)
        d.point((mx - 1, my), fill=EYE)
        d.point((mx + 1, my + 2), fill=EYE)
    elif m == "sad":
        d.line((mx - 1, my + 1, mx + 1, my + 1), fill=EYE)
        d.point((mx - 2, my + 2), fill=EYE)
        d.point((mx + 2, my + 2), fill=EYE)


def draw_arm(d, sx, sy, px, py):
    d.line((sx, sy, px, py), fill=INK, width=5)
    d.line((sx, sy, px, py), fill=FUR, width=3)


def render_grid(p):
    img = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gy = GROUND - p["y"]
    cx = 40 + p["x"]
    rx, ry = 8 + p["bw"], 8 + p["bh"]
    bcx, bcy = cx + p["lean"] // 2, gy - 2 - ry
    hcx, hcy = cx + p["lean"] + p["hx"], bcy - ry - 5 + p["hy"]

    draw_tail(d, p, bcx + 6 * p["tside"], gy - 5)
    # 耳
    for s in (-1, 1):
        oval(d, hcx + 7 * s, hcy - 9 - p["ears"], 3, 4, FUR)
        oval(d, hcx + 7 * s, hcy - 8 - p["ears"], 1, 2, PINK, PINK)
    # 胴と足
    oval(d, bcx, bcy, rx, ry, FUR)
    oval(d, bcx, bcy + 1, rx - 3, ry - 2, CREAM, CREAM)
    oval(d, cx - 5, gy - 2 - p["fl"], 3, 2, FUR)
    oval(d, cx + 5, gy - 2 - p["fr"], 3, 2, FUR)
    # ほっぺ (ふくらむ) と頭
    if p["cheek"]:
        for s in (-1, 1):
            oval(d, hcx + 8 * s, hcy + 3, 4 + p["cheek"], 3 + p["cheek"] // 2, FUR)
    oval(d, hcx, hcy, 11, 9, FUR)
    if p["cheek"]:
        for s in (-1, 1):
            oval(d, hcx + 8 * s, hcy + 3, 3 + p["cheek"], 2 + p["cheek"] // 2, FUR, FUR)
    d.line((hcx - 1, hcy - 8, hcx - 1, hcy - 5), fill=FUR_D)
    d.line((hcx + 1, hcy - 8, hcx + 1, hcy - 5), fill=FUR_D)
    oval(d, hcx, hcy + 3, 4, 3, CREAM, CREAM)
    for s in (-1, 1):
        d.rectangle((hcx + 6 * s - 1 if s > 0 else hcx - 9, hcy + 2, hcx + 9 if s > 0 else hcx - 6, hcy + 3),
                    fill=BLUSH)
    draw_eyes(d, p, hcx, hcy)
    d.point((hcx, hcy + 1), fill=EYE)
    draw_mouth(d, p, hcx, hcy + 3)
    # マフラー
    nb = hcy + 8
    for i, x in enumerate(range(hcx - 8, hcx + 9, 2)):
        d.rectangle((x, nb, x + 1, nb + 2), fill=RED if i % 2 == 0 else ORANGE)
    d.rectangle((hcx - 9, nb - 1, hcx + 9, nb + 3), outline=INK)
    ex = hcx + 4
    w = p["wind"]
    end = [(ex, nb + 3), (ex + 3, nb + 3), (ex + 3 + w, nb + 10), (ex + w, nb + 10)]
    d.polygon(end, fill=RED, outline=INK)
    d.line((ex + w // 2, nb + 6, ex + 3 + w // 2, nb + 6), fill=ORANGE)
    # 持ち物と腕
    shl, shr = (bcx - 6, bcy - ry + 4), (bcx + 6, bcy - ry + 4)
    pl = (bcx + p["la"][0], bcy + p["la"][1])
    pr = (bcx + p["ra"][0], bcy + p["ra"][1])
    if p["item"]:
        kind, at, s = p["item"]
        if at == "hands":
            ix, iy = (pl[0] + pr[0]) / 2, (pl[1] + pr[1]) / 2 - 1
        elif at == "r":
            ix, iy = pr[0], pr[1] - 4 * s
        elif at == "l":
            ix, iy = pl[0], pl[1] - 4 * s
        else:
            ix, iy = at
        put(img, kind, ix, iy, s=s)
        d = ImageDraw.Draw(img)
    for sh, pw in ((shl, pl), (shr, pr)):
        draw_arm(d, *sh, *pw)
        oval(d, pw[0], pw[1], 2, 2, FUR)

    for kind, x, y, color, *s in [f if len(f) == 5 else (*f, 1) for f in p["fx"]]:
        put(img, kind, x, y, color, s[0] if s else 1)
    if p["flip"]:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    # 全体にシール風の白いふち
    mask = img.getchannel("A").point(lambda v: 255 if v else 0).filter(ImageFilter.MaxFilter(3))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(Image.new("RGBA", img.size, (255, 255, 255, 255)), (0, 0), mask)
    out.alpha_composite(img)
    return out


TEXT_FILL = ("#F7A23A", "#D2541A")
TEXT_INK = "#5A2408"


def text_image(text):
    font = ps.load_font()
    w = int(font.getlength(text)) + 2
    mask = Image.new("L", (w, 18), 0)
    md = ImageDraw.Draw(mask)
    for b in (0, 1):
        md.text((b, 0), text, font=font, fill=255)
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    mask = mask.crop(mask.getbbox())
    k = 2 if mask.width * 2 <= 296 else 1
    mask = mask.resize((mask.width * k, mask.height * k), Image.NEAREST)
    pad = 6
    big = Image.new("L", (mask.width + pad * 2, mask.height + pad * 2), 0)
    big.paste(mask, (pad, pad))
    ink = big.filter(ImageFilter.MaxFilter(5))
    white = ink.filter(ImageFilter.MaxFilter(5))
    img = Image.new("RGBA", big.size, (0, 0, 0, 0))
    img.paste(Image.new("RGBA", big.size, (255, 255, 255, 255)), (0, 0), white)
    img.paste(Image.new("RGBA", big.size, ps.rgba(TEXT_INK)), (0, 0), ink)
    grad = Image.new("RGBA", big.size)
    top, bot = ps.rgba(TEXT_FILL[0]), ps.rgba(TEXT_FILL[1])
    for y in range(big.height):
        t = min(1, max(0, (y - pad) / max(1, mask.height)))
        grad.paste(tuple(round(a + (b - a) * t) for a, b in zip(top, bot)), (0, y, big.width, y + 1))
    img.paste(grad, (0, 0), big)
    return img


def render(p, text, pop=False):
    canvas = Image.new("RGBA", an.ANIM_SIZE, (0, 0, 0, 0))
    canvas.alpha_composite(ps.scaled(render_grid(p), K), (0, TOP))
    t = text_image(text)
    if t.width > 318:
        raise SystemExit(f"セリフが長すぎます: {text}")
    canvas.alpha_composite(t, ((320 - t.width) // 2, max(0, (TOP - t.height) // 2 - (3 if pop else 0))))
    return canvas


# --- モーション (各 3 シーンのポーズ列) ----------------------------------------
def m_thanks():   # ありがとう! → 感謝の気持ち → どんぐり1個あげる
    a = [hold("acorn", expr="happy", tail=0), P(expr="closed", hy=6, lean=0, bh=-1, la=(-6, 2), ra=(6, 2), tail=15),
         P(expr="closed", hy=7, bh=-2, la=(-6, 3), ra=(6, 3), tail=20, fx=[fx("heart", 64, 8)]),
         hold("acorn", expr="happy", y=3, tail=-10, fx=[fx("heart", 64, 6), fx("heart", 14, 12)])]
    b = [P(expr="happy", mouth="open", la=(-9, -10), ra=(9, -10), y=6, ears=1, fx=[fx("heart", 12, 10), fx("heart", 66, 8)]),
         P(expr="happy", la=(-9, -6), ra=(9, -6), y=0, bh=-1, fx=[fx("heart", 12, 6), fx("heart", 66, 4)]),
         P(expr="happy", mouth="open", la=(-9, -10), ra=(9, -10), y=7, ears=1, fx=[fx("heart", 10, 3), fx("heart", 68, 2)]),
         P(expr="happy", la=(-4, -2), ra=(4, -2), y=0, bh=-1)]
    c = [P(item=("acorn", (52, 28), 2), ra=(12, -2), lean=3, expr="normal", mouth="open"),
         P(item=("acorn", (56, 26), 2), ra=(14, -4), lean=5, expr="sparkle", mouth="open", fx=[fx("spark", 66, 14)]),
         P(item=("acorn", (56, 26), 2), ra=(14, -4), lean=5, expr="happy", fx=[fx("spark", 68, 12), fx("dot", 46, 16)]),
         P(item=("acorn", (56, 26), 2), ra=(14, -4), lean=5, expr="wink", fx=[fx("spark", 66, 14), fx("heart", 20, 14)])]
    return a, b, c


def m_morning():  # おはよ〜 → 寒くなったね → マフラー出した
    a = [P(expr="happy", mouth="open", la=(-10, -20), ra=(10, -20), bh=2, y=2, ears=1),
         P(expr="closed", mouth="big", la=(-11, -22), ra=(11, -22), bh=3, y=3, ears=1),
         P(expr="closed", mouth="big", la=(-10, -20), ra=(10, -20), bh=2, y=2, ears=1),
         P(expr="happy", mouth="w", la=(-9, -6), ra=(9, -6))]
    b = [P(expr="closed", mouth="wavy", x=-1, la=(-3, -3), ra=(3, -3), bw=-1, fx=[fx("sweat", 58, 12)]),
         P(expr="closed", mouth="wavy", x=1, la=(-3, -3), ra=(3, -3), bw=-1, fx=[fx("sweat", 60, 14)]),
         P(expr="closed", mouth="wavy", x=-1, la=(-3, -3), ra=(3, -3), bw=-1, fx=[fx("sweat", 58, 12)]),
         P(expr="closed", mouth="wavy", x=1, la=(-3, -3), ra=(3, -3), bw=-1, fx=[fx("sweat", 60, 14)])]
    c = [P(expr="happy", wind=4, la=(-8, -12), ra=(8, -12), tail=-10),
         P(expr="happy", wind=-2, la=(-2, -12), ra=(10, -14), tail=10, y=3),
         P(expr="sparkle", mouth="open", wind=5, la=(-10, -4), ra=(10, -4), y=5, fx=[fx("spark", 14, 10), fx("spark", 66, 10)]),
         P(expr="happy", wind=2, la=(-4, -2), ra=(4, -2), fx=[fx("spark", 16, 12), fx("dot", 64, 8)])]
    return a, b, c


def m_ryo():      # りょ! → おけまる → どんぐり拾ってくる
    a = [P(expr="wink", mouth="open", ra=(9, -18), hx=-1, tail=-10),
         P(expr="wink", mouth="open", ra=(10, -20), y=6, ears=1, tail=10, fx=[fx("spark", 66, 6)]),
         P(expr="wink", mouth="w", ra=(9, -18), y=0, bh=-1, fx=[fx("spark", 66, 8)])]
    b = [P(expr="happy", mouth="open", la=(-12, -8), ra=(12, -8), y=4, fx=[fx("dot", 10, 10), fx("dot", 70, 10)]),
         P(expr="happy", mouth="open", la=(-12, -14), ra=(12, -14), y=8, ears=1, fx=[fx("spark", 10, 8), fx("spark", 70, 8)]),
         P(expr="happy", la=(-9, -4), ra=(9, -4), bh=-1)]
    c = [P(expr="sparkle", flip=True, lean=4, la=(-9, 4), ra=(10, -2), fl=3, tail=20),
         P(expr="sparkle", flip=True, x=-12, lean=5, la=(-10, -2), ra=(9, 4), fr=3, y=2, tail=25, fx=[fx("dot", 70, 40), fx("dot", 74, 44)]),
         P(expr="sparkle", flip=True, x=-24, lean=5, la=(-9, 4), ra=(10, -2), fl=3, tail=20, fx=[fx("dot", 62, 42), fx("dot", 68, 46), fx("dot", 74, 40)]),
         P(expr="happy", x=0, item=("acorn", "r", 1), ra=(9, -14), y=4, fx=[fx("spark", 66, 6)])]
    return a, b, c


def m_sorena():   # それな! → わかりみ深い → 落ち葉より深い
    a = [P(expr="sparkle", mouth="open", ra=(13, -6), lean=4, hx=1),
         P(expr="sparkle", mouth="open", ra=(15, -7), lean=6, hx=2, fx=[fx("spark", 74, 10)]),
         P(expr="sparkle", mouth="open", ra=(15, -7), lean=6, hx=2, fx=[fx("spark", 74, 10), fx("dot", 70, 4)])]
    b = [P(expr="closed", hy=5, la=(-6, -6), ra=(6, -6)), P(expr="closed", hy=0, la=(-6, -6), ra=(6, -6)),
         P(expr="closed", hy=6, la=(-6, -6), ra=(6, -6)), P(expr="happy", hy=0, la=(-6, -6), ra=(6, -6))]
    c = [P(expr="happy", mouth="open", y=8, la=(-10, -10), ra=(10, -10), fl=2, fr=2, fx=leaves(2, 4, area=(4, 40, 76, 50))),
         P(expr="happy", y=0, bh=-2, la=(-8, -4), ra=(8, -4), fx=burst(9, 8, cy=44)),
         P(expr="happy", mouth="open", y=9, la=(-10, -12), ra=(10, -12), fx=burst(13, 8, cy=40)),
         P(expr="happy", y=0, la=(-4, -2), ra=(4, -2), fx=leaves(3, 6, area=(4, 44, 76, 52)))]
    return a, b, c


def m_meroi():    # メロい… → 秋の夕焼け → メロすぎ問題
    a = [P(expr="heart", la=(-9, -14), ra=(9, -14), hx=-2, lean=-2, fx=[fx("heart", 12, 10)]),
         P(expr="heart", la=(-9, -14), ra=(9, -14), hx=2, lean=2, fx=[fx("heart", 66, 8)]),
         P(expr="heart", la=(-9, -14), ra=(9, -14), hx=-2, lean=-2, fx=[fx("heart", 12, 6), fx("heart", 66, 12)])]
    b = [P(expr="sparkle", mouth="o", la=(-11, -12), ra=(-6, -14), lean=-3, fx=[fx("spark", 64, 6), fx("dot", 70, 14)]),
         P(expr="sparkle", mouth="o", la=(-11, -12), ra=(-6, -14), lean=-3, fx=[fx("spark", 66, 8), fx("dot", 72, 4)]),
         P(expr="heart", mouth="o", la=(-9, -14), ra=(9, -14), fx=[fx("spark", 64, 6), fx("heart", 14, 8)])]
    c = [P(expr="heart", mouth="wavy", bh=-2, hy=3, la=(-10, -3), ra=(10, -3), fx=[fx("heart", 14, 10), fx("heart", 64, 6)]),
         P(expr="heart", mouth="wavy", bh=-3, bw=2, hy=6, la=(-12, 0), ra=(12, 0), fx=[fx("heart", 12, 6), fx("heart", 66, 3), fx("heart", 40, 2)]),
         P(expr="heart", mouth="wavy", bh=-4, bw=3, hy=8, la=(-13, 2), ra=(13, 2), tail=30, fx=[fx("heart", 10, 2), fx("heart", 68, 1), fx("heart", 26, 4), fx("heart", 54, 4)])]
    return a, b, c


def m_emo():      # 秋、エモすぎん? → 落ち葉ふみふみ → 焼き芋たべよ
    a = [hold("acorn", expr="sparkle", fx=fall(0) + [fx("potato", 14, 46), fx("mush", 66, 48)])]
    a += [hold("acorn", expr="sparkle", hx=s, lean=s, fx=fall(i) + [fx("potato", 14, 46), fx("mush", 66, 48)])
          for i, s in ((1, 2), (2, -2), (3, 2))]
    b = [P(expr="happy", mouth="open", fl=4, y=2, la=(-9, -6), ra=(9, -6), fx=leaves(4, 6, area=(6, 44, 74, 52))),
         P(expr="happy", fr=4, y=2, la=(-9, -6), ra=(9, -6), fx=burst(8, 6, cx=34, cy=46)),
         P(expr="happy", mouth="open", fl=4, y=2, la=(-9, -6), ra=(9, -6), fx=burst(8, 6, cx=46, cy=46)),
         P(expr="happy", fr=4, y=2, la=(-9, -6), ra=(9, -6), fx=burst(10, 8, cx=40, cy=44))]
    c = [hold("potato", expr="sparkle", mouth="open", fx=[fx("steam", 36, 16), fx("steam", 44, 14)]),
         hold("potato", expr="happy", mouth="open", y=5, fx=[fx("steam", 36, 10), fx("steam", 44, 8), fx("spark", 66, 8)]),
         hold("potato", expr="happy", mouth="munch", cheek=1, fx=[fx("steam", 36, 12), fx("steam", 44, 10), fx("heart", 66, 10)]),
         hold("potato", expr="happy", mouth="munch", cheek=2, fx=[fx("steam", 38, 14), fx("heart", 66, 6), fx("heart", 14, 10)])]
    return a, b, c


def m_yakiimo():  # 焼き芋しか勝たん → ほくほく → 秋の優勝
    a = [lift("potato", expr="sparkle", mouth="open", fx=[fx("steam", 50, 4), fx("spark", 14, 10)]),
         lift("potato", expr="sparkle", mouth="open", y=6, ra=(9, -14), fx=[fx("steam", 50, 2), fx("spark", 12, 6)]),
         lift("potato", expr="sparkle", mouth="open", fx=[fx("steam", 50, 4), fx("spark", 14, 10)])]
    b = [hold("potato", expr="happy", mouth="munch", cheek=1, fx=[fx("steam", 32, 14)]),
         hold("potato", expr="happy", mouth="munch", cheek=2, hy=1, fx=[fx("steam", 46, 12)]),
         hold("potato", expr="happy", mouth="munch", cheek=3, fx=[fx("steam", 32, 12)]),
         hold("potato", expr="happy", mouth="munch", cheek=3, hy=1, fx=[fx("steam", 46, 10), fx("heart", 66, 8)])]
    c = [P(expr="happy", mouth="big", la=(-11, -16), ra=(11, -16), y=4, fx=burst(16, 8, cy=24)),
         P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), y=10, ears=1, fx=burst(20, 10, cy=22)),
         P(expr="happy", mouth="big", la=(-11, -16), ra=(11, -16), y=3, fx=burst(22, 10, cy=26) + [fx("spark", 40, 4)]),
         P(expr="sparkle", mouth="open", la=(-11, -16), ra=(11, -16), fx=leaves(5, 8, area=(2, 2, 78, 48)))]
    return a, b, c


def m_otsukare():  # おつかれさま → 今日もえらい → 栗ごほうび
    a = [P(expr="happy", ra=(10, -16), tail=-10), P(expr="happy", ra=(13, -14), lean=2, tail=10),
         P(expr="happy", ra=(8, -18), lean=-1, tail=-10), P(expr="happy", ra=(13, -14), lean=2, tail=10)]
    b = [P(expr="happy", mouth="open", ra=(12, -12), lean=4, hx=1, fx=[fx("spark", 70, 10)]),
         P(expr="happy", mouth="open", ra=(14, -10), lean=5, hx=1, fx=[fx("spark", 70, 6), fx("dot", 74, 16)]),
         P(expr="happy", mouth="open", ra=(12, -12), lean=4, hx=1, fx=[fx("spark", 70, 10), fx("heart", 12, 10)])]
    c = [P(item=("chestnut", (40, 6), 2), expr="wide", mouth="o", la=(-10, -16), ra=(10, -16)),
         P(item=("chestnut", (40, 14), 2), expr="sparkle", mouth="open", la=(-8, -16), ra=(8, -16)),
         hold("chestnut", expr="happy", mouth="open", y=5, fx=[fx("spark", 14, 10), fx("spark", 66, 10)]),
         hold("chestnut", expr="happy", fx=[fx("heart", 14, 8), fx("heart", 66, 8)])]
    return a, b, c


def m_sorry():    # ごめんね → 反省してます → どんぐりで許して
    a = [P(expr="teary", mouth="sad", la=(-4, -4), ra=(4, -4), ears=-1, fx=[fx("sweat", 58, 10)]),
         P(expr="closed", mouth="sad", hy=7, bh=-2, la=(-5, 3), ra=(5, 3), ears=-1, fx=[fx("sweat", 58, 14)]),
         P(expr="teary", mouth="sad", la=(-4, -4), ra=(4, -4), ears=-1)]
    b = [P(expr="closed", mouth="sad", hy=8, bh=-3, la=(-7, 4), ra=(7, 4), tail=30, tsize=0.9, ears=-1),
         P(expr="closed", mouth="sad", hy=9, bh=-3, la=(-7, 4), ra=(7, 4), tail=34, tsize=0.9, ears=-1, fx=[fx("sweat", 56, 18)]),
         P(expr="closed", mouth="sad", hy=8, bh=-3, la=(-7, 4), ra=(7, 4), tail=30, tsize=0.9, ears=-1, fx=[fx("sweat", 58, 16)])]
    c = [P(item=("acorn", (52, 28), 2), ra=(12, -2), lean=3, expr="teary", mouth="sad"),
         P(item=("acorn", (55, 27), 2), ra=(14, -3), lean=4, expr="teary", mouth="wavy", fx=[fx("sweat", 24, 12)]),
         P(item=("acorn", (52, 28), 2), ra=(12, -2), lean=3, expr="teary", mouth="wavy"),
         P(item=("acorn", (55, 27), 2), ra=(14, -3), lean=4, expr="sparkle", mouth="wavy", fx=[fx("spark", 66, 14)])]
    return a, b, c


def m_goodnight():  # おやすみ → ぬくぬく → 冬眠じゃないよ
    a = [P(expr="sleep", mouth="w", la=(-3, -6), ra=(3, -6), tail=25, fx=[fx("z", 62, 10), fx("z", 68, 4, s=1)]),
         P(expr="sleep", mouth="w", la=(-3, -6), ra=(3, -6), tail=20, hy=1, fx=[fx("z", 64, 8), fx("z", 70, 2)]),
         P(expr="sleep", mouth="o", la=(-3, -6), ra=(3, -6), tail=25, fx=[fx("z", 62, 6), fx("z", 68, 12)])]
    b = [P(expr="sleep", mouth="w", hy=6, bh=-3, bw=2, tside=-1, tail=-60, tsize=1.0, la=(-7, 2), ra=(7, 2), fx=[fx("z", 66, 12)]),
         P(expr="sleep", mouth="w", hy=7, bh=-3, bw=2, tside=-1, tail=-64, la=(-7, 2), ra=(7, 2), fx=[fx("z", 68, 8)]),
         P(expr="sleep", mouth="w", hy=6, bh=-3, bw=2, tside=-1, tail=-60, la=(-7, 2), ra=(7, 2), fx=[fx("z", 70, 4), fx("z", 64, 14)])]
    c = [P(expr="wink", mouth="open", ra=(12, -10), lean=2, fx=[fx("spark", 70, 10)]),
         P(expr="wink", mouth="open", ra=(14, -6), lean=3, fx=[fx("spark", 70, 6)]),
         P(expr="wink", mouth="open", ra=(12, -10), lean=2, fx=[fx("spark", 70, 10)]),
         P(expr="sleep", mouth="w", la=(-3, -6), ra=(3, -6), tail=25, fx=[fx("z", 62, 10)])]
    return a, b, c


def m_kawachii():  # かわちい〜 → 秋コーデ → 優勝です
    a = [P(expr="sparkle", mouth="w", la=(-9, -12), ra=(9, -12), hx=-1, fx=[fx("heart", 14, 10), fx("spark", 64, 8)]),
         P(expr="sparkle", mouth="open", la=(-9, -12), ra=(9, -12), hx=1, lean=2, fx=[fx("heart", 64, 6), fx("spark", 14, 6)]),
         P(expr="sparkle", mouth="w", la=(-9, -12), ra=(9, -12), hx=-1, lean=-2, fx=[fx("heart", 14, 4), fx("spark", 66, 10)])]
    b = [P(expr="happy", flip=True, wind=4, tail=10), P(expr="happy", x=0, tside=-1, tail=-10, wind=-4, y=4, la=(-10, -8), ra=(10, -8)),
         P(expr="wink", mouth="open", wind=3, ra=(10, -16), la=(-6, -4), lean=-2, fx=[fx("spark", 70, 6), fx("spark", 12, 14)])]
    c = [P(expr="happy", mouth="big", la=(-11, -16), ra=(11, -16), y=5, fx=burst(15, 8, cy=24)),
         P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), y=10, fx=burst(19, 10, cy=22)),
         P(expr="sparkle", mouth="open", la=(-11, -16), ra=(11, -16), fx=leaves(6, 8, area=(2, 2, 78, 48)))]
    return a, b, c


def m_pien():     # ぴえん… → どんぐり落とした → ぱおん
    a = [hold("acorn", expr="teary", mouth="sad", ears=-1),
         hold("acorn", expr="teary", mouth="wavy", ears=-1, hy=1, fx=[fx("drop", 28, 22)]),
         hold("acorn", expr="teary", mouth="sad", ears=-1, fx=[fx("drop", 52, 22)])]
    b = [P(expr="wide", mouth="o", la=(-8, -6), ra=(8, -6), item=("acorn", (40, 44), 1), fx=[fx("sweat", 58, 10)]),
         P(expr="wide", mouth="o", la=(-8, -2), ra=(8, -2), lean=5, item=("acorn", (54, 48), 1), fx=[fx("sweat", 60, 10)]),
         P(expr="wide", mouth="open", la=(-6, 2), ra=(14, 0), lean=8, item=("acorn", (70, 48), 1)),
         P(expr="teary", mouth="sad", la=(-6, 2), ra=(14, 0), lean=8, ears=-1)]
    c = [P(expr="cry", mouth="big", la=(-10, -14), ra=(10, -14), y=2, fx=[fx("drop", 20, 18), fx("drop", 60, 18)]),
         P(expr="cry", mouth="big", la=(-11, -16), ra=(11, -16), y=4, fx=[fx("drop", 14, 24), fx("drop", 66, 24), fx("drop", 24, 12), fx("drop", 56, 12)]),
         P(expr="cry", mouth="big", la=(-10, -14), ra=(10, -14), y=2, fx=[fx("drop", 10, 30), fx("drop", 70, 30), fx("drop", 18, 18), fx("drop", 62, 18)]),
         P(expr="cry", mouth="big", la=(-11, -16), ra=(11, -16), y=4, fx=[fx("drop", 14, 24), fx("drop", 66, 24), fx("drop", 8, 38), fx("drop", 72, 38)])]
    return a, b, c


def m_egui():     # えぐい! → 紅葉えぐい → 映えすぎ
    a = [P(expr="wide", mouth="big", la=(-12, -10), ra=(12, -10), y=8, ears=2, fx=[fx("sweat", 62, 6), fx("sweat", 18, 6)]),
         P(expr="wide", mouth="big", la=(-12, -12), ra=(12, -12), y=10, x=-3, ears=2, fx=[fx("sweat", 64, 4), fx("sweat", 16, 4)]),
         P(expr="wide", mouth="big", la=(-12, -10), ra=(12, -10), y=0, bh=-2, ears=2, fx=[fx("sweat", 62, 8)])]
    b = [P(expr="sparkle", mouth="open", ra=(13, -12), lean=4, fx=leaves(7, 8, area=(2, 2, 78, 30))),
         P(expr="sparkle", mouth="open", ra=(13, -12), lean=4, fx=leaves(7, 8, dy=5, area=(2, 2, 78, 30))),
         P(expr="sparkle", mouth="open", la=(-13, -12), lean=-4, fx=leaves(7, 8, dy=10, area=(2, 2, 78, 30))),
         P(expr="sparkle", mouth="open", la=(-13, -12), lean=-4, fx=leaves(7, 8, dy=15, area=(2, 2, 78, 30)))]
    c = [P(expr="wink", mouth="open", ra=(10, -14), la=(-6, -4), fx=[fx("spark", 64, 6)]),
         P(expr="wink", mouth="open", ra=(10, -14), la=(-6, -4), y=3, fx=[fx("spark", 64, 4), fx("spark", 16, 8), fx("spark", 70, 20)]),
         P(expr="wink", mouth="open", ra=(10, -14), la=(-6, -4), fx=[fx("spark", 66, 6), fx("spark", 14, 10), fx("spark", 70, 22), fx("spark", 10, 26)])]
    return a, b, c


def stick_pose(up, **kw):
    """紅葉ペンライトを左右に振る。"""
    la, ra = ((-12, -16), (6, -18)) if up else ((-6, -18), (12, -16))
    lx, ly = 40 + la[0], 35 + la[1] - 6
    rx, ry = 40 + ra[0], 35 + ra[1] - 6
    return P(la=la, ra=ra, lean=-2 if up else 2,
             fx=[fx("maple", lx, ly, "#D6332A"), fx("maple", rx, ry, "#F08A1E")] + kw.pop("fx", []), **kw)


def m_oseru():    # 推せる → 秋の推し活 → 栗しか勝たん
    a = [P(expr="heart", mouth="open", la=(-8, -12), ra=(8, -12), y=3, fx=[fx("heart", 14, 8), fx("heart", 66, 8)]),
         P(expr="heart", mouth="open", la=(-9, -14), ra=(9, -14), y=7, fx=[fx("heart", 12, 4), fx("heart", 68, 4)]),
         P(expr="heart", mouth="w", la=(-8, -12), ra=(8, -12), y=0, fx=[fx("heart", 14, 8), fx("heart", 66, 8)])]
    b = [stick_pose(True, expr="sparkle", mouth="open"), stick_pose(False, expr="sparkle", mouth="open", y=3),
         stick_pose(True, expr="sparkle", mouth="open"), stick_pose(False, expr="sparkle", mouth="open", y=3)]
    c = [hold("chestnut", expr="heart", mouth="open", fx=[fx("heart", 14, 10), fx("heart", 66, 10)]),
         P(item=("chestnut", (40, 10), 2), expr="heart", mouth="open", la=(-9, -14), ra=(9, -14), y=4, fx=[fx("heart", 12, 6), fx("heart", 68, 6)]),
         hold("chestnut", expr="heart", mouth="w", cheek=1, fx=[fx("heart", 14, 6), fx("heart", 66, 6), fx("heart", 40, 2)])]
    return a, b, c


def m_gachi():    # ガチ? → まじで? → 詳しく聞かせて
    a = [P(expr="wide", mouth="o", ears=2, la=(-6, -4), ra=(6, -4)),
         P(expr="wide", mouth="o", ears=2, hx=4, lean=6, la=(-2, -6), ra=(10, -6)),
         P(expr="wide", mouth="o", ears=2, hx=5, lean=8, la=(0, -6), ra=(12, -6), fx=[fx("sweat", 70, 10)])]
    b = [P(expr="wide", mouth="open", ears=2, y=6, la=(-12, -12), ra=(12, -12), fx=[fx("spark", 12, 6), fx("spark", 68, 6)]),
         P(expr="wide", mouth="open", ears=2, y=0, bh=-1, la=(-12, -10), ra=(12, -10)),
         P(expr="wide", mouth="open", ears=2, y=6, la=(-12, -12), ra=(12, -12), fx=[fx("spark", 12, 6), fx("spark", 68, 6)])]
    c = [P(expr="sparkle", mouth="o", hx=-4, lean=-6, la=(-12, -10), ra=(-4, -6), ears=1),
         P(expr="sparkle", mouth="o", hx=-5, lean=-7, la=(-13, -11), ra=(-4, -6), ears=2, fx=[fx("dot", 8, 14)]),
         P(expr="sparkle", mouth="o", hx=-4, lean=-6, la=(-12, -10), ra=(-4, -6), ears=1, fx=[fx("dot", 8, 14), fx("dot", 6, 22)]),
         P(expr="sparkle", mouth="o", hx=-5, lean=-7, la=(-13, -11), ra=(-4, -6), ears=2, fx=[fx("dot", 8, 14), fx("dot", 6, 22), fx("dot", 10, 30)])]
    return a, b, c


def m_daisuki():  # 大好き! → めっちゃ好き → 栗くらい好き
    a = [P(expr="happy", mouth="open", la=(-12, -14), ra=(12, -14), fx=[fx("heart", 40, 6, s=2)]),
         P(expr="happy", mouth="open", la=(-10, -16), ra=(10, -16), y=5, fx=[fx("heart", 40, 3, s=2), fx("heart", 12, 12), fx("heart", 68, 12)]),
         P(expr="happy", mouth="open", la=(-12, -14), ra=(12, -14), fx=[fx("heart", 40, 6, s=2), fx("heart", 10, 8), fx("heart", 70, 8)])]
    b = [P(expr="closed", mouth="w", tside=-1, tail=-50, la=(-8, -4), ra=(-2, -6), lean=-2, fx=[fx("heart", 66, 10)]),
         P(expr="closed", mouth="w", tside=-1, tail=-50, la=(-8, -4), ra=(-2, -6), lean=2, fx=[fx("heart", 66, 6), fx("heart", 14, 10)]),
         P(expr="closed", mouth="w", tside=-1, tail=-50, la=(-8, -4), ra=(-2, -6), lean=-2, fx=[fx("heart", 68, 3), fx("heart", 12, 6), fx("heart", 60, 14)]),
         P(expr="closed", mouth="w", tside=-1, tail=-50, la=(-8, -4), ra=(-2, -6), lean=2, fx=[fx("heart", 10, 3), fx("heart", 66, 8), fx("heart", 20, 16)])]
    c = [hold("chestnut", expr="sparkle", mouth="open", fx=[fx("heart", 14, 10)]),
         P(item=("chestnut", (40, 6), 2), expr="heart", mouth="open", la=(-9, -16), ra=(9, -16), y=4, fx=[fx("heart", 12, 8), fx("heart", 68, 8)]),
         hold("chestnut", expr="heart", mouth="w", fx=[fx("heart", 12, 4), fx("heart", 68, 4), fx("heart", 20, 16), fx("heart", 60, 16)])]
    return a, b, c


def m_iine():     # いいね! → 秋っぽい → センスいい
    a = [P(expr="wink", mouth="open", ra=(10, -12), item=("maple", "r", 2)),
         P(expr="wink", mouth="open", ra=(11, -16), item=("maple", "r", 2), y=5, fx=[fx("spark", 66, 6)]),
         P(expr="wink", mouth="w", ra=(10, -12), item=("maple", "r", 2), fx=[fx("spark", 68, 10)])]
    b = [P(expr="happy", la=(-10, -8), ra=(10, -8), lean=-3, hx=-1, fx=fall(0, 5)),
         P(expr="happy", la=(-10, -8), ra=(10, -8), lean=3, hx=1, fx=fall(1, 5)),
         P(expr="happy", la=(-10, -8), ra=(10, -8), lean=-3, hx=-1, fx=fall(2, 5)),
         P(expr="happy", la=(-10, -8), ra=(10, -8), lean=3, hx=1, fx=fall(3, 5))]
    c = [P(expr="sparkle", mouth="open", ra=(12, -6), lean=4, fx=[fx("spark", 70, 12)]),
         P(expr="sparkle", mouth="open", ra=(14, -8), lean=5, y=3, fx=[fx("spark", 72, 8), fx("spark", 64, 2)]),
         P(expr="sparkle", mouth="open", ra=(12, -6), lean=4, fx=[fx("spark", 70, 12), fx("dot", 74, 22)])]
    return a, b, c


def m_shokuyoku():  # 食欲の秋 → 止まらない → ほっぺパンパン
    a = [hold("acorn", expr="sparkle", mouth="open", fx=[fx("chestnut", 14, 44), fx("potato", 66, 46), fx("mush", 64, 34)]),
         hold("acorn", expr="sparkle", mouth="open", y=4, fx=[fx("chestnut", 14, 44), fx("potato", 66, 46), fx("mush", 64, 34)]),
         hold("acorn", expr="sparkle", mouth="open", fx=[fx("chestnut", 14, 44), fx("potato", 66, 46), fx("mush", 64, 34), fx("spark", 40, 4)])]
    b = [hold("acorn", expr="closed", mouth="munch", cheek=1), hold("chestnut", expr="closed", mouth="munch", cheek=2, hy=1),
         hold("acorn", expr="closed", mouth="munch", cheek=3), hold("chestnut", expr="closed", mouth="munch", cheek=3, hy=1)]
    c = [P(expr="happy", mouth="munch", cheek=4, la=(-12, -6), ra=(12, -6)),
         P(expr="wide", mouth="munch", cheek=5, la=(-13, -6), ra=(13, -6), y=3, fx=[fx("sweat", 66, 8)]),
         P(expr="wide", mouth="munch", cheek=5, la=(-13, -6), ra=(13, -6), fx=[fx("sweat", 66, 10), fx("sweat", 14, 10)])]
    return a, b, c


def m_matte():    # ちょっと待って → 今どんぐり集め中 → あと3個
    a = [P(expr="wide", mouth="open", ra=(14, -10), lean=5, fx=[fx("sweat", 66, 6)]),
         P(expr="wide", mouth="open", ra=(15, -12), lean=6, hx=1, fx=[fx("sweat", 68, 4)]),
         P(expr="wide", mouth="open", ra=(14, -10), lean=5, fx=[fx("sweat", 66, 6)])]
    b = [P(expr="sparkle", x=-18, flip=True, lean=-4, la=(-6, 4), ra=(6, 4), hy=3, fx=[fx("pile", 18, 49), fx("acorn", 60, 48)]),
         P(expr="sparkle", x=-14, flip=True, lean=-5, la=(-6, 6), ra=(6, 6), hy=4, fx=[fx("pile", 18, 49)]),
         P(expr="happy", x=14, lean=4, la=(-4, 0), ra=(4, 0), item=("acorn", "hands", 1), y=4, fx=[fx("pile", 18, 49)]),
         P(expr="happy", x=8, lean=-2, la=(-10, -2), ra=(4, 0), fx=[fx("pile", 20, 47, s=2)])]
    c = [P(expr="wink", mouth="open", la=(-6, -14), ra=(8, -10), fx=[fx("pile", 16, 47, s=2), fx("acorn", 66, 22), fx("acorn", 70, 30), fx("acorn", 62, 38)]),
         P(expr="wink", mouth="open", la=(-6, -14), ra=(8, -10), y=4, fx=[fx("pile", 16, 47, s=2), fx("acorn", 66, 20), fx("acorn", 70, 28), fx("acorn", 62, 36)]),
         P(expr="wink", mouth="w", la=(-6, -14), ra=(8, -10), fx=[fx("pile", 16, 47, s=2), fx("acorn", 66, 22), fx("acorn", 70, 30), fx("acorn", 62, 38)])]
    return a, b, c


def m_tanoshimi():  # 楽しみ! → わくわく → 秋の予定立てよ
    a = [P(expr="sparkle", mouth="open", la=(-11, -12), ra=(11, -12), y=8, ears=1, fx=[fx("note", 12, 8), fx("note", 68, 12)]),
         P(expr="sparkle", mouth="open", la=(-9, -6), ra=(9, -6), y=0, bh=-2, fx=[fx("note", 12, 12), fx("note", 68, 8)]),
         P(expr="sparkle", mouth="open", la=(-11, -12), ra=(11, -12), y=8, ears=1, fx=[fx("note", 10, 6), fx("note", 70, 10)])]
    b = [P(expr="happy", mouth="open", x=-8, lean=-3, fl=3, la=(-10, -8), ra=(8, -10), tail=-10, fx=[fx("note", 66, 10)]),
         P(expr="happy", mouth="open", x=0, y=4, la=(-10, -10), ra=(10, -10), tail=10, fx=[fx("note", 14, 10)]),
         P(expr="happy", mouth="open", x=8, lean=3, fr=3, la=(-8, -10), ra=(10, -8), tail=-10, fx=[fx("note", 14, 6)]),
         P(expr="happy", mouth="open", x=0, y=4, la=(-10, -10), ra=(10, -10), tail=10, fx=[fx("note", 66, 6)])]
    c = [P(expr="normal", mouth="w", ra=(4, -8), hx=-2, hy=1, la=(-6, -4), fx=[fx("dot", 64, 10)]),
         P(expr="sparkle", mouth="open", ra=(10, -18), y=4, fx=[fx("spark", 66, 4), fx("maple", 14, 10, "#D6332A"), fx("ginkgo", 66, 18, "#F2C230")]),
         P(expr="sparkle", mouth="open", ra=(10, -18), fx=[fx("spark", 66, 6), fx("maple", 14, 12, "#D6332A"), fx("ginkgo", 66, 20, "#F2C230"), fx("potato", 12, 28)])]
    return a, b, c


def m_samu():     # 寒っ! → 秋どこ行った → マフラー巻いた
    wind_fx = lambda i: [fx("leaf", 10 + i * 8, 14 + i * 2, "#F08A1E"), fx("maple", 20 + i * 8, 30 - i, "#D6332A")]
    a = [P(expr="wide", mouth="wavy", la=(-3, -2), ra=(3, -2), bw=-1, x=-1, ears=-1, wind=6, fx=wind_fx(0)),
         P(expr="wide", mouth="wavy", la=(-3, -2), ra=(3, -2), bw=-1, x=1, ears=-1, wind=7, fx=wind_fx(1)),
         P(expr="wide", mouth="wavy", la=(-3, -2), ra=(3, -2), bw=-1, x=-1, ears=-1, wind=6, fx=wind_fx(2)),
         P(expr="wide", mouth="wavy", la=(-3, -2), ra=(3, -2), bw=-1, x=1, ears=-1, wind=7, fx=wind_fx(3))]
    b = [P(expr="normal", mouth="o", hx=-3, lean=-4, la=(-12, -10), ra=(-6, -12), fx=[fx("sweat", 62, 8)]),
         P(expr="normal", mouth="o", hx=3, lean=4, la=(6, -12), ra=(12, -10), fx=[fx("sweat", 18, 8)]),
         P(expr="wide", mouth="open", la=(-12, -10), ra=(12, -10), y=5, fx=[fx("sweat", 62, 4), fx("sweat", 18, 4)])]
    c = [P(expr="closed", mouth="w", la=(-2, -10), ra=(2, -10), wind=0),
         P(expr="happy", mouth="w", la=(-4, -6), ra=(4, -6), wind=1, tside=-1, tail=-50, fx=[fx("heart", 66, 10)]),
         P(expr="happy", mouth="w", la=(-4, -6), ra=(4, -6), wind=1, tside=-1, tail=-50, hy=1, fx=[fx("heart", 66, 6), fx("heart", 14, 10)])]
    return a, b, c


def m_congrats():  # おめでとう! → お祝いだ〜 → 紅葉ふぶき
    a = [P(expr="happy", mouth="big", la=(-12, -16), ra=(12, -16), y=6, fx=burst(16, 8, cy=24)),
         P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), y=10, fx=burst(20, 10, cy=22)),
         P(expr="happy", mouth="open", la=(-12, -16), ra=(12, -16), y=4, fx=burst(22, 10, cy=26))]
    b = [P(expr="sparkle", mouth="open", la=(-10, -8), ra=(10, -8), x=-6, y=4, fx=[fx("note", 66, 8), fx("spark", 12, 6)]),
         P(expr="sparkle", mouth="open", la=(-12, -16), ra=(12, -16), x=0, y=10, fx=[fx("note", 14, 8), fx("spark", 68, 6)]),
         P(expr="sparkle", mouth="open", la=(-10, -8), ra=(10, -8), x=6, y=4, fx=[fx("note", 14, 4), fx("spark", 68, 10)])]
    c = [P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), fx=leaves(8, 12, dy=0, area=(2, 0, 78, 48))),
         P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), y=4, fx=leaves(8, 12, dy=5, area=(2, 0, 78, 48))),
         P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), fx=leaves(8, 12, dy=10, area=(2, 0, 78, 48))),
         P(expr="happy", mouth="big", la=(-12, -18), ra=(12, -18), y=4, fx=leaves(8, 12, dy=15, area=(2, 0, 78, 48)))]
    return a, b, c


def m_aitai():    # 会いたい → 秋だから → 寂しいの
    a = [P(expr="teary", mouth="w", ra=(12, -6), lean=4, hx=1, tail=10, fx=[fx("heart", 68, 10)]),
         P(expr="teary", mouth="w", ra=(14, -4), lean=6, hx=2, tail=14, fx=[fx("heart", 70, 6)]),
         P(expr="teary", mouth="w", ra=(12, -6), lean=4, hx=1, tail=10, fx=[fx("heart", 68, 3)])]
    b = [P(expr="normal", mouth="w", hx=-2, hy=-1, la=(-4, -2), ra=(4, -2), fx=fall(0, 4)),
         P(expr="normal", mouth="w", hx=-2, hy=-1, la=(-4, -2), ra=(4, -2), fx=fall(1, 4)),
         P(expr="normal", mouth="w", hx=-2, hy=-1, la=(-4, -2), ra=(4, -2), fx=fall(2, 4))]
    c = [P(expr="teary", mouth="sad", tside=-1, tail=-50, la=(-8, -4), ra=(-2, -6), hy=2, ears=-1),
         P(expr="teary", mouth="sad", tside=-1, tail=-54, la=(-8, -4), ra=(-2, -6), hy=3, ears=-1, fx=[fx("drop", 52, 22)]),
         P(expr="teary", mouth="sad", tside=-1, tail=-50, la=(-8, -4), ra=(-2, -6), hy=2, ears=-1, fx=[fx("drop", 52, 28)]),
         P(expr="teary", mouth="wavy", tside=-1, tail=-54, la=(-8, -4), ra=(-2, -6), hy=3, ears=-1, fx=[fx("heart", 66, 8)])]
    return a, b, c


def m_yoroshiku():  # よろしくね → ゆるっと → お願いします
    a = [P(expr="wink", mouth="open", ra=(11, -16), tail=-10), P(expr="wink", mouth="open", ra=(14, -12), tail=10, lean=2),
         P(expr="wink", mouth="open", ra=(9, -18), tail=-10, lean=-1), P(expr="wink", mouth="open", ra=(14, -12), tail=10, lean=2)]
    b = [P(expr="happy", mouth="w", x=-5, lean=-4, hx=-1, tail=-15, la=(-8, -2), ra=(8, -2)),
         P(expr="happy", mouth="w", x=0, la=(-8, -2), ra=(8, -2)),
         P(expr="happy", mouth="w", x=5, lean=4, hx=1, tail=15, la=(-8, -2), ra=(8, -2)),
         P(expr="happy", mouth="w", x=0, la=(-8, -2), ra=(8, -2))]
    c = [P(expr="closed", mouth="w", hy=7, bh=-2, la=(-5, 3), ra=(5, 3), tail=20),
         P(expr="closed", mouth="w", hy=8, bh=-3, la=(-5, 4), ra=(5, 4), tail=24, fx=[fx("spark", 66, 10)]),
         P(expr="happy", mouth="open", la=(-4, -6), ra=(4, -6), fx=[fx("heart", 66, 8), fx("heart", 14, 8)])]
    return a, b, c


MOTIONS = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}


# --- 書き出し ----------------------------------------------------------------
def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = cfg_path.parent / cfg["output"]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    problems, all_frames = [], []
    for i, item in enumerate(cfg["stamps"], 1):
        scenes = MOTIONS[item["motion"]]()
        imgs, ms = [], []
        for text, poses, total in zip(item["texts"], scenes, SCENE_MS):
            for j, p in enumerate(poses):
                imgs.append(render(p, text, pop=(j == 0 and imgs != [])))
            ms += an.split(total, len(poses))
        if not 5 <= len(imgs) <= 20:
            raise SystemExit(f"{item['motion']}: フレーム数 {len(imgs)}")
        path = out / f"{i:02d}.png"
        an.save_apng(imgs, ms, 1, path)
        all_frames.append((imgs, ms, 1))
        info, errs = an.check_anim(path, "stamp")
        problems += [f"{path.name}: {e}" for e in errs]
        print(f"  {path.name} {item['motion']:<10} {info['frames']:>2}f {info['ms']:>4}ms {info['bytes'] // 1024:>3}KB  {' → '.join(item['texts'])}")

    # メイン画像 (240x240): どんぐりを持ってまばたき / タブ画像
    exprs = ["sparkle"] * 5 + ["closed"] + ["sparkle"] * 4
    grids = [render_grid(hold("acorn", expr=e, y=1 if j in (2, 3, 7, 8) else 0)) for j, e in enumerate(exprs)]
    box = (14, 6, 66, 55)
    k = min((MAIN_SIZE[0] - 16) // (box[2] - box[0]), (MAIN_SIZE[1] - 16) // (box[3] - box[1]))
    mains = []
    for g in grids:
        big = ps.scaled(g.crop(box), k)
        canvas = Image.new("RGBA", MAIN_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(big, ((MAIN_SIZE[0] - big.width) // 2, (MAIN_SIZE[1] - big.height) // 2))
        mains.append(canvas)
    an.save_apng(mains, an.split(2000, len(mains)), 2, out / "main.png")
    problems += [f"main.png: {e}" for e in an.check_anim(out / "main.png", "main")[1]]
    ps.fit_square(render_grid(hold("acorn", expr="happy")), TAB_SIZE, 2).save(out / "tab.png")

    an.make_preview_gif(all_frames, cfg_path.parent / cfg["preview"])
    zip_path = cfg_path.parent / f"{cfg['name']}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.glob("[0-9][0-9].png")) + [out / "main.png", out / "tab.png"]:
            z.write(p, p.name)
    if problems:
        print("\n❌ 仕様チェックで問題が見つかりました:")
        for p in problems:
            print("  -", p)
    else:
        print("\n✔ 仕様チェック OK (サイズ・フレーム数・再生時間・ループ・300KB以下・個数)")
    print(f"\n✅ 出力: {out}/  提出用 ZIP: {zip_path}")


def main():
    ap = argparse.ArgumentParser(description="秋のリスの動くスタンプ")
    ap.add_argument("-c", "--config", default="squirrel_stamps.json")
    build(ap.parse_args().config)


if __name__ == "__main__":
    main()
