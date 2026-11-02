#!/usr/bin/env python3
"""ていねいインコ set03「ひつじ年のお正月」: ひつじのキャラと、筆で書いていく年賀状。

  確認用シート : python3 tools/newyear.py 01 --png sheet.png
  (キャラのスタンプは 12コマ=4x3、年賀状は 20コマ=5x4 のシートになる)

決まりごと(docs/stamp_rules.md)はそのまま守る。キャラの動きは winter.py / soft.py と同じ仕組み。
"""
import argparse
import math
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import inko
import soft
import winter
from soft import kf, S, J0, J1, J2, B1, B2, happy, talk, step, flap, tuft, TUFT
from winter import add, head_off, face_off, HORN, confetti, make, MID

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

def cf01(i, av):
    return confetti(31, 4, i, box=(240, 30, 296, 84)) + confetti(32, 4, i, box=(30, 196, 112, 250))


EAR01 = ([0, -12, 6, -12, 6, -10, 4, -12, 6, -10, 4, 0],     # 耳: 左右で逆に、ぴくぴく
         [0, 6, -12, 6, -12, 4, -10, 6, -12, 4, -10, 0])

STAMPS = {
    "01": make("new", [("あけまして", 46, True), ("おめでとう", 34, False), ("ございます", 34, False)], "A",
               lambda i: [[S, happy], [J0, happy], [J1, happy], [J1, happy, J2], [J1, happy], [J0, happy],
                          [S, happy], [B1, happy], [B2, happy], [B1, happy], [S, happy], [S, happy]][i]
               + [ears(EAR01[0][i], EAR01[1][i]), sheep], cf01, m=MID),
}

LEGS = {  # (左前足の持ち上げpx, 右前足の持ち上げpx, 左前足の角度, 右前足の角度, 後ろ足の持ち上げpx)
    # 前足は付け根を支点に最大16°・持ち上げ最大5px、後ろ足は最大3px。左右で交互・別の角度
    "01": ([0, 2, 5, 5, 4, 0, 4, 0, 3, 0, 4, 0],
           [0, 0, 4, 5, 5, 2, 0, 4, 0, 3, 0, 4],
           [0, -6, 16, 14, 10, -4, 12, -2, 10, -2, 12, 0],
           [0, -4, 12, 16, 12, -6, -2, 12, -2, 10, -2, 12],
           [0, 3, -3, 0, 0, 3, -3, 3, -3, 3, -3, 0]),
}

for name, frames in STAMPS.items():
    ll, lr, al, ar, hd = LEGS[name]
    for i, fr in enumerate(frames):
        extra = []
        if i in soft.TALK_FRAMES:
            extra.append(sheep_talk)
        if i:
            extra.append(legs(ll[i], lr[i], al[i], ar[i], hd[i]))
        fr["poses"] = fr["poses"] + extra


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
    return im


def glyph(ch, size, color=INK_BLACK):
    font = ImageFont.truetype(str(BRUSH_FONT), size)
    g = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
    # 少し太らせて、筆の墨のたっぷりした感じを出す
    ImageDraw.Draw(g).text(((size + 20) / 2, (size + 20) / 2), ch, font=font, anchor="mm", fill=color,
                           stroke_width=1, stroke_fill=color)
    return g


def reveal(g, k, n=4):
    """書いている途中: 字を上から n 本の帯に分け、k 本目まで見せる。
    筆は帯ごとに左右へ振れながら下りる(偶数本目は右端、奇数本目は左端で止まる)。戻り値は (画像, 筆先の位置)。"""
    bb = g.getbbox()
    x0, y0, x1, y1 = bb
    y = y0 + (y1 - y0) * (k + 1) / n
    out = g.copy()
    if k < n - 1:
        ImageDraw.Draw(out).rectangle((0, round(y), g.width, g.height), fill=(0, 0, 0, 0))
    bx = x1 - 4 if k % 2 == 0 else x0 + 4
    return out, (bx, y)


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
        d = ImageDraw.Draw(im)
        d.ellipse((94, 28, 106, 40), fill="#F49CB4", outline=soft.LINE, width=2)  # 左上の小さな梅
        d.ellipse((98, 32, 102, 36), fill="#FFD24D")
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


CARDS = {"05": card05}


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
