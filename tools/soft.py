#!/usr/bin/env python3
"""ていねいインコ「ゆるふわ版」: 線をやわらかくしたキャラと、手書き風のセリフを作る。

  確認用シート : python3 tools/soft.py 04 --png sheet.png
  Canva用      : python3 tools/soft.py 04 --text-png text.png --ops ops.json --page PAGE_ID

inko.py のパーツ・ポーズをそのまま使い、見た目だけを変える。
- キャラ: 線を濃い茶→やわらかい茶色にして細くし、輪郭を手描き風に少し揺らす。
  体はふちを小さく波打たせて「ふわふわ」に見せる。羽はふっくら丸く、目は大きく。ほっぺはピンク。
- セリフ: Yusei Magic(手書きマーカー風, OFL)で一文字ずつ置き、文字ごとに少し傾ける。
  言葉ごとに色を分け、コマごとに「ポン」と出す(拡大→戻る)。
"""
import argparse
import copy
import math
import random
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import inko

ROOT = Path(__file__).resolve().parent.parent
HAND_FONT = ROOT / "assets/fonts/YuseiMagic-Regular.ttf"
COLS, ROWS = 4, 3
CW, CH = inko.CELL_W, inko.CELL_H

LINE = "#8C6450"      # やわらかい茶色の線(細く・淡く)
EYE = "#4A3328"
CHEEK = "#FFB3C1"
BROWN, ORANGE, PINK = "#5B3A2E", "#F2894B", "#EE7D98"
CORAL = "#F0607A"     # 強調語(1スタンプ1か所)
RIM = "#E2C2AC"       # 文字の白フチのさらに外側の、淡い茶色のフチ
FILLS = {"#FFE066": "#FFE98F", "#FFF6D6": "#FFF8E3", "#F5B83D": "#F7C766"}  # 塗りを淡く

BODY_PATHS = {inko.BODY} | {d for k, (_, _, d) in inko.ALT.items() if k.startswith("BODY")}


# ---- キャラをやわらかくする ---------------------------------------------------

def scallop(w, h, bumps=18, depth=1.6):
    """体のふちを小さく波打たせた楕円(ふわふわの毛並み)。"""
    cx, cy, rx, ry = w / 2, h / 2 + 1, w / 2 - 3, h / 2 - 3
    pts = []
    for i in range(bumps + 1):
        a = -math.pi / 2 + 2 * math.pi * i / bumps
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a), a))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (x0, y0, a0), (x1, y1, a1) in zip(pts, pts[1:]):
        k = 1 + depth / min(rx, ry)
        c1 = (cx + rx * k * math.cos(a0 + (a1 - a0) / 3), cy + ry * k * math.sin(a0 + (a1 - a0) / 3))
        c2 = (cx + rx * k * math.cos(a1 - (a1 - a0) / 3), cy + ry * k * math.sin(a1 - (a1 - a0) / 3))
        d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {x1:.1f} {y1:.1f}"
    return d + " Z"


# 羽: なめらかでふっくらした形に、下側だけ小さな羽先を2つ(ボコボコさせない)
WING_L = "M22 2 C30 10 30 32 25 44 C23 48 20 50 17 48 C15 51 11 51 9 48 C6 49 3 46 4 42 C2 30 8 10 22 2 Z"
WING_R = "M8 2 C0 10 0 32 5 44 C7 48 10 50 13 48 C15 51 19 51 21 48 C24 49 27 46 26 42 C28 30 22 10 8 2 Z"


def big_eyes(c, k=1.4, hk=1.7):
    """目を大きく、ハイライトも大きくする(閉じ目・にっこり目も同じ倍率)。"""
    for eye, hl in (("P8", "P10"), ("P9", "P11")):
        if eye not in c:
            continue
        e = c[eye]
        ex, ey = e["left"] + e["w"] / 2, e["top"] + e["h"] / 2
        e.setdefault("vw", e["w"])
        e.setdefault("vh", e["h"])
        e["w"], e["h"] = e["w"] * k, e["h"] * k
        e["left"], e["top"] = ex - e["w"] / 2, ey - e["h"] / 2
        if hl in c:
            h = c[hl]
            hx, hy = h["left"] + h["w"] / 2, h["top"] + h["h"] / 2
            h.setdefault("vw", h["w"])
            h.setdefault("vh", h["h"])
            h["w"], h["h"] = h["w"] * hk, h["h"] * hk
            nx, ny = ex + (hx - ex) * k, ey + (hy - ey) * k
            h["left"], h["top"] = nx - h["w"] / 2, ny - h["h"] / 2


def _unit(x, y):
    l = math.hypot(x, y)
    return x / l, y / l


