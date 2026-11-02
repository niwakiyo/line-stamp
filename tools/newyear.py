#!/usr/bin/env python3
"""ていねいインコ set03「ひつじ年のお正月」: ひつじのキャラと、筆で書いていく年賀状。

  確認用シート : python3 tools/newyear.py 01 --png sheet.png
  (キャラのスタンプは 12コマ=4x3、年賀状は 20コマ=5x4 のシートになる)

決まりごと(docs/stamp_rules.md)はそのまま守る。キャラの動きは winter.py / soft.py と同じ仕組み。
"""
import argparse
import math
import random
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import inko
import soft
import winter
from soft import kf, word, S, J0, J1, J2, B1, B2, happy, blink, talk, step, flap, tuft, TUFT
from winter import add, head_off, face_off, HORN, confetti, make, MID, SMALL, daruma, omikuji, sh, SWAY, HOP, STRIPE, DOT

ROOT = Path(__file__).resolve().parent.parent
BRUSH_FONT = ROOT / "assets/fonts/YujiSyuku-Regular.ttf"

# ---- ひつじ ---------------------------------------------------------
WOOL = "#FFFDF6"
FACE_YELLOW = "#FFE98F"
HOOF = "#E8CFA6"

_scallop = soft.scallop


def wool_scallop(w, h, bumps=18, depth=1.6):
    """体のふちを、ひつじの毛のように大きく波打たせる。"""
    return _scallop(w, h, bumps=13, depth=4.2)


soft.scallop = wool_scallop

_order = winter.inko_order


def inko_order(key):
    if key.startswith("FACE"):  # 顔の黄色い部分は、体の毛より前・目や口より後ろ
        return winter.ORDER.index("P5") - 0.5
    return _order(key)


winter.inko_order = inko_order
soft.inko_order = inko_order


SHEEP_FACE = "#FFF1DC"
EAR = "#F3D9C0"
WOOL_TUFT = ("M5 20 C1 20 0 14 4 12 C3 6 9 3 13 6 C15 1 23 1 25 6 C29 5 31 10 28 13 C31 15 30 20 26 20 Z")
EAR_L = "M2 7 C6 1 18 0 27 5 C26 10 16 14 8 13 C4 12 2 10 2 7 Z"
EAR_R = "M26 7 C22 1 10 0 1 5 C2 10 12 14 20 13 C24 12 26 10 26 7 Z"
NOSE = "M3 2 C3 1 17 1 17 2 C17 5 13 7 10 7 C7 7 3 5 3 2 Z"
MOUTH = ("M3 6 C5 10 8 10 9 7 C10 10 13 10 15 6 C15 5 14 5 13.5 6 C12.5 8 10.5 8 9.8 5.5 L8.2 5.5 "
         "C7.5 8 5.5 8 4.5 6 C4 5 3 5 3 6 Z")
MOUTH_OPEN = "M4 4 C4 3 14 3 14 4 C14 10 12 13 9 13 C6 13 4 10 4 4 Z"


SKIN = "#F6E4D2"     # 顔と足(はだ色)
HOOF_DARK = "#7A5A48"
CLOUD_FRINGE = ("M8 28 C2 28 1 20 6 17 C4 9 12 5 18 9 C21 2 31 1 36 7 C40 1 52 2 54 9 C60 5 70 9 68 17 "
                "C74 20 73 28 67 28 Z")
LEG = "M2 1 L12 1 L12 11 C12 14 10 15 7 15 C4 15 2 14 2 11 Z"  # 14x16 の短い足
HOOF_P = "M3 2 L17 2 C19 2 20 4 20 6 L20 12 L0 12 L0 6 C0 4 1 2 3 2 Z"


_soften = soft.soften


def soften_keep_legs(c):
    """soft.soften は P6/P7 をインコの羽の形に描き替えるので、ひつじの足(leg 印)は足の形に戻す。"""
    c = _soften(c)
    for key, e in c.items():
        if e.get("leg"):
            e["d"] = LEG
        if e.get("sw") and key != "P0":  # 輪郭の線を太くする(soften で細くなった線の約1.8倍)
            e["sw"] = round(max(e["sw"] * 1.8, 2.6), 1)
        if e.get("sw") and e.get("vw", e["w"]) > e["w"] * 1.5:
            # 大きな座標で描いた部品(角・前髪)は、縮めると線も細くなるので、その分だけ太くしておく
            e["sw"] = round(e["sw"] * e["vw"] / e["w"], 1)
    return c


soft.soften = soften_keep_legs


EAR_OUT = "#E6BC9A"   # 耳の外側(顔より少し濃い)
EAR_IN = "#F7C9C3"    # 耳の内側(うすい桃色。ほっぺより淡く)
EAR_IN_L = "M4 7 C8 3 17 3 23 6 C22 9 15 11 9 10 C6 10 4 9 4 7 Z"


def _horn(mirror):
    """角のパスを4倍の大きさの座標にする(手描きの揺れで左右の形がずれないように)。mirror で左右反転。"""
    def tf(m):
        x, y = float(m.group(1)), float(m.group(2))
        return f"{(28 - x if mirror else x) * 4:g} {y * 4:g}"
    return re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", tf, HORN)


HORN_L, HORN_R = _horn(False), _horn(True)
# 角は頭の上から外へ張り出し、下へ回って先が顔の側(内側)へ巻き込む向き
# うず巻きの内側(4倍の座標の丸)。HORN_L / HORN_R の巻きの中心に置く
HORN_IN_L = soft.ellipse_d(26, 26).replace("M", "M", 1)
HORN_IN_L = re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)",
                   lambda m: f"{float(m.group(1)) + 41:.1f} {float(m.group(2)) + 49:.1f}", HORN_IN_L)
HORN_IN_R = re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)",
                   lambda m: f"{112 - float(m.group(1)):.1f} {float(m.group(2)):.1f}", HORN_IN_L)
def _area(d):
    pts = [(float(x), float(y)) for x, y in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", d)]
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def _reverse_circle(d):
    """ellipse_d の丸(M + C4本)を逆回りにする。"""
    nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
    pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    start, rest = pts[0], pts[1:]
    segs = [rest[i:i + 3] for i in range(0, len(rest), 3)]
    out, cur = f"M{start[0]:.1f} {start[1]:.1f}", start
    for c1, c2, end in reversed([(sg[0], sg[1], sg[2]) for sg in segs]):
        pass
    # 逆回り: 各区間を (終点→始点) の順に、制御点を入れ替えて並べる
    ends = [start] + [sg[2] for sg in segs]
    out = f"M{ends[-1][0]:.1f} {ends[-1][1]:.1f}"
    for k in range(len(segs) - 1, -1, -1):
        c1, c2, _ = segs[k]
        e0 = ends[k]
        out += f" C{c2[0]:.1f} {c2[1]:.1f} {c1[0]:.1f} {c1[1]:.1f} {e0[0]:.1f} {e0[1]:.1f}"
    return out + " Z"


def _with_hole(horn, hole):
    """角のパスに、うず巻きの内側の穴を足す。穴の丸を角と逆回りにして、内側だけ塗らない(角が無い)ようにする。"""
    if (_area(horn) > 0) == (_area(hole) > 0):
        hole = _reverse_circle(hole)
    return horn + " " + hole


HORN_SET, HORN_ROT = (_with_hole(HORN_R, HORN_IN_R), _with_hole(HORN_L, HORN_IN_L)), -20


def _circles(cx, cy, rx, ry, n, r, shrink=0.0):
    """楕円の上に n 個の丸を並べたパス(丸は C で描く)。4倍の座標で作り、手描きの揺れを目立たなくする。"""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y, rr = cx + rx * math.cos(a), cy + ry * math.sin(a), r - shrink
        out.append(soft.ellipse_d(2 * rr, 2 * rr).replace("M", f"M", 1))
        # ellipse_d は (0,0)〜(2rr,2rr) の箱なので、丸の左上へずらす
        out[-1] = re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)",
                         lambda m: f"{float(m.group(1)) + x - rr:.1f} {float(m.group(2)) + y - rr:.1f}", out[-1])
    out.append(soft.ellipse_d(2 * (rx - shrink), 2 * (ry + r * 0.6 - shrink)))
    out[-1] = re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)",
                     lambda m: f"{float(m.group(1)) + cx - rx + shrink:.1f} {float(m.group(2)) + cy - ry - r * 0.6 + shrink:.1f}",
                     out[-1])
    return " ".join(out)


