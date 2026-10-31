#!/usr/bin/env python3
"""ていねいインコ(work/set01/plan.md)を、Canva の図形だけで描くためのデータを作る。

  プレビュー : python3 tools/inko.py 01 --png work/set01/preview/01.png
  Canva操作  : python3 tools/inko.py 01 --ops ops.json --page PAGE_ID --frames 1,2

キャラの部品・ポーズ・セリフは企画書の 5〜7 章をそのままコードにしたもの。
セリフは Canva の API でフォントを選べないため、M PLUS Rounded 1c の字形を
SVG パス(M/L/C/Z のみ)に変換して図形として描く。
"""
import argparse
import copy
import math
import json
import subprocess
import tempfile
from pathlib import Path

from fontTools.pens.basePen import BasePen
from PIL import Image
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets/fonts/MPLUSRounded1c-ExtraBold.ttf"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

CELL_W, CELL_H = 320, 270
BG = "#00FF00"
INK, NAVY, WHITE = "#3A2E39", "#233A6B", "#FFFFFF"
TEXT_OUTLINE = 10  # 白フチの線幅(外側に半分の5pxが出る)


def part(fill, stroke, sw, w, h, left, top, d):
    return dict(fill=fill, stroke=stroke, sw=sw, w=w, h=h, left=left, top=top, d=d, rot=0)


BODY = "M55 2 C85 2 106 26 106 58 C106 90 84 110 55 110 C26 110 4 90 4 58 C4 26 25 2 55 2 Z"
FOOT = "M2 11 C2 5 6 2 12 2 C18 2 22 5 22 11 Z"
EYE = "M6 1 C9.5 1 11 4.5 11 8 C11 11.5 9.5 15 6 15 C2.5 15 1 11.5 1 8 C1 4.5 2.5 1 6 1 Z"
HIGHLIGHT = "M2.5 0.5 A2 2 0 1 1 2.5 4.5 A2 2 0 1 1 2.5 0.5 Z"
CHEEK = "M8 1 C12.5 1 15 3 15 5 C15 7 12.5 9 8 9 C3.5 9 1 7 1 5 C1 3 3.5 1 8 1 Z"

# 5-2 基本パーツ(置く順 = 下から上)
BASE = {
    "P0": part(WHITE, WHITE, 12, 110, 112, 105, 140, BODY),
    "P1": part("#FFE066", INK, 3, 30, 22, 150, 124,
               "M8 21 C4 14 4 6 10 1 C12 7 14 12 15 16 C17 10 21 5 28 4 C26 11 23 17 20 21 Z"),
    "P2": part("#F49CA8", INK, 2.5, 24, 12, 134, 246, FOOT),
    "P3": part("#F49CA8", INK, 2.5, 24, 12, 162, 246, FOOT),
    "P4": part("#FFE066", INK, 4, 110, 112, 105, 140, BODY),
    "P5": part("#FFF6D6", None, 0, 70, 56, 125, 190,
               "M35 2 C55 2 68 18 68 30 C68 46 54 54 35 54 C16 54 2 46 2 30 C2 18 15 2 35 2 Z"),
    "P6": part("#F5B83D", INK, 3, 30, 52, 98, 186,
               "M22 2 C30 10 29 34 20 48 C16 52 8 50 6 44 C2 30 8 10 22 2 Z"),
    "P7": part("#F5B83D", INK, 3, 30, 52, 192, 186,
               "M8 2 C0 10 1 34 10 48 C14 52 22 50 24 44 C28 30 22 10 8 2 Z"),
    "P8": part(INK, None, 0, 12, 16, 134, 170, EYE),
    "P9": part(INK, None, 0, 12, 16, 174, 170, EYE),
    "P10": part(WHITE, None, 0, 5, 5, 137, 172, HIGHLIGHT),
    "P11": part(WHITE, None, 0, 5, 5, 177, 172, HIGHLIGHT),
    "P12": part("#6F7FD8", None, 0, 16, 10, 118, 190, CHEEK),
    "P13": part("#6F7FD8", None, 0, 16, 10, 186, 190, CHEEK),
    "P14": part("#7FA7E8", INK, 2, 20, 8, 150, 180, "M3 7 C3 2 7 1 10 1 C13 1 17 2 17 7 Z"),
    "P15": part("#FF9F43", INK, 2.5, 18, 18, 151, 186, "M1 2 L17 2 C17 9 12 16 9 17 C6 16 1 9 1 2 Z"),
}
FACE = ["P8", "P9", "P10", "P11", "P12", "P13", "P14", "P15"]
WINGS, FEET = ["P6", "P7"], ["P2", "P3"]

