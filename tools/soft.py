#!/usr/bin/env python3
"""ていねいインコ「ゆるふわ版」: 線をやわらかくしたキャラと、手書き風のセリフを作る。

  試作プレビュー : python3 tools/soft.py 04 --png out.png --gif out.gif

inko.py のパーツ・ポーズをそのまま使い、見た目だけを変える。
- キャラ: 線を濃い茶→やわらかい茶色にして細くし、輪郭を手描き風に少し揺らす。
  体はふちを小さく波打たせて「ふわふわ」に見せる。ほっぺはピンク。
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

LINE = "#7A5040"      # やわらかい茶色の線
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


def wobble(d, seed, amt=0.7):
    """パスの座標を少しずらして手描きの揺らぎを出す。"""
    rnd = random.Random(seed)
    return re.sub(r"-?\d+(?:\.\d+)?", lambda m: f"{float(m.group()) + rnd.uniform(-amt, amt):.1f}", d)


def soften(c):
    for key, e in c.items():
        if e["d"] in BODY_PATHS:
            e["d"] = scallop(e.get("vw", e["w"]), e.get("vh", e["h"]))
        elif e["sw"] and key not in ("P0",):
            e["d"] = wobble(e["d"], key)
        if e["stroke"] == inko.INK:
            e["stroke"] = LINE
            e["sw"] = round(e["sw"] * 0.75, 1)
        if e["fill"] == inko.INK:
            e["fill"] = EYE
        if key in ("P12", "P13"):
            e["fill"] = CHEEK
        e["fill"] = FILLS.get(e["fill"], e["fill"])
        if key in ("P8", "P9", "P10", "P11"):
            e["top"] += 5  # 目を少し下げて幼く
        if key == "P0":
            e["sw"] = 10
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

def word(text, cx, cy, size, color, rot=0, scale=1.0, arc=0, seed=0, vertical=False, count=None):
    """count を指定すると先頭から count 文字だけ出す(書いているように見せる)。"""
    return dict(text=text, cx=cx, cy=cy, size=size, color=color, rot=rot, scale=scale, arc=arc, seed=seed,
                vertical=vertical, count=len(text) if count is None else count)


def draw_word(layer, w, ox, oy, outline=9):
    """一文字ずつ、少し傾け・上下にずらして置く。arc>0 で笑った口のような弧になる。"""
    size = round(w["size"] * w["scale"])
    font = ImageFont.truetype(str(HAND_FONT), size)
    rnd = random.Random(w["seed"])
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
        if w["vertical"]:
            lx, ly = jit[0] - w["arc"] * size * (4 * t * t - 1) * 0.5, lx
        x = ox + w["cx"] + lx * math.cos(r) - ly * math.sin(r)
        y = oy + w["cy"] + lx * math.sin(r) + ly * math.cos(r)
        pad = outline + 6
        g = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(g)
        pos = (pad + size / 2, pad + size / 2)
        dr.text(pos, ch, font=font, anchor="mm", fill=RIM, stroke_width=outline + 2, stroke_fill=RIM)
        dr.text(pos, ch, font=font, anchor="mm", fill=w["color"], stroke_width=outline, stroke_fill="white")
        g = g.rotate(-(w["rot"] + jit[1]), resample=Image.BICUBIC, expand=True)
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


# ---- スタンプの台本(12コマ) -----------------------------------------------

def kf(poses, words=(), marks=(), scale=1.25, anchor=(198, 246)):
    return dict(poses=poses, words=list(words), marks=list(marks), scale=scale, anchor=anchor)


def yoro(scale=1.0, n2=0, bob=0):
    """「よろしく」(強調語・コーラル)は左上にポンと出し、「お願いします」は頭に重ねて左から書いていく。"""
    ws = [word("よろしく", 120, 42 + bob, 54, CORAL, rot=-6, scale=scale, seed=1)]
    if n2:  # 2行目はキャラの頭に少し重ねて、文字を前に出す
        ws.append(word("お願いします", 168, 98 + bob, 38, BROWN, rot=-3, arc=0.2, seed=2, count=n2))
    return ws


B1, B2, S = inko.B1, inko.B2, inko.S
PEKO1, PEKO2 = ("peko", 272, 140, 28), ("peko", 272, 156, 32)
STAMPS = {
    "04": [kf([B1], yoro(1, 6), [PEKO1]),
           kf([S]),
           kf([S], yoro(1.12)),
           kf([S], yoro(0.96)),
           kf([S], yoro(1.0)),
           kf([B1], yoro(1.0, 2)),
           kf([B2], yoro(1.0, 4)),
           kf([B2], yoro(1.0, 6), [PEKO2]),
           kf([B2], yoro(1.0, 6, bob=2), [PEKO2]),
           kf([B1], yoro(1.0, 6, bob=1), [("heart", 286, 140, 13)]),
           kf([B1], yoro(1.0, 6), [("heart", 288, 134, 16)]),
           kf([B1], yoro(1, 6), [PEKO1])],
}


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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", choices=sorted(STAMPS))
    ap.add_argument("--chara-png", help="キャラだけの透過シート")
    ap.add_argument("--text-png", help="セリフと飾りだけの透過シート(Canva にアップロードする)")
    ap.add_argument("--png", help="緑背景で合成したシート(確認用)")
    a = ap.parse_args()
    frames = STAMPS[a.stamp]
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