# 前髪(84x38 を 4倍の座標 336x152 で): 丸 9 個を輪に並べる
FRINGE_OUT = _circles(168, 76, 118, 34, 9, 40)
FRINGE_IN = _circles(168, 76, 118, 34, 9, 40, shrink=9)


def ear(c, key, bx, by, side, rot):
    """耳: 付け根 (bx, by) を支点に rot 度。外側(濃い色)の上に内側(桃色)を重ねて立体感を出す。
    side=-1 は左耳(先が左)、1 は右耳。顔(FACE1)より後ろに置き、付け根が顔に隠れるようにする。"""
    w, h = 34, 17
    for suffix, fill, d, sw, kw in (("a", EAR_OUT, EAR_L if side < 0 else EAR_R, 2, 1.0),
                                    ("b", EAR_IN, EAR_IN_L, 0, 0.72)):
        ww, hh = w * kw, h * kw
        ra = math.radians(rot)
        off = side * (w / 2 - 2) * (1 if suffix == "a" else 0.9)  # 付け根から耳の中心までの距離
        cx, cy = bx + off * math.cos(ra), by + off * math.sin(ra)
        dd = d if side < 0 or suffix == "a" else "M23 7 C19 3 10 3 4 6 C5 9 12 11 18 10 C21 10 23 9 23 7 Z"
        add(c, key + suffix, fill, inko.INK if sw else None, sw, ww, hh, cx - ww / 2, cy - hh / 2, dd, rot=rot)
        c[key + suffix].update(vw=28 if suffix == "a" else 27, vh=15 if suffix == "a" else 12)


def ears(dl, dr):
    """耳を動かす(左右で別の角度)。sheep() より前に置く。"""
    def f(c):
        c["_earL"], c["_earR"] = dl, dr
    return f


def legs(lift_l, lift_r, ang_l, ang_r, hind):
    """足の動き: 前足は付け根(上の端)を支点に回しながら持ち上げる。後ろ足は交互に少し持ち上げる。"""
    def f(c):
        for k, lift, ang in (("P6", lift_l, ang_l), ("P7", lift_r, -ang_r)):
            e = c[k]
            px, py = e["left"] + e["w"] / 2, e["top"]  # 付け根
            ra = math.radians(ang)
            # 回すと中心が付け根のまわりを動くので、中心の位置を回して置き直す
            cx, cy = px - (e["h"] / 2) * math.sin(ra), py + (e["h"] / 2) * math.cos(ra)
            e.update(left=cx - e["w"] / 2, top=cy - e["h"] / 2 - lift, rot=ang)
        for k, up in (("P2", hind), ("P3", -hind)):
            if up > 0:
                c[k]["top"] -= up
    return f


def sheep(c):
    """ひつじ(インコの形は使わない):
    - 体: 横に広い雲のような毛のかたまり(高さはポーズのまま、幅を高さの1.35倍に広げる)
    - 顔: はだ色の大きな顔に、おでこを覆う毛の前髪。横にたれた耳、くるんとした角
    - 目: 小さな黒い目(インコの大きな目にしない)、小さな鼻と「ω」の口
    - 前足(インコの羽の部品を足にする)と後ろ足: はだ色の足と、こげ茶のひづめ。肩を支点に動くのはそのまま
    顔まわりは鼻(P14)の位置から、前髪・角は頭(P1)の位置から置くので、おじぎやジャンプについて行く。"""
    fx, fy = face_off(c)
    hx, hy = fx, fy  # 前髪・角も顔と同じだけ動かす(頭の毛 P1 のずれは顔とちがうので使わない)
    for k in ("P0", "P4"):  # 体を横に広い毛のかたまりにする
        e = c[k]
        w = min(e["h"] * 1.35, 138)
        cx = e["left"] + e["w"] / 2
        e.update(w=w, left=cx - w / 2, vw=w, vh=e["h"])
    c["P4"]["fill"] = WOOL
    c["P5"].update(fill=WOOL)
    c.pop("P1", None)  # インコの頭の毛は使わない(前髪にまとめる)
    # 足: 毛のかたまりの下から、短い4本の足をのぞかせる(前足は体の前、後ろ足は体の後ろ)。
    # インコの羽のように体の前に垂らさない。前足は付け根を支点に ARMS の角度(小さめ)で動く
    bottom = c["P4"]["top"] + c["P4"]["h"]
    for k, x in (("P6", 160 - 18), ("P7", 160 + 18)):
        c[k].update(d=LEG, fill=SKIN, w=14, h=16, vw=14, vh=16, left=x - 7, top=bottom - 16, rot=0, leg=True)
    for k, x in (("P2", 160 - 40), ("P3", 160 + 40)):
        c[k].update(d=LEG, fill=SKIN, w=14, h=16, vw=14, vh=16, left=x - 7, top=bottom - 16)
    add(c, "FACE1", SKIN, inko.INK, 3.4, 76, 66, 122 + fx, 146 + fy, soft.ellipse_d(76, 66))  # 顔の輪郭は太め
    ear(c, "FACE0_earL", 128 + fx, 188 + fy, -1, -14 + c.get("_earL", 0))
    ear(c, "FACE0_earR", 192 + fx, 188 + fy, 1, 14 + c.get("_earR", 0))
    # 角: 付け根(とがった端)を頭のてっぺん側(前髪の下)に向け、うず巻きは顔の横に下ろす
    add(c, "ACC1_hornL", "#E9C98F", inko.INK, 2, 42, 42, 90 + hx, 140 + hy, HORN_SET[0], rot=HORN_ROT)
    c["ACC1_hornL"].update(vw=112, vh=112)
    add(c, "ACC2_hornR", "#E9C98F", inko.INK, 2, 42, 42, 188 + hx, 140 + hy, HORN_SET[1], rot=-HORN_ROT)  # 左の角の鏡うつし
    c["ACC2_hornR"].update(vw=112, vh=112)
    # うず巻きの内側は角ではなく体: 体の毛と同じ白で埋める(角と同じ箱・同じ回転で、角の上に重ねる)
    for key, hole in (("ACC1_hornL", HORN_IN_R), ("ACC2_hornR", HORN_IN_L)):
        e = c[key]
        add(c, "ACC9_" + key[5:] + "_hole", WOOL, None, 0, e["w"], e["h"], e["left"], e["top"], hole, rot=e["rot"])
        c["ACC9_" + key[5:] + "_hole"].update(vw=112, vh=112)

    # 前髪: 丸を輪に並べた雲の形(とがった谷を作らない)。輪郭の丸の上に、少し小さい白い丸を重ねて内側の線を消す
    add(c, "ACC3_fringe", WOOL, inko.INK, 2, 84, 38, 118 + hx, 124 + hy, FRINGE_OUT)
    add(c, "ACC4_fringefill", WOOL, None, 0, 84, 38, 118 + hx, 124 + hy, FRINGE_IN)
    for k in ("ACC3_fringe", "ACC4_fringefill"):
        c[k].update(vw=336, vh=152)
    # 目は小さく(あとで soften が 1.4 倍にするので、先に小さくしておく)・ほっぺは顔の内側へ
    for k in ("P8", "P9", "P10", "P11"):
        if k in c:
            e = c[k]
            cx, cy = e["left"] + e["w"] / 2, e["top"] + e["h"] / 2
            e.setdefault("vw", e["w"])
            e.setdefault("vh", e["h"])
            kk = 0.76 if k in ("P8", "P9") else 0.6
            e["w"], e["h"] = e["w"] * kk, e["h"] * kk
            e["left"], e["top"] = cx - e["w"] / 2 + (4 if k in ("P8", "P10") else -4), cy - e["h"] / 2
    c["P12"]["left"] += 10
    c["P13"]["left"] -= 10
    c["P14"].update(d=NOSE, fill="#9C6B55", sw=0, stroke=None)  # 鼻はこげ茶(ほっぺのピンクと分ける)
    c["P15"].update(d=MOUTH, fill=soft.LINE, sw=0, stroke=None)
    c.pop("_earL", None)
    c.pop("_earR", None)