def round_chevron(a, b, c, r):
    """折れ線 a-b-c を太さ 2r の線にした形(両端と外側の角を丸める)。place() が A を楕円に
    置き換えてしまうので、丸みはすべて C で描く。"""
    def side(a, b, c):
        """a→b→c の左側(進む向きに対して)をたどる。b の角は内側なら交点、外側なら丸める。"""
        d1, d2 = _unit(b[0] - a[0], b[1] - a[1]), _unit(c[0] - b[0], c[1] - b[1])
        n1, n2 = (d1[1], -d1[0]), (d2[1], -d2[0])
        cos = n1[0] * n2[0] + n1[1] * n2[1]
        q = (b[0] + r * (n1[0] + n2[0]) / (1 + cos), b[1] + r * (n1[1] + n2[1]) / (1 + cos))
        if (q[0] - b[0]) * d1[0] + (q[1] - b[1]) * d1[1] < 0:
            segs = [("L", q)]
        else:
            k = 4 / 3 * math.tan(math.acos(max(-1.0, min(1.0, cos))) / 4) * r
            p1, p2 = (b[0] + r * n1[0], b[1] + r * n1[1]), (b[0] + r * n2[0], b[1] + r * n2[1])
            segs = [("L", p1), ("C", (p1[0] + k * d1[0], p1[1] + k * d1[1]), (p2[0] - k * d2[0], p2[1] - k * d2[1]), p2)]
        return segs + [("L", (c[0] + r * n2[0], c[1] + r * n2[1]))], d2, n2

    def cap(o, n, d):
        """o を中心にした半円(+n 側 → 先端 o+r·d → -n 側)を C 2本で。"""
        k = 0.5523 * r
        p1, tip, p2 = (o[0] + r * n[0], o[1] + r * n[1]), (o[0] + r * d[0], o[1] + r * d[1]), (o[0] - r * n[0], o[1] - r * n[1])
        return [("C", (p1[0] + k * d[0], p1[1] + k * d[1]), (tip[0] + k * n[0], tip[1] + k * n[1]), tip),
                ("C", (tip[0] - k * n[0], tip[1] - k * n[1]), (p2[0] + k * d[0], p2[1] + k * d[1]), p2)]

    go, d2, n2 = side(a, b, c)
    back, d0, n0 = side(c, b, a)  # 逆向きにたどると、反対側のふちになる
    d1 = _unit(b[0] - a[0], b[1] - a[1])
    start = (a[0] + r * d1[1], a[1] - r * d1[0])
    segs = go + cap(c, n2, d2) + back + cap(a, n0, d0)
    return f"M{start[0]:.1f} {start[1]:.1f} " + " ".join(
        op + " ".join(f"{x:.1f} {y:.1f}" for x, y in pts) for op, *pts in segs) + " Z"


# 目は角を丸くする: にっこり目・閉じ目は両端を丸め、「><」目は丸い線で描き直す
ROUND_EYES = {
    inko.ALT["E_HAPPY"][2]: "M1 9 C3 1 11 1 13 9 C13 10.3 11 10.3 11 9 C9.5 5 4.5 5 3 9 C3 10.3 1 10.3 1 9 Z",
    inko.ALT["E_CLOSE"][2]: "M1 1 C3 9 11 9 13 1 C13 -0.3 11 -0.3 11 1 C9.5 5 4.5 5 3 1 C3 -0.3 1 -0.3 1 1 Z",
    inko.ALT["E_X_L"][2]: round_chevron((2.4, 3.4), (11.4, 7), (2.4, 10.6), 1.6),
    inko.ALT["E_X_R"][2]: round_chevron((11.6, 3.4), (2.6, 7), (11.6, 10.6), 1.6),
}


def wobble(d, seed, amt=1.0):
    """パスの座標を少しずらして手描きの揺らぎを出す。"""
    rnd = random.Random(seed)
    return re.sub(r"-?\d+(?:\.\d+)?", lambda m: f"{float(m.group()) + rnd.uniform(-amt, amt):.1f}", d)


def soften(c):
    for key, e in c.items():
        e["d"] = ROUND_EYES.get(e["d"], e["d"])
        if e["d"] in BODY_PATHS:
            e["d"] = scallop(e.get("vw", e["w"]), e.get("vh", e["h"]))
        elif key in ("P6", "P7"):
            e["d"] = wobble(WING_L if key == "P6" else WING_R, key, 0.5)
        elif e["sw"] and key not in ("P0", "P15"):
            e["d"] = wobble(e["d"], key)
        if e["stroke"] == inko.INK:
            e["stroke"] = LINE
            e["sw"] = round(e["sw"] * 0.65, 1)
        if e["fill"] == inko.INK:
            e["fill"] = EYE
        if key in ("P12", "P13"):
            e["fill"] = CHEEK
        e["fill"] = FILLS.get(e["fill"], e["fill"])
        if key in ("P8", "P9", "P10", "P11"):
            e["top"] += 5  # 目を少し下げて幼く
        if key == "P0":
            e["sw"] = 10
    big_eyes(c)
    for key in ("P14", "P15", "P15m"):  # くちばしは小さめに(口の中はくちばしの中心を基準に縮める)
        if key in c:
            e = c[key]
            b = c["P15"] if key == "P15m" else e
            cx, cy = b["left"] + b["w"] / 2, b["top"] + b["h"] / 2
            if key == "P15m":
                e["left"], e["top"] = cx + (e["left"] - cx) * 0.78, cy + (e["top"] - cy) * 0.78
                e["w"], e["h"] = e["w"] * 0.78, e["h"] * 0.78
                continue
            e.setdefault("vw", e["w"])
            e.setdefault("vh", e["h"])
            e["w"], e["h"] = e["w"] * 0.78, e["h"] * 0.78
            e["left"], e["top"] = cx - e["w"] / 2, cy - e["h"] / 2
    return c