# 5-3 差し替えパス: (width, height, path)
ALT = {
    "BODY_S": (110, 100, "M55 2 C85 2 108 24 108 52 C108 80 84 98 55 98 C26 98 2 80 2 52 C2 24 25 2 55 2 Z"),
    "BODY_SS": (110, 88, "M55 2 C86 2 108 22 108 46 C108 70 84 86 55 86 C26 86 2 70 2 46 C2 22 24 2 55 2 Z"),
    "BODY_L": (100, 124, "M50 2 C77 2 96 28 96 64 C96 98 76 122 50 122 C24 122 4 98 4 64 C4 28 23 2 50 2 Z"),
    "BELLY_S": (70, 44, "M35 2 C55 2 68 14 68 24 C68 36 54 42 35 42 C16 42 2 36 2 24 C2 14 15 2 35 2 Z"),
    "E_HAPPY": (14, 10, "M1 9 C3 1 11 1 13 9 L11 9 C9.5 5 4.5 5 3 9 Z"),
    "E_CLOSE": (14, 10, "M1 1 C3 9 11 9 13 1 L11 1 C9.5 5 4.5 5 3 1 Z"),
    "E_X_L": (14, 14, "M1 2 L13 7 L1 12 L1 9 L8 7 L1 5 Z"),
    "E_X_R": (14, 14, "M13 2 L1 7 L13 12 L13 9 L6 7 L13 5 Z"),
}
SWEAT = ("#8CC8F5", INK, 2, 12, 18,
         "M6 1 C9 6 11 10 11 12 C11 15 9 17 6 17 C3 17 1 15 1 12 C1 10 3 6 6 1 Z")
SPARK = ("#FFD23F", INK, 2, 22, 22,
         "M11 1 C12 8 14 10 21 11 C14 12 12 14 11 21 C10 14 8 12 1 11 C8 10 10 8 11 1 Z")


# ---- ポーズ部品の操作 ---------------------------------------------------------

def move(c, ids, dx=0, dy=0):
    for i in ids:
        if i in c:
            c[i]["left"] += dx
            c[i]["top"] += dy


def body(c, key, left, top):
    w, h, d = ALT[key]
    for i in ("P0", "P4"):
        c[i].update(w=w, h=h, d=d, left=left, top=top)


def wing(c, i, cx, cy, rot):
    p = c[i]
    p.update(left=cx - p["w"] / 2, top=cy - p["h"] / 2, rot=rot)


def eyes(c, kind, dy=0):
    """目を差し替える(ハイライトは消す)。kind: E_HAPPY / E_CLOSE / X
    おじぎ等で顔が動いていても、くちばし(P14)の位置から同じだけずらして顔について行かせる。"""
    c.pop("P10", None)
    c.pop("P11", None)
    ox, oy = c["P14"]["left"] - BASE["P14"]["left"], c["P14"]["top"] - BASE["P14"]["top"]
    if kind == "X":
        specs = [("P8", "E_X_L", 133, 171), ("P9", "E_X_R", 173, 171)]
    else:
        specs = [("P8", kind, 133, 173), ("P9", kind, 173, 173)]
    for i, key, left, top in specs:
        w, h, d = ALT[key]
        c[i].update(w=w, h=h, d=d, left=left + ox, top=top + oy + dy)


# 5-4 ポーズ(基本ポーズへの変更として順に適用する)
def S(c): pass
def happy(c): eyes(c, "E_HAPPY")
def blink(c): eyes(c, "E_CLOSE")