def sheep_talk(c):
    """ひつじの口パク: 口の形を少し開いた丸にして、色を変えるだけ(大きさ・位置はそのまま)。"""
    c["P15"].update(d=MOUTH_OPEN, fill=soft.BEAK_OPEN_FILL, sw=1.5, stroke=inko.INK)


# ---- 01 あけまして/おめでとう/ございます(ひつじのインコ) ----------------------------

def say_curved(pal, *parts):
    """set03 のセリフ: ゆるいカーブ・文字ごとの大きさの変化と段差・漢字は筆の書体。"""
    key, rest, rim = winter.PAL[pal]
    ws = []
    for i, (text, x, y, size, rot, strong, extra) in enumerate(parts):
        w = word(text, x, y, size, key if strong else rest, rot=rot, seed=i + 1, arc=0.32 if strong else 0.2,
                 **extra)
        w.update(vary=True, kanji_font=BRUSH_FONT)
        if strong and rim:
            w.update(rim=rim, rim_w=4)
        ws.append(w)
    return ws


def block_staggered(pal, lines, x0=28, y0=24, indent=8):
    """行ごとに、横の位置と傾きを交互にずらす(左ぞろえの直列にしない)。"""
    out, y = [], y0 + 10
    x0 += 12  # 先頭の大きな字とカーブの分だけ内側へ
    for i, (text, size, strong) in enumerate(lines):
        w = len(text) * size * 0.98
        cy = y + size * 0.62
        shift = (0, 22, 8, 26)[i % 4]
        out.append((text, x0 + shift + w / 2, cy, size, (-7, 4, -3, 5)[i % 4], strong))
        y += size * 1.3
    return out


winter.say = say_curved
winter.block = block_staggered


def kazari(c):
    """前髪の右上に、紅白の水引の髪飾り(顔と同じ基準で動く)。"""
    ox, oy = face_off(c)
    x, y, k = 196 + ox, 130 + oy, 1.1

    def put(key, fill, w, h, dx, dy, d, rot):
        add(c, key, fill, inko.INK, 2, w * k, h * k, x + dx * k, y + dy * k, d, rot=rot)
        c[key].update(vw=w, vh=h)
    put("ACC90_tailW", "#FFFFFF", 9, 18, -8, 1, winter.TAIL, 18)
    put("ACC91_tailR", SHU, 9, 18, -1, 1, winter.TAIL, -12)
    put("ACC92_loopW", "#FFFFFF", 18, 14, -17, -9, winter.LOOP_L, -8)
    put("ACC93_loopR", SHU, 18, 14, 0, -10, winter.LOOP_R, 8)
    put("ACC94_knot", "#E8B33A", 10, 10, -5, -5, DOT, 0)
    c["ACC94_knot"].update(vw=40, vh=40)


def cf01(i, av):
    return confetti(31, 4, i, box=(240, 30, 296, 84)) + confetti(32, 4, i, box=(30, 196, 112, 250))


EAR01 = ([0, -12, 6, -12, 6, -10, 4, -12, 6, -10, 4, 0],     # 耳: 左右で逆に、ぴくぴく
         [0, 6, -12, 6, -12, 4, -10, 6, -12, 4, -10, 0])

STAMPS = {
    "01": make("new", [("あけまして", 46, True), ("おめでとう", 34, False), ("ございます", 34, False)], "A",
               lambda i: [[S, happy], [J0, happy], [J1, happy], [J1, happy, J2], [J1, happy], [J0, happy],
                          [S, happy], [B1, happy], [B2, happy], [B1, happy], [S, happy], [S, happy]][i]
               + [ears(EAR01[0][i], EAR01[1][i]), sheep, kazari], cf01, m=MID),
}

# ---- 残りのひつじのスタンプ(02〜04・13〜16) ------------------------------------------

POCHI = "M2 2 L24 2 L24 34 L2 34 Z"


def pochi(c):
    """ぽち袋(赤に金の帯と白い結び)。体の前に持つ。"""
    ox, oy = face_off(c)
    oy *= 0.6  # 深いおじぎで下にはみ出さないよう、顔より少しだけ下げる
    add(c, "ACC5_pochi", "#E0352B", inko.INK, 2, 28, 36, 146 + ox, 204 + oy, POCHI)
    add(c, "ACC6_pochiband", "#E8B33A", None, 0, 24, 5, 148 + ox, 214 + oy, STRIPE)
    c["ACC6_pochiband"].update(vw=16, vh=6)
    add(c, "ACC7_pochiknot", "#FFFFFF", inko.INK, 1.5, 9, 9, 155.5 + ox, 212 + oy, DOT)
    c["ACC7_pochiknot"].update(vw=40, vh=40)


JUBAKO = "M4 2 L116 2 C118 2 120 4 120 6 L120 30 L0 30 L0 6 C0 4 2 2 4 2 Z"


def jubako(c):
    """おせちの重箱(体の前に置く。体には付いて行かない)。黒い箱に朱のふちと金の線、上に料理。"""
    add(c, "ACC5_box", "#2E2A2A", inko.INK, 2, 124, 40, 98, 220, "M2 2 L122 2 L122 38 L2 38 Z")
    add(c, "ACC6_boxline", "#E8B33A", None, 0, 116, 4, 102, 236, STRIPE)
    c["ACC6_boxline"].update(vw=16, vh=6)
    add(c, "ACC7_tray", "#D8402F", inko.INK, 2, 128, 14, 96, 208, "M2 2 L126 2 L126 12 L2 12 Z")
    for k, (x, col) in enumerate(((112, "#F07A4A"), (134, "#FFD24D"), (156, "#3A2E39"), (178, "#F7C9C3"),
                                  (200, "#FFD24D"))):
        add(c, f"ACC8_food{k}", col, inko.INK, 1.5, 16, 12, x, 199, DOT)
        c[f"ACC8_food{k}"].update(vw=40, vh=40)