def chara_elems(poses, scale=1.0, anchor=(160, 258)):
    """scale>1 でキャラを大きくし、足元(160,258)を anchor に合わせる。"""
    c = copy.deepcopy(inko.BASE)
    for p in poses:
        p(c)
    elems = list(soften(c).values())
    for e in elems:
        e["left"] = anchor[0] + (e["left"] - 160) * scale
        e["top"] = anchor[1] + (e["top"] - 258) * scale
        e["w"], e["h"] = e["w"] * scale, e["h"] * scale  # 線の太さは変えない(太いと硬く見える)
        e.setdefault("vw", e["w"] / scale)
        e.setdefault("vh", e["h"] / scale)
    return elems


# ---- 手書き風セリフ ----------------------------------------------------------

def word(text, cx, cy, size, color, rot=0, scale=1.0, arc=0, seed=0, vertical=False, count=None,
         last=1.0, wave=None, shiver=None):
    """セリフ1語。
    count : 先頭から count 文字だけ出す(書いているように見せる)
    last  : 最後に出した1文字だけの倍率(1文字ずつ「ポン」と出す)
    wave  : (振れ幅px, 位相) 文字を波のように上下させる(跳ねる)
    shiver: (px, 度, 乱数の種) 文字をぷるぷる震わせる
    """
    return dict(text=text, cx=cx, cy=cy, size=size, color=color, rot=rot, scale=scale, arc=arc, seed=seed,
                vertical=vertical, count=len(text) if count is None else count, last=last, wave=wave, shiver=shiver)