def B1(c):
    body(c, "BODY_S", 105, 152)
    move(c, ["P1"], dy=12)
    eyes(c, "E_CLOSE")
    move(c, FACE, dy=16)
    move(c, ["P5"], dy=4)
    wing(c, "P6", 116, 218, -20)
    wing(c, "P7", 204, 218, 20)


def B2(c):
    body(c, "BODY_SS", 105, 164)
    move(c, ["P1"], dy=24)
    eyes(c, "E_CLOSE")
    move(c, FACE, dy=30)
    w, h, d = ALT["BELLY_S"]
    c["P5"].update(w=w, h=h, d=d, left=125, top=204)
    wing(c, "P6", 120, 224, -35)
    wing(c, "P7", 200, 224, 35)


def J0(c):
    body(c, "BODY_S", 105, 152)
    move(c, ["P1"], dy=12)
    move(c, FACE, dy=12)
    move(c, ["P5"], dy=4)
    move(c, WINGS, dy=8)


def J1(c):
    body(c, "BODY_L", 110, 118)
    move(c, ["P1"], dy=-22)
    move(c, FACE, dy=-18)
    move(c, ["P5"], dy=-10)
    move(c, WINGS, dy=-14)
    move(c, FEET, dy=-14)


def J2(c): move(c, list(c), dy=-22)
def SAL(c, dy=0):
    """敬礼: 右羽を肩(体の右側)から上げ、羽先をおでこに当てる(羽は30x64に伸ばす)。
    羽の付け根(上端)が肩、ギザギザの羽先(下端)がおでこに来るよう 140° 回す。"""
    c["P7"].update(h=64, vw=30, vh=52)
    wing(c, "P7", 194, 186 + dy, 140)
    # 羽先の右上に「ビシッ」の強調線を3本(放射状)
    for k, ang in enumerate((-75, -40, -5)):
        r = math.radians(ang)
        cx, cy = 204 + 16 * math.cos(r), 150 + dy + 16 * math.sin(r)
        c[f"SAL{k}"] = dict(fill=INK, stroke=None, sw=0, w=10, h=3, left=cx - 5, top=cy - 1.5,
                            d="M1.5 0 L8.5 0 A1.5 1.5 0 0 1 8.5 3 L1.5 3 A1.5 1.5 0 0 1 1.5 0 Z", rot=ang)
def W_A(c): wing(c, "P7", 215, 180, -150); happy(c)
def W_B(c): wing(c, "P7", 228, 184, -115); happy(c)
def N1(c): wing(c, "P6", 100, 190, 90); wing(c, "P7", 220, 190, -90)


def N2(c):
    body(c, "BODY_L", 110, 128)
    move(c, ["P1"], dy=-12)
    happy(c)
    move(c, FACE, dy=-8)
    move(c, ["P5"], dy=-2)
    wing(c, "P6", 110, 176, 160)
    wing(c, "P7", 210, 176, -160)


def shake(dx):
    return lambda c: move(c, list(c), dx=dx)


def sway(dx, rot):
    def f(c):
        eyes(c, "E_CLOSE")
        move(c, FACE + ["P1"], dx=dx)
        c["P1"]["rot"] = rot
    return f


# ---- セリフ(字形 → 図形) ---------------------------------------------------