def sun(c):
    """頭のうしろから昇る初日の出(体には付いて行かない)。"""
    cx, cy, r = 170, 124, 30
    for j, a in enumerate((-170, -135, -100, -65, -30, 5)):
        ra = math.radians(a)
        x, y = cx + (r + 12) * math.cos(ra), cy + (r + 12) * math.sin(ra)
        add(c, f"BG1_ray{j}", "#FFD24D", inko.INK, 1.5, 12, 5, x - 6, y - 2.5, winter.RAY, rot=a)
    add(c, "BG2_sun", "#FFA94D", inko.INK, 2, 2 * r, 2 * r, cx - r, cy - r, winter.SUN)


def sheep_stamp(lines, typ, poses, marks, props=(), m=MID, **kw):
    """ひつじのスタンプ: poses(i) のあとに 耳 → ひつじ → 髪飾り → 小物 の順で足す。"""
    return make("new", lines, typ,
                lambda i: poses(i) + [ears(EAR01[0][i], EAR01[1][i]), sheep, kazari] + list(props),
                marks, m=m, **kw)


def wa_marks(pts):
    """和風の飾り: 梅の花と金のキラキラを交互に置き、キラキラだけ少しまたたく。"""
    def f(i, av):
        out = []
        for j, (x, y, sz) in enumerate(pts):
            out.append(("ume", x, y, sz + 2) if j % 2 == 0 else ("spark", x, y, sz + (3 if (i + j) % 2 else 0)))
        return out
    return f


BOW02 = [[B2], [S, blink], [S, blink], [S, blink], [B1], [B2], [B2], [B2], [B2], [B2], [B1], [S, blink]]
BOW15 = [[B1, happy], [S, happy], [S, happy], [S, happy], [B1, happy], [B1, happy], [B2, happy], [B2, happy],
         [B1, happy], [S, happy], [S, happy], [S, happy]]
SWAY2 = [0, 0, 1, 1, 0, -1, -1, 0, 1, 1, 0, 0]

STAMPS.update({
    # 02 本年も/よろしく/お願い/いたします(A): 両前足をそろえて深くおじぎ
    "02": sheep_stamp([("本年も", 48, True), ("よろしく", 32, False), ("お願い", 30, False), ("いたします", 28, False)],
                      "A", lambda i: list(BOW02[i]), wa_marks([(292, 118, 9), (292, 206, 7)]), m=SMALL),
    # 03 謹賀新年(C): もこもこの体でぽよんと弾む。金の紙ふぶき
    "03": sheep_stamp([("謹賀新年", 58, True)], "C", lambda i: [HOP[i], happy, sh(SWAY[i])],
                      lambda i, av: confetti(33, 7, i, box=(24, 100, 116, 250)) + confetti(34, 3, i, box=(262, 40, 288, 90)),
                      wave_amp=5, m=dict(scale=1.12, anchor=(220, 254))),
    # 04 旧年中は/お世話に/なりました(B): だるまを抱えてゆらゆら
    "04": sheep_stamp([("旧年中は", 50, True), ("お世話に", 34, False), ("なりました", 34, False)], "B",
                      lambda i: [S, happy, sh(SWAY[i])], wa_marks([(288, 110, 10), (44, 222, 9)]),
                      props=()),
    # 17 初日の出/きれいです(A): 頭のうしろに初日の出。目を閉じてうっとり、ゆらゆら
    "17": sheep_stamp([("初日の出", 46, True), ("きれいです", 34, False)], "A",
                      lambda i: [S, blink, sh(SWAY2[i])], wa_marks([(40, 228, 8), (120, 236, 6)]),
                      props=(sun,), m=dict(scale=1.0, anchor=(230, 256))),
    # 18 大吉/でした!(B): おみくじを持って、うれしくてぴょんぴょん
    "18": sheep_stamp([("大吉", 60, True), ("でした!", 38, False)], "B", lambda i: [HOP[i]],
                      lambda i, av: confetti(14, 6, i, box=(250, 30, 296, 100)) + [("spark", 290, 150, 10 + i % 2 * 3)],
                      props=(omikuji,)),
    # 19 お年玉/ありがとう/ございます(A): ぽち袋を持ってぺこり
    "19": sheep_stamp([("お年玉", 50, True), ("ありがとう", 32, False), ("ございます", 32, False)], "A",
                      lambda i: list(BOW15[i]), wa_marks([(290, 120, 9), (44, 230, 8)]), props=(pochi,)),
    # 20 おせち/いただきます(A): 重箱の前でにっこり。前足を交互に大きく上げ下げ(食べる手の動き)
    "20": sheep_stamp([("おせち", 54, True), ("いただきます", 32, False)], "A",
                      lambda i: [S, happy, sh(SWAY2[i])], wa_marks([(292, 120, 9), (40, 120, 7)]),
                      props=(jubako,)),
})
STAMPS.update({
    # 21 今年も/がんばります!(B): ぴょんぴょん跳ねて、前足でガッツ
    "21": sheep_stamp([("今年も", 50, True), ("がんばります!", 34, False)], "B", lambda i: [HOP[i], happy],
                      lambda i, av: confetti(21, 4, i, box=(250, 40, 290, 100))),
    # 22 寝正月/中です(C): こたつでうとうと(目を閉じて、ゆっくりゆれる)
    "22": sheep_stamp([("寝正月", 54, True), ("中です", 36, False)], "C", lambda i: [S, blink, sh(SWAY2[i])],
                      lambda i, av: [("steam", 120 + j * 10, 186, 12 + (i + j) % 3 * 3, i * 0.9 + j) for j in range(2)],
                      props=(winter.kotatsu,), m=dict(scale=1.12, anchor=(214, 254))),
    # 23 笑う門には/福来たる(A): にっこり左右にゆれる、金の紙ふぶき
    "23": sheep_stamp([("笑う門には", 36, True), ("福来たる", 34, True)], "A", lambda i: [S, happy, sh(SWAY2[i])],
                      lambda i, av: confetti(23, 5, i, box=(36, 170, 110, 246)), x0=36),
    # 24 新年会/楽しみです(B): うれしくて弾む
    "24": sheep_stamp([("新年会", 54, True), ("楽しみです", 36, False)], "B", lambda i: [HOP[i], happy],
                      wa_marks([(290, 120, 9), (44, 228, 8)])),
})

# 04 のだるまは、ゆれの角度をコマごとに変えるので、台本を作り直す
STAMPS["04"] = sheep_stamp([("旧年中は", 50, True), ("お世話に", 34, False), ("なりました", 34, False)], "B",
                           lambda i: [S, happy, sh(SWAY[i])], wa_marks([(286, 110, 10), (44, 222, 9)]),
                           m=dict(scale=1.12, anchor=(220, 254)))
for i, fr in enumerate(STAMPS["04"]):
    fr["poses"] = fr["poses"] + [daruma(SWAY[i] * 4)]