def draw_word(layer, w, ox, oy, outline=9):
    """一文字ずつ、少し傾け・上下にずらして置く。arc>0 で笑った口のような弧になる。"""
    size = round(w["size"] * w["scale"])
    rnd = random.Random(w["seed"])
    shv = random.Random(w["shiver"][2]) if w["shiver"] else None
    n = len(w["text"])
    adv = size * 0.98
    total = adv * n
    r = math.radians(w["rot"])
    for i, ch in enumerate(w["text"]):
        jit = (rnd.uniform(-2, 2), rnd.uniform(-7, 7))
        if i >= w["count"]:
            continue
        t = (i + 0.5) / n - 0.5
        lx = -total / 2 + adv * (i + 0.5)
        ly = w["arc"] * size * (4 * t * t - 1) * 0.5 + jit[0]
        rot = w["rot"] + jit[1]
        if w["wave"]:
            ly += w["wave"][0] * math.sin(w["wave"][1] + i * 0.9)
        if shv:
            lx += shv.uniform(-1, 1) * w["shiver"][0]
            ly += shv.uniform(-1, 1) * w["shiver"][0]
            rot += shv.uniform(-1, 1) * w["shiver"][1]
        if w["vertical"]:
            lx, ly = jit[0] - w["arc"] * size * (4 * t * t - 1) * 0.5, lx
        csize = round(size * (w["last"] if i == w["count"] - 1 else 1))
        font = ImageFont.truetype(str(HAND_FONT), csize)
        x = ox + w["cx"] + lx * math.cos(r) - ly * math.sin(r)
        y = oy + w["cy"] + lx * math.sin(r) + ly * math.cos(r)
        pad = outline + 6
        g = Image.new("RGBA", (csize + pad * 2, csize + pad * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(g)
        pos = (pad + csize / 2, pad + csize / 2)
        dr.text(pos, ch, font=font, anchor="mm", fill=RIM, stroke_width=outline + 2, stroke_fill=RIM)
        dr.text(pos, ch, font=font, anchor="mm", fill=w["color"], stroke_width=outline, stroke_fill="white")
        g = g.rotate(-rot, resample=Image.BICUBIC, expand=True)
        layer.alpha_composite(g, (round(x - g.width / 2), round(y - g.height / 2)))


def draw_marks(layer, marks, ox, oy):
    d = ImageDraw.Draw(layer)
    for kind, x, y, s in marks:
        x, y = ox + x, oy + y
        if kind == "peko":  # おじぎの「ペコッ」線(3本)
            for k, a in enumerate((-55, -25, 5)):
                ra = math.radians(a)
                p0 = (x + s * 0.5 * math.cos(ra), y + s * 0.5 * math.sin(ra))
                p1 = (x + s * math.cos(ra), y + s * math.sin(ra))
                d.line([p0, p1], fill="white", width=8)
                d.line([p0, p1], fill=LINE, width=3)
        elif kind == "heart":
            pts = [(x + s * math.sin(t) ** 3, y - s * (13 * math.cos(t) - 5 * math.cos(2 * t)
                    - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16) for t in [i * math.pi / 30 for i in range(61)]]
            d.polygon(pts, fill=PINK, outline="white", width=3)
        elif kind == "spark":  # キラキラ(4つ角の星)
            pts = []
            for k in range(8):
                a = math.pi / 2 * k / 2 - math.pi / 2
                r = s if k % 2 == 0 else s * 0.32
                pts.append((x + r * math.cos(a), y + r * math.sin(a)))
            d.polygon(pts, fill="#FFD84D", outline="white", width=3)
            d.line(pts + pts[:1], fill=LINE, width=2, joint="curve")
        elif kind == "sweat":  # 汗のしずく
            pts = [(x, y - s)] + [(x + s * 0.6 * math.cos(a), y + s * 0.35 + s * 0.6 * math.sin(a))
                                  for a in [math.pi * (-0.15 + 1.3 * k / 20) for k in range(21)]] + [(x, y - s)]
            d.polygon(pts, fill="#9FD3F5", outline="white", width=3)
            d.line(pts, fill=LINE, width=2, joint="curve")
        elif kind == "z":  # 寝息の Z
            font = ImageFont.truetype(str(HAND_FONT), round(s))
            d.text((x, y), "Z", font=font, anchor="mm", fill="#8E9BD8", stroke_width=5, stroke_fill="white")
        elif kind == "note":  # 音符
            font = ImageFont.truetype(str(HAND_FONT), round(s))
            d.text((x, y), "♪", font=font, anchor="mm", fill=CORAL, stroke_width=5, stroke_fill="white")


# ---- スタンプの台本(12コマ) -----------------------------------------------

def kf(poses, words=(), marks=(), scale=1.25, anchor=(198, 246)):
    return dict(poses=poses, words=list(words), marks=list(marks), scale=scale, anchor=anchor)


def two(k, rest, kpos, rpos, ks=1.0, n1=None, last1=1.0, rs=None, n2=None, last2=1.0, wave=None, shiver=None,
        bob=0):
    """強調語 k(コーラル)と残り rest(こげ茶)の2語。rs=None なら rest は出さない。
    kpos/rpos は (中心x, 中心y, 文字サイズ, 傾き)。"""
    kx, ky, ksz, krot = kpos
    ws = [word(k, kx, ky + bob, ksz, CORAL, rot=krot, scale=ks, seed=1, count=n1, last=last1, wave=wave,
               shiver=shiver)]
    if rest and rs is not None:
        rx, ry, rsz, rrot = rpos
        ws.append(word(rest, rx, ry + bob, rsz, BROWN, rot=rrot, scale=rs, arc=0.2, seed=2, count=n2, last=last2,
                       shiver=shiver))
    return ws


B1, B2, S, J0, J1, J2 = inko.B1, inko.B2, inko.S, inko.J0, inko.J1, inko.J2
SAL, W_A, W_B, N1, N2 = inko.SAL, inko.W_A, inko.W_B, inko.N1, inko.N2
happy, blink = inko.happy, inko.blink
PEKO1, PEKO2 = ("peko", 272, 140, 28), ("peko", 272, 156, 32)


# 口パク: くちばしを丸いおわん形に開き、中に口(ピンクの楕円)を重ねる。
# 小さい部品なので手描きの揺らぎはかけない(揺らすと形がくずれる)。
BEAK_OPEN = "M1 2 L19 2 C19 12 14.5 19 10 19 C5.5 19 1 12 1 2 Z"
MOUTH = "M6 0.5 C9.5 0.5 11.5 2.5 11.5 5 C11.5 7.5 9.5 9.5 6 9.5 C2.5 9.5 0.5 7.5 0.5 5 C0.5 2.5 2.5 0.5 6 0.5 Z"


def talk(c):
    b = c["P15"]
    b.update(left=b["left"] - 1, w=20, h=20, d=BEAK_OPEN)
    mouth = dict(fill="#E8607A", stroke=None, sw=0, w=12, h=10, left=b["left"] + 4, top=b["top"] + 5,
                 d=MOUTH, rot=0)
    items = list(c.items())
    c.clear()
    for k, v in items:  # 口の中はくちばしの上に重ねる
        c[k] = v
        if k == "P15":
            c["P15m"] = mouth


def step(side):
    """足ぶみ: 片足を少し外へけり上げる(side=0 左足, 1 右足)。体の下に隠れないよう外側へずらす。"""
    def f(c):
        key, dx, rot = ("P2", -6, -25) if side == 0 else ("P3", 6, 25)
        if key in c:
            c[key]["left"] += dx
            c[key]["top"] -= 3
            c[key]["rot"] = c[key].get("rot", 0) + rot
    return f


def X(c):
    inko.eyes(c, "X")


def sh(dx):
    return inko.shake(dx)


# 01 承知しました: 「承」「知」を1文字ずつポン(B型)→「しました」がポン。敬礼。
P01 = dict(kpos=(98, 50, 68, -6), rpos=(176, 104, 40, -3))
f01 = lambda **k: two("承知", "しました", **P01, **k)
SPK01 = [("spark", 282, 116, 12), ("spark", 108, 150, 9)]
# 02 ありがとう/ございます: 分割出し(A型)。「ございます」は丸ごとポン、ハートがふわっと上がる。
P02 = dict(kpos=(152, 42, 46, -6), rpos=(180, 100, 36, -3))
f02 = lambda **k: two("ありがとう", "ございます", **P02, **k)
# 03 お疲れさま/です: 分割出し(A型)。「お疲れさま」を書いていき、「です」がポン。手をふる。
P03 = dict(kpos=(142, 42, 48, -6), rpos=(244, 104, 48, 6))
f03 = lambda **k: two("お疲れさま", "です", **P03, **k)
# 05 了解/です！: 1文字ずつポン(B型)+ジャンプ。
P05 = dict(kpos=(100, 56, 64, -8), rpos=(222, 108, 44, -4))
f05 = lambda **k: two("了解", "です！", **P05, **k)
SPK05 = [("spark", 290, 150, 11), ("spark", 112, 160, 8)]
# 06 すみません: 1文字ずつ出て、ぷるぷる震える(C型)。汗。
P06 = dict(kpos=(150, 48, 52, -4), rpos=(0, 0, 0, 0))
f06 = lambda **k: two("すみません", "", **P06, **k)
SW06 = [("sweat", 118, 150, 13), ("sweat", 284, 136, 11)]
SW06b = [("sweat", 112, 158, 13), ("sweat", 290, 128, 11)]
# 07 おはよう/ございます: 強調語が跳ねる(C型)。ばんざい。
P07 = dict(kpos=(134, 44, 52, -6), rpos=(182, 102, 36, -3))
f07 = lambda **k: two("おはよう", "ございます", **P07, **k)
SPK07 = [("spark", 290, 128, 12), ("spark", 104, 156, 10)]
SPK07b = [("spark", 294, 120, 9), ("spark", 100, 150, 13)]
# 08 おやすみ/なさい: 強調語がゆっくり揺れ(C型)、「なさい」を書いていく。Z が浮かぶ。
P08 = dict(kpos=(134, 46, 52, -6), rpos=(202, 104, 40, -3))
f08 = lambda **k: two("おやすみ", "なさい", **P08, **k)


def zz(i):
    return [("z", 272 + i * 2, 146 - i * 4, 24 + i % 2 * 4), ("z", 288 + i, 120 - i * 3, 16)]


def yoro(scale=1.0, n2=0, bob=0, dx=0):
    """「よろしく」(強調語・コーラル)は左上にポンと出し、「お願いします」は頭に重ねて左から書いていく。
    dx: 大きくポンと出すコマで左端が切れないよう右へずらす量。"""
    ws = [word("よろしく", 120 + dx, 42 + bob, 54, CORAL, rot=-6, scale=scale, seed=1)]
    if n2:  # 2行目はキャラの頭に少し重ねて、文字を前に出す
        ws.append(word("お願いします", 168, 98 + bob, 38, BROWN, rot=-3, arc=0.2, seed=2, count=n2))
    return ws


STAMPS = {
    "01": [kf([SAL], f01(rs=1), SPK01),
           kf([S]),
           kf([S], f01(n1=1, last1=1.35)),
           kf([S], f01(n1=2, last1=1.35)),
           kf([SAL], f01()),
           kf([SAL], f01(rs=1.25), SPK01[:1]),
           kf([SAL], f01(rs=0.95), SPK01),
           kf([SAL], f01(rs=1), SPK01),
           kf([SAL], f01(rs=1, bob=1), [("spark", 284, 114, 14), ("spark", 108, 150, 11)]),
           kf([SAL], f01(rs=1), SPK01),
           kf([SAL], f01(rs=1, bob=1), [("spark", 284, 114, 14), ("spark", 108, 150, 11)]),
           kf([SAL], f01(rs=1), SPK01)],
    "02": [kf([B2, happy], f02(rs=1), [("heart", 282, 132, 14), ("heart", 110, 156, 10)]),
           kf([S, happy]),
           kf([S, happy], f02(ks=1.08)),
           kf([S, happy], f02(ks=0.96)),
           kf([S, happy], f02()),
           kf([B1, happy], f02(rs=1.18)),
           kf([B2, happy], f02(rs=0.94)),
           kf([B2, happy], f02(rs=1), [("heart", 280, 150, 9)]),
           kf([B2, happy], f02(rs=1), [("heart", 281, 142, 12), ("heart", 112, 168, 8)]),
           kf([B2, happy], f02(rs=1, bob=1), [("heart", 282, 134, 14), ("heart", 111, 160, 10)]),
           kf([B1, happy], f02(rs=1, bob=1), [("heart", 283, 126, 15), ("heart", 110, 152, 11)]),
           kf([B2, happy], f02(rs=1), [("heart", 282, 132, 14), ("heart", 110, 156, 10)])],
    "03": [kf([W_A], f03(rs=1)),
           kf([S, happy]),
           kf([W_A], f03(n1=2)),
           kf([W_B], f03(n1=4)),
           kf([W_A], f03()),
           kf([W_B], f03(rs=1.2)),
           kf([W_A], f03(rs=0.95), [("note", 116, 156, 26)]),
           kf([W_B], f03(rs=1), [("note", 112, 150, 28)]),
           kf([W_A], f03(rs=1, bob=1), [("note", 110, 144, 26)]),
           kf([W_B], f03(rs=1)),
           kf([W_A], f03(rs=1, bob=1)),
           kf([W_A], f03(rs=1))],
    "04": [kf([B1], yoro(1, 6), [PEKO1]),
           kf([S, blink]),
           kf([S, blink], yoro(1.12, dx=10)),
           kf([S, blink], yoro(0.96)),
           kf([S, blink], yoro(1.0)),
           kf([B1], yoro(1.0, 2)),
           kf([B2], yoro(1.0, 4)),
           kf([B2], yoro(1.0, 6), [PEKO2]),
           kf([B2], yoro(1.0, 6, bob=2), [PEKO2]),
           kf([B1], yoro(1.0, 6, bob=1), [("heart", 286, 140, 13)]),
           kf([B1], yoro(1.0, 6), [("heart", 288, 134, 16)]),
           kf([B1], yoro(1, 6), [PEKO1])],
    "05": [kf([SAL], f05(rs=1), SPK05),
           kf([J0, lambda c: SAL(c, 8)]),
           kf([J1, lambda c: SAL(c, -14)], f05(n1=1, last1=1.25)),
           kf([SAL, happy, J2], f05(n1=2, last1=1.25)),
           kf([SAL, happy, J2], f05()),
           kf([J1, lambda c: SAL(c, -14)], f05(rs=1.2)),
           kf([J0, lambda c: SAL(c, 8)], f05(rs=0.95), SPK05),
           kf([SAL], f05(rs=1), SPK05),
           kf([SAL], f05(rs=1, wave=(3, 0)), [("spark", 292, 146, 13), ("spark", 112, 158, 10)]),
           kf([SAL], f05(rs=1, wave=(3, 1.6)), SPK05),
           kf([SAL], f05(rs=1, wave=(3, 3.2)), [("spark", 292, 146, 13), ("spark", 112, 158, 10)]),
           kf([SAL], f05(rs=1), SPK05)],
    "06": [kf([B1, X], f06(), SW06),
           kf([B1, X]),
           kf([B1, X], f06(n1=2, last1=1.3)),
           kf([B1, X, sh(-3)], f06(n1=3, last1=1.3, shiver=(2, 4, 1)), SW06[:1]),
           kf([B1, X, sh(3)], f06(n1=5, last1=1.3, shiver=(2, 4, 2)), SW06),
           kf([B1, X, sh(-3)], f06(shiver=(2, 4, 3)), SW06b),
           kf([B1, X, sh(3)], f06(shiver=(2, 4, 4)), SW06),
           kf([B1, X, sh(-3)], f06(shiver=(2, 4, 5)), SW06b),
           kf([B1, X, sh(3)], f06(shiver=(2, 4, 6)), SW06),
           kf([B1, X, sh(-2)], f06(shiver=(1, 2, 7)), SW06b),
           kf([B1, X, sh(2)], f06(shiver=(1, 2, 8)), SW06),
           kf([B1, X], f06(), SW06)],
    "07": [kf([N2], f07(rs=1), SPK07),
           kf([S]),
           kf([N1], f07(ks=1.08)),
           kf([N2, happy], f07(wave=(4, 0)), SPK07),
           kf([N2, happy], f07(wave=(4, 1.6), rs=1, n2=3), SPK07b),
           kf([N2, happy], f07(wave=(4, 3.2), rs=1), SPK07),
           kf([N1], f07(wave=(4, 4.8), rs=1), SPK07b),
           kf([N2, happy], f07(wave=(4, 0), rs=1), SPK07),
           kf([N2, happy], f07(wave=(4, 1.6), rs=1), SPK07b),
           kf([N1], f07(wave=(4, 3.2), rs=1), SPK07),
           kf([N2, happy], f07(wave=(4, 4.8), rs=1), SPK07b),
           kf([N2], f07(rs=1), SPK07)],
    "08": [kf([inko.sway(0, 0)], f08(rs=1), zz(0)),
           kf([blink]),
           kf([blink], f08(ks=1.06)),
           kf([inko.sway(4, 5)], f08(wave=(2, 0))),
           kf([inko.sway(6, 8)], f08(wave=(2, 0.8), rs=1, n2=1), zz(1)[:1]),
           kf([inko.sway(4, 5)], f08(wave=(2, 1.6), rs=1, n2=2), zz(2)[:1]),
           kf([inko.sway(0, 0)], f08(wave=(2, 2.4), rs=1), zz(3)),
           kf([inko.sway(-4, -5)], f08(wave=(2, 3.2), rs=1), zz(4)),
           kf([inko.sway(-6, -8)], f08(wave=(2, 4.0), rs=1), zz(5)),
           kf([inko.sway(-4, -5)], f08(wave=(2, 4.8), rs=1), zz(6)),
           kf([inko.sway(0, 0)], f08(wave=(2, 5.6), rs=1), zz(0)),
           kf([inko.sway(0, 0)], f08(rs=1), zz(0))],
}


# 口パク: セリフが出ているあいだ、1コマおきに口を開ける(1コマ目=完成形は閉じたまま)
TALK_FRAMES = (2, 4, 6, 8, 10)
for frames in STAMPS.values():
    for i in TALK_FRAMES:
        frames[i]["poses"] = frames[i]["poses"] + [talk]
# 足ぶみ: 2コマ目から左右の足を交互に少し上げる(1コマ目=完成形は両足をつけたまま)
STEP_FRAMES = {1: 0, 3: 1, 5: 0, 7: 1, 9: 0, 11: 1}
for frames in STAMPS.values():
    for i, side in STEP_FRAMES.items():
        frames[i]["poses"] = frames[i]["poses"] + [step(side)]


# ---- 出力 --------------------------------------------------------------------

def origin(i):
    return (i % COLS) * CW, (i // COLS) * CH


def chara_svg(frames):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{CW * COLS}" height="{CH * ROWS}">']
    for i, fr in enumerate(frames):
        x0, y0 = origin(i)
        for e in chara_elems(fr["poses"], fr["scale"], fr["anchor"]):
            vw, vh = e.get("vw", e["w"]), e.get("vh", e["h"])
            tf = (f'translate({x0 + e["left"]:.1f} {y0 + e["top"]:.1f}) '
                  f'rotate({e["rot"]} {e["w"] / 2:.1f} {e["h"] / 2:.1f}) scale({e["w"] / vw:.4f} {e["h"] / vh:.4f})')
            stroke = f'stroke="{e["stroke"]}" stroke-width="{e["sw"]}"' if e["sw"] else 'stroke="none"'
            out.append(f'<path transform="{tf}" d="{e["d"]}" fill="{e["fill"]}" {stroke} stroke-linejoin="round"/>')
    out.append("</svg>")
    return "\n".join(out)


def chara_png(frames, path):
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "c.svg"
        svg.write_text(chara_svg(frames))
        subprocess.run([inko.CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={CW * COLS},{CH * ROWS + 160}", "--default-background-color=00000000",
                        f"--screenshot={path}", svg.as_uri()], check=True, capture_output=True)
    Image.open(path).crop((0, 0, CW * COLS, CH * ROWS)).save(path)


def text_png(frames, path):
    layer = Image.new("RGBA", (CW * COLS, CH * ROWS), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        x0, y0 = origin(i)
        cell = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        draw_marks(cell, fr["marks"], 0, 0)
        for w in fr["words"]:
            draw_word(cell, w, 0, 0)
        layer.alpha_composite(cell, (x0, y0))  # はみ出しはコマ内で切る
    layer.save(path)


def compact(d):
    """Canva に送るパスは座標を整数に丸めて小さくする(見た目はほぼ変わらない)。"""
    return re.sub(r"-?\d+\.\d+", lambda m: str(round(float(m.group()))), d)


def to_ops(frames, page_id):
    """キャラの図形を Canva の insert_shape 操作にする(12コマ分、4x3 のマス目に配置)。"""
    ops = []
    for i, fr in enumerate(frames):
        x0, y0 = origin(i)
        for e in chara_elems(fr["poses"], fr["scale"], fr["anchor"]):
            op = dict(type="insert_shape", page_id=page_id,
                      left=round(x0 + e["left"], 1), top=round(y0 + e["top"], 1),
                      width=round(e["w"], 1), height=round(e["h"], 1), path=compact(e["d"]),
                      view_box_width=round(e.get("vw", e["w"]), 1), view_box_height=round(e.get("vh", e["h"]), 1),
                      color=e["fill"])
            if e["sw"]:
                op.update(stroke_color=e["stroke"], stroke_weight=e["sw"])
            if e["rot"]:
                op["rotation"] = e["rot"]
            ops.append(op)
    return ops


def ellipse_d(w, h):
    """楕円を C だけで描くパス(A を使わない形に置き換える用)。"""
    k = 0.5523
    rx, ry, cx, cy = w / 2, h / 2, w / 2, h / 2
    return (f"M{cx} {cy - ry} C{cx + k * rx} {cy - ry} {cx + rx} {cy - k * ry} {cx + rx} {cy} "
            f"C{cx + rx} {cy + k * ry} {cx + k * rx} {cy + ry} {cx} {cy + ry} "
            f"C{cx - k * rx} {cy + ry} {cx - rx} {cy + k * ry} {cx - rx} {cy} "
            f"C{cx - rx} {cy - k * ry} {cx - k * rx} {cy - ry} {cx} {cy - ry} Z")


def place(e, x0, y0):
    """部品のパスを、ページ全体の座標に変換した文字列にする(移動・回転・拡大を座標に焼き込む)。"""
    vw, vh = e.get("vw", e["w"]), e.get("vh", e["h"])
    d = ellipse_d(vw, vh) if "A" in e["d"] else e["d"]
    sx, sy = e["w"] / vw, e["h"] / vh
    r = math.radians(e["rot"])
    cr, sr = math.cos(r), math.sin(r)
    hx, hy = e["w"] / 2, e["h"] / 2

    def tf(m):
        x, y = float(m.group(1)) * sx - hx, float(m.group(2)) * sy - hy
        return f"{x0 + e['left'] + hx + x * cr - y * sr:.0f} {y0 + e['top'] + hy + x * sr + y * cr:.0f}"
    return re.sub(r"(-?\d+(?:\.\d+)?)[ ,](-?\d+(?:\.\d+)?)", tf, d)


def relative(d):
    """整数座標の絶対パス(M/L/C/Z)を、相対座標(m/l/c/z)の短い書き方にする。"""
    out, cur, start = [], (0, 0), (0, 0)
    for cmd, args in re.findall(r"([MLCZ])([^MLCZ]*)", d):
        v = [int(float(x)) for x in re.findall(r"-?\d+(?:\.\d+)?", args)]
        if cmd == "M":
            cur = start = (v[0], v[1])
            out.append(f"M{v[0]} {v[1]}")
        elif cmd == "Z":
            out.append("z")
            cur = start
        else:
            n = 2 if cmd == "L" else 6
            for j in range(0, len(v), n):
                seg = v[j:j + n]
                rel = [seg[k] - cur[k % 2] for k in range(n)]
                out.append(cmd.lower() + " ".join(map(str, rel)))
                cur = (seg[-2], seg[-1])
    return re.sub(r" -", "-", "".join(out))


def to_ops_merged(frames, page_id):
    """同じ役割・同じ色の部品を、12コマ分まとめて1つの図形にする(ページ全体で十数個の図形になる)。
    コマどうしは重ならないので、重なり順は部品の役割ごとの順番で保たれる。"""
    groups = {}
    for i, fr in enumerate(frames):
        x0, y0 = origin(i)
        c = copy.deepcopy(inko.BASE)
        for p in fr["poses"]:
            p(c)
        keys = list(soften(c).keys())
        for key, e in zip(keys, chara_elems(fr["poses"], fr["scale"], fr["anchor"])):
            gk = (inko_order(key), key[:4] if key.startswith("SAL") else key, e["fill"], e["stroke"], e["sw"])
            groups.setdefault(gk, []).append(place(e, x0, y0))
    W, H = CW * COLS, CH * ROWS
    merged = []  # 重なり順で隣り合う同じ見た目の部品(両足・両目など)はさらに1つにまとめる
    for gk in sorted(groups):
        style = gk[2:]
        if merged and merged[-1][0] == style:
            merged[-1][1].extend(groups[gk])
        else:
            merged.append((style, list(groups[gk])))
    ops = []
    for (fill, stroke, sw), paths in merged:
        op = dict(type="insert_shape", page_id=page_id, left=0, top=0, width=W, height=H,
                  path="".join(relative(g) for g in paths), view_box_width=W, view_box_height=H, color=fill)
        if sw:
            op.update(stroke_color=stroke, stroke_weight=sw)
        ops.append(op)
    return ops


ORDER = list(inko.BASE)


def inko_order(key):
    if key == "P15m":  # 口の中はくちばしのすぐ上
        return ORDER.index("P15") + 0.5
    return ORDER.index(key) if key in ORDER else len(ORDER)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", choices=sorted(STAMPS))
    ap.add_argument("--chara-png", help="キャラだけの透過シート")
    ap.add_argument("--text-png", help="セリフと飾りだけの透過シート(Canva にアップロードする)")
    ap.add_argument("--png", help="緑背景で合成したシート(確認用)")
    ap.add_argument("--ops", help="Canva 操作 JSON の保存先(キャラの図形)")
    ap.add_argument("--page", default="PAGE_ID", help="Canva のページID")
    a = ap.parse_args()
    frames = STAMPS[a.stamp]
    if a.ops:
        import json
        ops = to_ops_merged(frames, a.page)
        Path(a.ops).write_text(json.dumps(ops, ensure_ascii=False, separators=(",", ":")))
        print(f"Canva操作: {a.ops}({len(ops)}個, {Path(a.ops).stat().st_size // 1024}KB)")
    with tempfile.TemporaryDirectory() as tmp:
        cp = a.chara_png or f"{tmp}/c.png"
        tp = a.text_png or f"{tmp}/t.png"
        chara_png(frames, cp)
        text_png(frames, tp)
        if a.png:
            sheet = Image.new("RGBA", (CW * COLS, CH * ROWS), inko.BG)
            sheet.alpha_composite(Image.open(cp).convert("RGBA"))
            sheet.alpha_composite(Image.open(tp).convert("RGBA"))
            sheet.convert("RGB").save(a.png)
            print(f"シート: {a.png}")


if __name__ == "__main__":
    main()