class CubicPen(BasePen):
    """2次ベジェを3次に直して M/L/C/Z だけのパスにする。"""

    def __init__(self, glyphset, tf):
        super().__init__(glyphset)
        self.tf, self.cmds, self.cur = tf, [], None

    def _pt(self, p):
        return self.tf(*p)

    def _moveTo(self, p):
        self.cur = p
        self.cmds.append(("M", [self._pt(p)]))

    def _lineTo(self, p):
        self.cur = p
        self.cmds.append(("L", [self._pt(p)]))

    def _curveToOne(self, p1, p2, p3):
        self.cur = p3
        self.cmds.append(("C", [self._pt(p1), self._pt(p2), self._pt(p3)]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur
        c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
        c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
        self._curveToOne(c1, c2, p2)

    def _closePath(self):
        self.cmds.append(("Z", []))


_font = None


def text_paths(lines, size, cx, cy, lh=1.12, pad=8):
    """セリフを (left, top, w, h, path) にする。座標はコマ内、path は要素の左上が原点。"""
    global _font
    _font = _font or TTFont(FONT)
    gs, cmap = _font.getGlyphSet(), _font.getBestCmap()
    upm = _font["head"].unitsPerEm
    asc, desc = _font["hhea"].ascent, _font["hhea"].descent
    sc = size / upm
    top = cy - len(lines) * size * lh / 2
    cmds = []
    for n, line in enumerate(lines):
        names = [cmap[ord(ch)] for ch in line]
        width = sum(gs[g].width for g in names) * sc
        x = cx - width / 2
        base = top + n * size * lh + (size * lh - (asc - desc) * sc) / 2 + asc * sc
        for g in names:
            pen = CubicPen(gs, lambda px, py, x=x: (x + px * sc, base - py * sc))
            gs[g].draw(pen)
            cmds += pen.cmds
            x += gs[g].width * sc
    pts = [p for _, ps in cmds for p in ps]
    minx, miny = min(p[0] for p in pts) - pad, min(p[1] for p in pts) - pad
    maxx, maxy = max(p[0] for p in pts) + pad, max(p[1] for p in pts) + pad
    # データ量を減らすため、整数に丸めた相対座標(m/l/c)で書く
    out, cur, start = [], (0, 0), (0, 0)
    for op, ps in cmds:
        if op == "Z":
            out.append("z")
            cur = start
            continue
        ps = [(round(px - minx), round(py - miny)) for px, py in ps]
        out.append(op.lower() + " ".join(f"{px - cur[0]} {py - cur[1]}" for px, py in ps))
        cur = ps[-1]
        if op == "M":
            start = cur
    d = "".join(out).replace(" -", "-")
    return minx, miny, maxx - minx, maxy - miny, d


def text_elems(lines, size, cx, cy, rot=0):
    left, top, w, h, d = text_paths(lines, size, cx, cy)
    common = dict(w=w, h=h, left=left, top=top, d=d, rot=rot)
    return [dict(common, fill=WHITE, stroke=WHITE, sw=TEXT_OUTLINE),
            dict(common, fill=NAVY, stroke=None, sw=0)]


# ---- スタンプ定義(企画書 7 章) -------------------------------------------------

def T(lines, size, dx=0, dy=0, rot=0, cy=None):
    """セリフ。cy は文字の中心(2行は y66、1行は top20 から計算)。"""
    if cy is None:
        cy = 66 if len(lines) == 2 else 20 + size * 1.12 / 2
    return dict(lines=lines, size=size, cx=160 + dx, cy=cy + dy, rot=rot)


def spark(cx, cy, s=22): return ("spark", cx, cy, s, s)
def sweat(cx, cy, w=12, h=18): return ("sweat", cx, cy, w, h)
def zz(x, y, size): return ("z", x, y, size)


def F(poses, text=None, extras=()):
    return dict(poses=poses, text=text, extras=list(extras))


L01, L02 = ["承知", "しました"], ["ありがとう", "ございます"]
L03, L04 = ["お疲れさま", "です"], ["よろしく", "お願いします"]
L05, L06 = ["了解です！"], ["すみません"]
L07, L08 = ["おはよう", "ございます"], ["おやすみ", "なさい"]
ONE = 20 + 56 * 1.12 / 2  # 1行セリフの中心(サイズ56基準で固定)

f06 = [F([B1, lambda c: eyes(c, "X"), shake(-3)], T(L06, 56, dx=2), [sweat(104, 150), sweat(216, 150)]),
       F([B1, lambda c: eyes(c, "X"), shake(3)], T(L06, 56, dx=-2), [sweat(94, 140), sweat(226, 140)]),
       F([B1, lambda c: eyes(c, "X"), shake(-3)], T(L06, 56, dx=2),
         [sweat(84, 130, 10, 15), sweat(236, 130, 10, 15)]),
       F([B1, lambda c: eyes(c, "X"), shake(3)], T(L06, 56, dx=-2))]
f07 = [F([N2], T(L07, 48, dy=-4), [spark(76, 156), spark(244, 156)]),
       F([N2], T(L07, 48, dy=-4), [spark(72, 182, 16), spark(248, 182, 16)])]
SW = [(0, 0), (4, 5), (6, 8), (4, 5), (0, 0), (-4, -5), (-6, -8), (-4, -5)]
ZZ = [[zz(228, 160, 28)], [zz(232, 152, 28)], [zz(236, 144, 28), zz(222, 168, 20)],
      [zz(240, 136, 28), zz(226, 160, 20)], [zz(230, 152, 20)], [zz(228, 160, 28), zz(234, 144, 20)],
      [zz(232, 152, 28)], [zz(236, 144, 28)]]

STAMPS = {
    "01": [F([SAL], T(L01, 48)), F([S]), F([J0]), F([S], T(L01, 29)),
           F([SAL], T(L01, 54, dy=4), [spark(58, 70), spark(262, 70)]),
           F([SAL], T(L01, 46)), F([SAL], T(L01, 50)), F([SAL], T(L01, 48))],
    "02": [F([B2], T(L02, 48, dy=6)), F([B2], T(L02, 48, dy=6)), F([B1], T(L02, 48, dy=3)),
           F([happy], T(L02, 48)), F([happy], T(L02, 48), [spark(88, 150), spark(232, 140)]),
           F([B1], T(L02, 48, dy=3), [spark(80, 172, 16), spark(240, 162, 16)]),
           F([B2], T(L02, 48, dy=6)), F([B2], T(L02, 48, dy=6))],
    "03": [F([W_A], T(L03, 48, rot=-3)) if i % 2 == 0 else F([W_B], T(L03, 48, rot=3)) for i in range(8)],
    "04": [F([p], T(L04, 48, dy=dy)) for p, dy in
           [(B2, 6), (B1, 3), (S, 0), (B1, 3), (B2, 6), (B1, 3), (S, 0), (B1, 3)]],
    "05": [F([SAL], T(L05, 56, cy=ONE)),
           F([J0, lambda c: SAL(c, 8)], T(L05, 54, dy=4, cy=ONE)),
           F([J1, lambda c: SAL(c, -14)], T(L05, 56, dy=-4, cy=ONE)),
           F([SAL, happy, J2], T(L05, 58, dy=-8, cy=ONE)),
           F([SAL, happy, J2], T(L05, 58, dy=-8, cy=ONE)),
           F([J1, lambda c: SAL(c, -14)], T(L05, 56, dy=-4, cy=ONE)),
           F([J0, lambda c: SAL(c, 8)], T(L05, 54, dy=4, cy=ONE)),
           F([SAL], T(L05, 56, cy=ONE))],
    "06": f06 + f06,
    "07": f07 + [F([N1], T(L07, 48, dy=-2)), F([blink], T(L07, 48)), F([S], T(L07, 48)),
                 F([N1], T(L07, 48, dy=-2))] + f07,
    "08": [F([sway(dx, r)], T(L08, 48, rot=tr), ZZ[i])
           for i, ((dx, r), tr) in enumerate(zip(SW, [0, 1, 2, 1, 0, -1, -2, -1]))],
}


def frame_elems(fr, layer="all"):
    """layer: all / chara(図形のみ) / text(セリフとZのみ)"""
    c = copy.deepcopy(BASE)
    for p in fr["poses"]:
        p(c)
    elems = list(c.values())
    if layer == "text":
        elems = []
    for ex in fr["extras"]:
        if ex[0] == "z":
            if layer == "chara":
                continue
            _, x, y, size = ex
            elems += text_elems(["Z"], size, x + size * 0.32, y + size * 0.56)
            continue
        if layer == "text":
            continue
        kind, cx, cy, w, h = ex
        fill, stroke, sw, vw, vh, d = SPARK if kind == "spark" else SWEAT
        elems.append(dict(fill=fill, stroke=stroke, sw=sw, w=w, h=h, left=cx - w / 2, top=cy - h / 2,
                          d=d, rot=0, vw=vw, vh=vh))
    if fr["text"] and layer != "chara":
        t = fr["text"]
        elems += text_elems(t["lines"], t["size"], t["cx"], t["cy"], t["rot"])
    return elems


def origin(i):
    return (i % 4) * CELL_W, (i // 4) * CELL_H


# ---- 出力 --------------------------------------------------------------------

def to_svg(frames, layer="all", bg=True):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="540">'
           + (f'<rect width="1280" height="540" fill="{BG}"/>' if bg else "")]
    for i, fr in enumerate(frames):
        x0, y0 = origin(i)
        for e in frame_elems(fr, layer):
            vw, vh = e.get("vw", e["w"]), e.get("vh", e["h"])
            tf = (f'translate({x0 + e["left"]:.1f} {y0 + e["top"]:.1f}) '
                  f'rotate({e["rot"]} {e["w"] / 2:.1f} {e["h"] / 2:.1f}) scale({e["w"] / vw:.4f} {e["h"] / vh:.4f})')
            stroke = f'stroke="{e["stroke"]}" stroke-width="{e["sw"]}"' if e["sw"] else 'stroke="none"'
            out.append(f'<path transform="{tf}" d="{e["d"]}" fill="{e["fill"]}" {stroke} stroke-linejoin="round"/>')
    out.append("</svg>")
    return "\n".join(out)


def to_png(frames, path, layer="all", bg=True):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "sheet.svg"
        svg.write_text(to_svg(frames, layer, bg))
        subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--window-size=1280,700", "--default-background-color=00000000", f"--screenshot={path}", svg.as_uri()],
                       check=True, capture_output=True)
    Image.open(path).crop((0, 0, 1280, 540)).save(path)
    print(f"プレビュー: {path}")


def to_ops(frames, page_id, frame_nums, layer="all"):
    ops = []
    for n in frame_nums:
        x0, y0 = origin(n - 1)
        for e in frame_elems(frames[n - 1], layer):
            op = dict(type="insert_shape", page_id=page_id,
                      left=round(x0 + e["left"], 1), top=round(y0 + e["top"], 1),
                      width=round(e["w"], 1), height=round(e["h"], 1), path=e["d"],
                      view_box_width=round(e.get("vw", e["w"]), 1), view_box_height=round(e.get("vh", e["h"]), 1),
                      color=e["fill"])
            if e["sw"]:
                op.update(stroke_color=e["stroke"], stroke_weight=e["sw"])
            if e["rot"]:
                op["rotation"] = e["rot"]
            ops.append(op)
    return ops


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", choices=sorted(STAMPS))
    ap.add_argument("--png", help="プレビュー画像の保存先")
    ap.add_argument("--ops", help="Canva 操作 JSON の保存先")
    ap.add_argument("--page", help="Canva のページID")
    ap.add_argument("--frames", default="1-8", help="例: 1-8 / 1,2")
    ap.add_argument("--text-png", help="セリフだけの透過PNG(Canva にアップロードして重ねる用)")
    ap.add_argument("--chara-only", action="store_true", help="Canva操作をキャラの図形だけにする")
    a = ap.parse_args()
    frames = STAMPS[a.stamp]
    if a.png:
        to_png(frames, a.png)
    if a.text_png:
        to_png(frames, a.text_png, layer="text", bg=False)
    if a.ops:
        if "-" in a.frames:
            lo, hi = map(int, a.frames.split("-"))
            nums = list(range(lo, hi + 1))
        else:
            nums = [int(x) for x in a.frames.split(",")]
        ops = to_ops(frames, a.page or "PAGE_ID", nums, "chara" if a.chara_only else "all")
        Path(a.ops).write_text(json.dumps(ops, ensure_ascii=False, separators=(",", ":")))
        print(f"Canva操作: {a.ops}({len(ops)}個, {Path(a.ops).stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