LEGS_EAT = ([0, 7, 2, 7, 2, 7, 2, 7, 2, 7, 2, 0],      # 20 おせち: 左右の前足を交互に大きく上げ下げ
            [0, 2, 7, 2, 7, 2, 7, 2, 7, 2, 7, 0],
            [0, 16, 4, 16, 4, 16, 4, 16, 4, 16, 4, 0],
            [0, 4, 16, 4, 16, 4, 16, 4, 16, 4, 16, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
LEGS_CHEER = ([0, 3, 7, 7, 4, 0, 6, 0, 7, 0, 6, 0],   # 21 がんばります: 跳ぶたびに前足を上げる
              [0, 0, 6, 7, 7, 3, 0, 7, 0, 6, 0, 6],
              [0, -6, 16, 16, 10, -4, 14, -2, 16, -2, 14, 0],
              [0, -4, 14, 16, 16, -6, -2, 16, -2, 14, -2, 14],
              [0, 3, -3, 0, 0, 3, -3, 3, -3, 3, -3, 0])

LEGS = {  # (左前足の持ち上げpx, 右前足の持ち上げpx, 左前足の角度, 右前足の角度, 後ろ足の持ち上げpx)
    # 前足は付け根を支点に最大16°・持ち上げ最大5px、後ろ足は最大3px。左右で交互・別の角度
    "01": ([0, 2, 5, 5, 4, 0, 4, 0, 3, 0, 4, 0],
           [0, 0, 4, 5, 5, 2, 0, 4, 0, 3, 0, 4],
           [0, -6, 16, 14, 10, -4, 12, -2, 10, -2, 12, 0],
           [0, -4, 12, 16, 12, -6, -2, 12, -2, 10, -2, 12],
           [0, 3, -3, 0, 0, 3, -3, 3, -3, 3, -3, 0]),
}

for name, frames in STAMPS.items():
    ll, lr, al, ar, hd = {"20": LEGS_EAT, "21": LEGS_CHEER}.get(name) or LEGS.get(name, LEGS["01"])
    for i, fr in enumerate(frames):
        extra = []
        if i in soft.TALK_FRAMES:
            extra.append(sheep_talk)
        if i:
            extra.append(legs(ll[i], lr[i], al[i], ar[i], hd[i]))
        fr["poses"] = fr["poses"] + extra


def hands_up(c):
    """20 おせち: 前足を重箱より前に出して、台の上で動いているのが見えるようにする。"""
    for k in ("P6", "P7"):
        e = c.pop(k)
        e["top"] -= 36
        c["ACC99_" + k] = e


for fr in STAMPS["20"]:
    fr["poses"] = fr["poses"] + [hands_up]


# ---- 年賀状(筆で書いていく) --------------------------------------------------------
CW, CH = 320, 270
CARD = "#FFF9EE"
INK_BLACK = "#2E2A2A"
SHU = "#D8402F"


def sheep_icon(height):
    """年賀状のすみに描く、小さなひつじ(キャラと同じ図形を描いて縮める)。"""
    frames = [kf([S, happy, sheep], scale=1.0, anchor=(160, 258))]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.png"
        soft.chara_png(frames, p)
        im = Image.open(p).convert("RGBA").crop((0, 0, CW, CH))
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    # 角の穴の緑は、はがきの上では透明にする(はがきの色が見えるように)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and g > 200 and r < 90 and b < 90:
                px[x, y] = (0, 0, 0, 0)
    im = im.crop(im.getbbox())
    k = height / im.height
    return im.resize((round(im.width * k), height), Image.LANCZOS)


def card_base():
    """はがき(生成り・朱の細い枠)。外側に白いふちを付けて、暗い背景でも形が分かるようにする。"""
    im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 82, 16, 238, 254
    d.rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), fill="white")  # はがきらしく、角は丸くしない
    d.rectangle((x0, y0, x1, y1), fill=CARD, outline=soft.LINE, width=3)
    d.rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), outline=SHU, width=2)
    # 和風の飾り: 左上に金の扇(要は角)、右下の角に紅白の水引の線
    fx, fy = x0 + 8, y0 + 8
    d.pieslice((fx - 30, fy - 30, fx + 30, fy + 30), 0, 90, fill="#E8B33A", outline=soft.LINE, width=2)
    for a in (22, 45, 68):
        ra = math.radians(a)
        d.line([(fx, fy), (fx + 29 * math.cos(ra), fy + 29 * math.sin(ra))], fill=soft.LINE, width=1)
    d.pieslice((fx - 10, fy - 10, fx + 10, fy + 10), 0, 90, fill=SHU)
    for k, col in enumerate((SHU, "white", SHU)):
        o = 14 + k * 4
        d.arc((x1 - 8 - o, y1 - 8 - o, x1 - 8 + o, y1 - 8 + o), 180, 270, fill=col, width=3)
    return im


def glyph(ch, size, color=INK_BLACK):
    font = ImageFont.truetype(str(BRUSH_FONT), size)
    g = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
    # 少し太らせて、筆の墨のたっぷりした感じを出す
    ImageDraw.Draw(g).text(((size + 20) / 2, (size + 20) / 2), ch, font=font, anchor="mm", fill=color,
                           stroke_width=1, stroke_fill=color)
    return g


def brush_point(bb, k, n, seed):
    """筆先の位置: 上から下へ・右と左に交互に振れる向きは変えず、止まる所は帯ごとにランダムにする。"""
    x0, y0, x1, y1 = bb
    rnd = random.Random(seed * 13 + k)
    mid = (x0 + x1) / 2
    bx = rnd.uniform(mid + 2, x1 - 2) if k % 2 == 0 else rnd.uniform(x0 + 2, mid - 2)
    by = y0 + (y1 - y0) * (k + 1) / n + rnd.uniform(-4, 3)
    return bx, by


def reveal(g, k, n=4):
    """書いている途中: 字を上から n 本の帯に分け、k 本目まで見せる。
    筆は帯ごとに左右へ振れながら下りる(偶数本目は右端、奇数本目は左端で止まる)。戻り値は (画像, 筆先の位置)。"""
    bb = g.getbbox()
    x0, y0, x1, y1 = bb
    y = y0 + (y1 - y0) * (k + 1) / n
    out = g.copy()
    if k < n - 1:
        ImageDraw.Draw(out).rectangle((0, round(y), g.width, g.height), fill=(0, 0, 0, 0))
    bx, by = brush_point(bb, k, n, seed=x0 * 31 + y0)
    return out, (bx, by)


def brush(layer, x, y):
    """筆: 穂先(墨)が (x, y) にあり、柄が右上へのびる。"""
    d = ImageDraw.Draw(layer)
    tx, ty = x + 30, y - 34
    d.line([(x + 6, y - 8), (tx, ty)], fill=soft.LINE, width=10)
    d.line([(x + 6, y - 8), (tx, ty)], fill="#B07A4A", width=6)
    d.polygon([(x, y), (x + 3, y - 14), (x + 12, y - 10)], fill=INK_BLACK, outline="white")


def seal(layer, cx, cy, s, ch="未"):
    """朱色のはんこ(四角に白抜きの字)。"""
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), radius=3, fill=SHU, outline="white",
                        width=2)
    font = ImageFont.truetype(str(BRUSH_FONT), round(s * 0.78))
    d.text((cx, cy + 1), ch, font=font, anchor="mm", fill=CARD)


def card05(icon):
    """05 謹賀新年: 縦書きの4文字を、1文字4コマずつ筆を左右に振りながら書く → ひつじが出て、はんこを押す。"""
    text, size, cx, top, step_y = "謹賀新年", 50, 176, 26, 48
    glyphs = [glyph(ch, size) for ch in text]

    def draw(n_full, partial=None, show_icon=None, seal_s=None, brush_at=None, pops=False):
        im = card_base()
        for k in range(len(text)):
            g = glyphs[k]
            y = top + k * step_y
            if k < n_full:
                im.alpha_composite(g, (round(cx - g.width / 2), round(y)))
            elif k == n_full and partial is not None:
                pg, (bx, by) = reveal(g, partial)
                gx = round(cx - g.width / 2)
                im.alpha_composite(pg, (gx, round(y)))
                brush_at = (gx + bx, y + by)
        if show_icon:
            ic = icon.resize((round(icon.width * show_icon), round(icon.height * show_icon)), Image.LANCZOS)
            im.alpha_composite(ic, (round(114 - ic.width / 2), round(246 - ic.height)))
        if seal_s:
            seal(im, 214, 228, seal_s)
        if pops:
            winter.draw_marks2(im, [("spark", 140, 190, 9), ("spark", 226, 196, 7)], 0, 0)
        if brush_at:
            brush(im, *brush_at)
        return im

    frames = [draw(4, show_icon=1.0, seal_s=26)]                       # 0: 完成形
    frames.append(draw(0, brush_at=(cx + 2, top + 30)))                 # 1: 何も書いていない
    for i in range(16):                                                # 2〜17: 1文字4コマ、筆を左右に振りながら下へ
        frames.append(draw(i // 4, partial=i % 4))
    frames.append(draw(4, show_icon=1.2, seal_s=36, pops=True))         # 18: ひつじがぽん、はんこを押す
    frames.append(draw(4, show_icon=1.0, seal_s=26))                   # 19: 完成形
    return frames


# ---- 書いていく場面の共通部品(年賀状・手書きのセリフ) -------------------------------

HAND_FONT = soft.HAND_FONT


def rim_glyph(ch, size, color, rim=None, rot=0):
    """手書きのセリフ1文字: (フチの画像, 中身の画像)。フチを全部描いてから中身を重ねるために分ける。
    漢字は筆の書体(Yuji Syuku)、かなは手書きの書体(Yusei Magic)にして、書体を混ぜる。"""
    if rot:
        a, b = rim_glyph(ch, size, color, rim)
        return (a.rotate(-rot, resample=Image.BICUBIC, expand=True),
                b.rotate(-rot, resample=Image.BICUBIC, expand=True))
    is_kanji = "\u4e00" <= ch <= "\u9fff"
    font = ImageFont.truetype(str(BRUSH_FONT if is_kanji else HAND_FONT), round(size * (1.08 if is_kanji else 1)))
    pad = 16
    n = size + pad * 2
    a = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    da = ImageDraw.Draw(a)
    rim = rim or soft.RIM
    da.text((n / 2, n / 2), ch, font=font, anchor="mm", fill=rim, stroke_width=13, stroke_fill=rim)
    da.text((n / 2, n / 2), ch, font=font, anchor="mm", fill="white", stroke_width=9, stroke_fill="white")
    b = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(b).text((n / 2, n / 2), ch, font=font, anchor="mm", fill=color)
    return a, b


def band_cut(img, k, n, bbox):
    """字を上から n 本の帯に分けて、k 本目まで残す(k は 0 から)。"""
    if k >= n - 1:
        return img
    y = bbox[1] + (bbox[3] - bbox[1]) * (k + 1) / n
    out = img.copy()
    ImageDraw.Draw(out).rectangle((0, round(y), img.width, img.height), fill=(0, 0, 0, 0))
    return out


def pen(layer, x, y):
    """サインペン: ペン先が (x, y)、軸は右上へ。"""
    d = ImageDraw.Draw(layer)
    tx, ty = x + 30, y - 34
    d.line([(x + 4, y - 5), (tx, ty)], fill=soft.LINE, width=12)
    d.line([(x + 4, y - 5), (tx, ty)], fill="#E0352B", width=8)
    d.line([(tx - 8, ty + 9), (tx, ty)], fill="white", width=8)
    d.polygon([(x, y), (x + 2, y - 8), (x + 8, y - 5)], fill="#3A2E39")


def write_frames(base, chars, deco, tool, n_frames=20, pop=None):
    """書いていく20コマ。chars: [(フチ画像 or None, 中身画像, (左, 上))] を書く順に。
    1コマ目は完成形、2コマ目は何も書いていない、そのあと書き進め、最後に飾り(deco)が出る。
    1文字に使えるコマが2つ以上あるときは、帯ごとに筆先(ペン先)を左右に振りながら下りる。"""
    N = len(chars)
    n_write = n_frames - 5
    states = []
    if N <= n_write:
        per = n_write // N
        for idx in range(N):
            for b in range(per):
                states.append((idx, b, per))
    else:
        cpf = math.ceil(N / n_write)
        for f in range(math.ceil(N / cpf)):
            states.append((min(N, (f + 1) * cpf) - 1, None, 1))

    def draw(upto, band=None, per=1, deco_k=None, tool_at=None, tool_on=True):
        im = base()
        layers = []
        for i, (rim, body, (x, y)) in enumerate(chars):
            if i > upto:
                break
            bb = body.getbbox()
            if i == upto and band is not None:
                rim = band_cut(rim, band, per, bb) if rim else None
                body = band_cut(body, band, per, bb)
                xb, yb = brush_point(bb, band, per, seed=i * 101 + x)
                tool_at = (x + xb, y + yb)
            elif i == upto and band is None and tool_at is None and tool_on:
                tool_at = (x + (bb[2] if i % 2 == 0 else bb[0]), y + bb[3])
            layers.append((rim, body, (x, y)))
        for rim, body, xy in layers:
            if rim:
                im.alpha_composite(rim, xy)
        for rim, body, xy in layers:
            im.alpha_composite(body, xy)
        if deco_k is not None:
            deco(im, deco_k)
        if tool_at:
            tool(im, *tool_at)
        return im

    frames = [draw(N - 1, deco_k=1.0, tool_on=False)]  # 完成形には筆(ペン)を描かない
    rim0, body0, (x0, y0) = chars[0]
    bb0 = body0.getbbox()
    frames.append(draw(-1, tool_at=(x0 + bb0[0] + 4, y0 + bb0[1] + 30)))  # 持ち手が上にはみ出さない高さ
    for idx, b, per in states:
        frames.append(draw(idx, band=b, per=per) if b is not None else draw(idx))
    # 書き終わったら筆(ペン)を上げ、飾りがぽんと出て、そのあと小さく弾み続ける
    frames.append(draw(N - 1, deco_k=pop or 1.25, tool_on=False))
    t = 0
    while len(frames) < n_frames:
        t += 1
        frames.append(draw(N - 1, deco_k=1.0 + 0.1 * (t % 2), tool_on=False))
    return frames[:n_frames]


def clear_base():
    return Image.new("RGBA", (CW, CH), (0, 0, 0, 0))


def line_chars(text, cx, cy, size, color, rim=None):
    """横書き1行を、文字ごとの (フチ, 中身, 位置) にする(中央ぞろえ、文字ごとに少し傾けない素直な手書き)。"""
    adv = size * 0.98
    x = cx - adv * len(text) / 2
    out = []
    for ch in text:
        a, b = rim_glyph(ch, size, color, rim)
        out.append((a, b, (round(x + adv / 2 - a.width / 2), round(cy - a.height / 2))))
        x += adv
    return out


def paste_center(im, icon, cx, bottom, k):
    ic = icon.resize((max(1, round(icon.width * k)), max(1, round(icon.height * k))), Image.LANCZOS)
    im.alpha_composite(ic, (round(cx - ic.width / 2), round(bottom - ic.height)))


def kagami(im, cx, bottom, k):
    """鏡餅(白いお餅2段・橙・朱の台)。葉は描かない。"""
    d = ImageDraw.Draw(im)
    s = 26 * k
    d.rectangle((cx - s * 1.2, bottom - s * 0.5, cx + s * 1.2, bottom), fill=SHU, outline=soft.LINE, width=3)
    d.ellipse((cx - s * 1.1, bottom - s * 1.3, cx + s * 1.1, bottom - s * 0.3), fill="white", outline=soft.LINE, width=3)
    d.ellipse((cx - s * 0.8, bottom - s * 1.9, cx + s * 0.8, bottom - s * 1.0), fill="white", outline=soft.LINE, width=3)
    d.ellipse((cx - s * 0.32, bottom - s * 2.35, cx + s * 0.32, bottom - s * 1.75), fill="#FFA234", outline=soft.LINE, width=3)


# ---- C. 手書きのセリフ(一文字ずつ) -------------------------------------------------
RED, GOLD_RIM = "#E0352B", "#E8B33A"


KOUBAI = "#E8577A"


def sheep_frames(poses_fn, n, scale=0.95, anchor=(240, 258)):
    """ひつじだけを n コマ描く(12コマずつまとめて描く)。poses_fn(i) はポーズの並び。"""
    out = []
    for start in range(0, n, 12):
        fr = []
        for i in range(start, min(n, start + 12)):
            fr.append(kf(poses_fn(i) + [ears(EAR01[0][i % 12], EAR01[1][i % 12]), sheep, kazari]
                         + [legs(*(LEGS["01"][k][i % 12] for k in range(5)))] + ([sheep_talk] if i % 2 == 0 and i else []),
                         scale=scale, anchor=anchor))
        with tempfile.TemporaryDirectory() as tmp:
            soft.chara_png(fr, f"{tmp}/s.png")
            sheet = Image.open(f"{tmp}/s.png").convert("RGBA")
        for j in range(len(fr)):
            x0, y0 = (j % soft.COLS) * CW, (j // soft.COLS) * CH
            im = sheet.crop((x0, y0, x0 + CW, y0 + CH))
            im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
            out.append(im)
    return out


def hand_frames(lines, deco, n_frames=20, sheep_poses=None):
    """筆なしの手書きセリフ。lines: (文字, 中心x, 中心y, 大きさ, 強調?)。
    1コマ目は完成形、2コマ目は空、そのあと一文字ずつポン(出た文字は 1.3 倍 → 1 倍)。
    書き終わったら、強調語がゆるく波打ち、金のキラキラが2つだけまたたく。最後に飾りがぽんと出る。"""
    chars = []
    for li, line in enumerate(lines):
        text, cx, cy, size, strong = line[:5]
        arc = line[5] if len(line) > 5 else (0.35 if strong else 0.2)   # ゆるいカーブ(山なり)
        tilt = line[6] if len(line) > 6 else (-6 if li % 2 == 0 else 4)  # 行ごとに傾きを変える
        rnd = random.Random(li * 31 + len(text))
        sizes = [size * (1.22 if j == 0 and strong else rnd.uniform(0.9, 1.06)) for j in range(len(text))]
        total = sum(sz * 0.96 for sz in sizes)
        x = -total / 2
        n = len(text)
        ra = math.radians(tilt)
        for j, ch in enumerate(text):
            adv = sizes[j] * 0.96
            lx = x + adv / 2
            t = (j + 0.5) / n - 0.5
            ly = arc * size * (4 * t * t - 1) * 0.5 + (4 if j % 2 else -3)  # カーブ + 少しの段差
            px = cx + lx * math.cos(ra) - ly * math.sin(ra)
            py = cy + lx * math.sin(ra) + ly * math.cos(ra)
            col = (RED if j % 2 == 0 else KOUBAI) if strong else soft.BROWN
            chars.append((ch, px, py, round(sizes[j]), col, GOLD_RIM if strong else None, strong,
                          tilt + rnd.uniform(-6, 6)))
            x += adv
    N = len(chars)
    n_write = n_frames - 6
    cpf = max(1, math.ceil(N / n_write))

    def draw(shown, pop_last=False, wave=None, deco_k=None, twinkle=None):
        im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        layers = []
        for i, (ch, x, y, size, col, rim, strong, rot) in enumerate(chars[:shown]):
            k = 1.2 if pop_last and i >= shown - cpf else 1.0
            if wave is not None:  # 書き終わったら、文字が順番に波のように跳ねる(強調語は大きめ)
                y += (7 if strong else 4) * math.sin(wave + i * 0.9)
            a, b = rim_glyph(ch, round(size * k), col, rim, rot=rot)
            layers.append((a, b, (round(x - a.width / 2), round(y - a.height / 2))))
        for a, b, xy in layers:
            im.alpha_composite(a, xy)
        for a, b, xy in layers:
            im.alpha_composite(b, xy)
        if twinkle is not None:
            winter.draw_marks2(im, [("spark", 28, 30, 7 + twinkle % 2 * 3), ("spark", 292, 34, 9 - twinkle % 2 * 3)],
                               0, 0)
        if deco_k is not None:
            deco(im, deco_k)
        return im

    # ひつじも一緒に出す(さびしくならないように)。ひつじはコマごとに動く
    sheep_ims = sheep_frames(sheep_poses, n_frames) if sheep_poses else None
    _draw = draw

    def draw(shown, pop_last=False, wave=None, deco_k=None, twinkle=None, _fi=[0]):
        im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        if sheep_ims:
            im.alpha_composite(sheep_ims[min(_fi[0], n_frames - 1)])
        _fi[0] += 1
        im.alpha_composite(_draw(shown, pop_last, wave, deco_k, twinkle))
        return im

    frames = [draw(N, deco_k=1.0, twinkle=0), draw(0)]
    shown = 0
    while shown < N:
        shown = min(N, shown + cpf)
        frames.append(draw(shown, pop_last=True))
    t = 0
    frames.append(draw(N, wave=0, deco_k=1.25, twinkle=0))  # 書き終わったら、飾りがぽんと出る
    while len(frames) < n_frames - 1:
        t += 1
        frames.append(draw(N, wave=t * 1.1, deco_k=1.0 + 0.08 * (t % 2), twinkle=t))
    frames.append(draw(N, deco_k=1.0, twinkle=t + 1))
    return frames[:n_frames]


HOP20 = [S, J0, S, J0, S, J0, S, J0, S, J0, S, J0, S, J0, S, J0, S, J0, S, S]
BOW20 = [B1, S, S, S, S, B1, B2, B1, S, S, B1, B2, B1, S, S, B1, B2, B1, S, S]


def hand13(icon):
    """あけおめ!: 大きく山なりに。ひつじがぴょんぴょん跳ねる。"""
    return hand_frames([("あけおめ!", 160, 80, 52, True, 0.5, -4)], lambda im, k: None,
                       sheep_poses=lambda i: [HOP20[i], happy])


def hand14(icon):
    """ことよろ!: 右上がりに。鏡餅の横で、ひつじがぺこり。"""
    return hand_frames([("ことよろ!", 166, 84, 50, True, 0.3, -8)], lambda im, k: kagami(im, 62, 252, 0.9 * k),
                       sheep_poses=lambda i: [BOW20[i], happy])


def hand15(icon):
    """今年も/よろしく/お願いします: 行ごとに傾きと位置をずらす。ひつじがぺこり。梅の枝。"""
    def deco(im, k):
        winter.draw_marks2(im, [("branch", 0, 0, 0, [(20, 236), (44, 226), (70, 240)]),
                                ("ume", 44, 226, 12 * k), ("ume", 68, 242, 9 * k)], 0, 0)
    return hand_frames([("今年も", 116, 58, 50, True, 0.3, -7), ("よろしく", 152, 118, 38, False, 0.2, 3),
                        ("お願いします", 136, 170, 28, False, 0.15, -3)], deco,
                       sheep_poses=lambda i: [BOW20[i], happy])


def hand16(icon):
    """おめでとう/ございます: 大きなカーブと、小さく段差。ひつじが跳ねて、紙ふぶき。"""
    def deco(im, k):
        winter.draw_marks(im, confetti(16, 6, round(k * 10), box=(24, 190, 130, 250)), 0, 0)
    return hand_frames([("おめでとう", 150, 66, 46, True, 0.45, -5), ("ございます", 156, 130, 36, False, 0.25, 4)],
                       deco, sheep_poses=lambda i: [HOP20[i], happy])


# ---- B. 年賀状(残り) ----------------------------------------------------------------

def vertical_chars(text, cx, top, size, step, color=INK_BLACK, font=None):
    out = []
    for k, ch in enumerate(text):
        g = glyph(ch, size, color)
        out.append((None, g, (round(cx - g.width / 2), round(top + k * step))))
    return out


def card06(icon):
    """06 あけまして/おめでとう/ございます(縦書き3列、右から)+ 左に小さく「令和九年 元旦」、ひつじとはんこ。"""
    chars = (vertical_chars("あけまして", 206, 22, 32, 36) + vertical_chars("おめでとう", 170, 22, 32, 36)
             + vertical_chars("ございます", 134, 22, 32, 36))
    date = vertical_chars("令和九年元旦", 102, 30, 17, 19)

    def deco(im, k):
        for _, g, xy in date:
            im.alpha_composite(g, xy)
        paste_center(im, icon, 104, 246, 0.8 * k)
        seal(im, 214, 230, 24 * min(k, 1.3))
    return write_frames(card_base, chars, deco, brush)


def card07(icon):
    """07 寿: 大きな1文字を、筆を左右に振りながら上から書く → 梅とはんこ。"""
    g = glyph("寿", 140)
    chars = [(None, g, (round(160 - g.width / 2), 40))]

    def deco(im, k):
        winter.draw_marks2(im, [("ume", 112, 222, 13 * k), ("ume", 134, 238, 9 * k)], 0, 0)
        seal(im, 212, 226, 26 * min(k, 1.3))
    return write_frames(card_base, chars, deco, brush)


def card08(icon):
    """08 Happy New Year 2027: 横書きのペン字で1文字ずつ → ひつじの絵。"""
    chars = []
    for text, cy, size, col in (("Happy", 58, 40, SHU), ("New Year", 104, 30, SHU), ("2027", 150, 40, INK_BLACK)):
        font = ImageFont.truetype(str(HAND_FONT), size)
        adv = [font.getlength(ch) for ch in text]
        x = 160 - sum(adv) / 2
        for ch, w in zip(text, adv):
            if ch != " ":
                g = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
                ImageDraw.Draw(g).text(((size + 20) / 2, (size + 20) / 2), ch, font=font, anchor="mm", fill=col)
                chars.append((None, g, (round(x + w / 2 - g.width / 2), round(cy - g.height / 2))))
            x += w
    return write_frames(card_base, chars, lambda im, k: paste_center(im, icon, 160, 248, 1.15 * k), pen)


def card09(icon):
    """09 謹んで/新春の/お慶びを/申し上げます(縦書き)+ 日付・ひつじ・はんこ。"""
    chars = (vertical_chars("謹んで新春の", 208, 30, 28, 31) + vertical_chars("お慶びを", 174, 30, 28, 31)
             + vertical_chars("申し上げます", 140, 30, 28, 31))
    date = vertical_chars("令和九年元旦", 108, 40, 16, 18)

    def deco(im, k):
        for _, g, xy in date:
            im.alpha_composite(g, xy)
        paste_center(im, icon, 104, 246, 0.8 * k)
        seal(im, 214, 230, 24 * min(k, 1.3))
    return write_frames(card_base, chars, deco, brush)


def card10(icon):
    """10 福: 大きな1文字 → 梅と金のキラキラ、はんこ。"""
    g = glyph("福", 136)
    chars = [(None, g, (round(162 - g.width / 2), 44))]

    def deco(im, k):
        winter.draw_marks2(im, [("ume", 112, 222, 13 * k), ("ume", 134, 238, 9 * k), ("spark", 206, 60, 8 * k)], 0, 0)
        seal(im, 212, 226, 26 * min(k, 1.3))
    return write_frames(card_base, chars, deco, brush)


def card11(icon):
    """11 初春(縦に大きく2文字)→ ひつじ・はんこ。"""
    chars = vertical_chars("初春", 176, 34, 84, 86)

    def deco(im, k):
        paste_center(im, icon, 112, 246, 0.9 * k)
        seal(im, 214, 230, 24 * min(k, 1.3))
    return write_frames(card_base, chars, deco, brush)


def card12(icon):
    """12 あけおめ/ことよろ(縦書き2列、友だち向け)→ ひつじ。"""
    chars = vertical_chars("あけおめ", 192, 34, 42, 44) + vertical_chars("ことよろ", 142, 34, 42, 44)

    def deco(im, k):
        paste_center(im, icon, 112, 248, 0.8 * k)
        winter.draw_marks2(im, [("ume", 214, 230, 11 * k)], 0, 0)
    return write_frames(card_base, chars, deco, brush)


CARDS = {"05": card05, "06": card06, "07": card07, "08": card08, "09": card09, "10": card10, "11": card11,
         "12": card12, "13": hand13, "14": hand14, "15": hand15, "16": hand16}


def card_sheet(frames, path, cols=5, rows=4):
    sheet = Image.new("RGBA", (CW * cols, CH * rows), inko.BG)
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, ((i % cols) * CW, (i // cols) * CH))
    sheet.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", choices=sorted(list(STAMPS) + list(CARDS)))
    ap.add_argument("--png", required=True)
    a = ap.parse_args()
    if a.stamp in CARDS:
        frames = CARDS[a.stamp](sheep_icon(56))
        card_sheet(frames, a.png)
        print(f"シート: {a.png}(年賀状 {len(frames)}コマ, 5x4)")
        return
    frames = STAMPS[a.stamp]
    with tempfile.TemporaryDirectory() as tmp:
        soft.chara_png(frames, f"{tmp}/c.png")
        soft.text_png(frames, f"{tmp}/t.png")
        sheet = Image.new("RGBA", (soft.CW * soft.COLS, soft.CH * soft.ROWS), inko.BG)
        sheet.alpha_composite(Image.open(f"{tmp}/c.png").convert("RGBA"))
        sheet.alpha_composite(Image.open(f"{tmp}/t.png").convert("RGBA"))
        sheet.convert("RGB").save(a.png)
    print(f"シート: {a.png}")


if __name__ == "__main__":
    main()
