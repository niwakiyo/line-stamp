#!/usr/bin/env python3
"""ていねいインコ set02「冬と年末年始の敬語」: soft.py のインコに、季節の小物と演出を足す。

  確認用シート : python3 tools/winter.py 05 --png sheet.png
  Canva用      : python3 tools/winter.py 05 --text-png text.png --ops ops.json --page PAGE_ID

決まりごと(docs/stamp_rules.md)はそのまま守る:
- 腕は肩を支点に、左右別々に最大16°(ARMS)。小物を持つ腕も同じ。
- 頭に着ける小物は頭の毛(P1)の位置から、首まわりの小物はくちばし(P14)の位置から置くので、
  おじぎ・ジャンプ・震えでも頭や体について行く。
- 背景の演出(初日の出など)は体の後ろ(BG_*)、雪・紙ふぶきはセリフと同じ前面の層に描く。
"""
import argparse
import json
import math
import random
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

import inko
import soft
from soft import kf, word, S, J0, J1, J2, B1, B2, happy, blink, talk, step, flap, tuft, TUFT

BROWN = soft.BROWN
GOLD = "#E8B33A"
PAL = {  # 時期ごとのセリフの色(強調語, 語尾, 外側のフチ)
    "end": ("#E5404F", BROWN, None),
    "new": ("#E0352B", BROWN, GOLD),
    "win": ("#4F86D9", BROWN, None),
}

# ---- 小物(キャラの部品として足す) --------------------------------------------
# 重なり順: BG_* は体より後ろ、MID_* は体と羽の間(マフラーなど)、ACC_* は一番前。
# 名前の順(BG1 < BG2 ...)がそのまま重なり順になる。

ORDER = list(inko.BASE)
_base_order = soft.inko_order


def inko_order(key):
    if key.startswith("BG"):
        return -1
    if key.startswith("MID"):
        return ORDER.index("P6") - 0.5
    return _base_order(key)


soft.inko_order = inko_order


def add(c, key, fill, stroke, sw, w, h, left, top, d, rot=0):
    """部品を重なり順の正しい位置に差し込む(確認用の SVG は dict の順に描くため)。"""
    e = inko.part(fill, stroke, sw, w, h, left, top, d)
    e["rot"] = rot
    items = list(c.items())
    c.clear()
    placed = False
    for k, v in items:
        if not placed and inko_order(k) > inko_order(key):
            c[key] = e
            placed = True
        c[k] = v
    if not placed:
        c[key] = e


def head_off(c):
    b = inko.BASE["P1"]
    return c["P1"]["left"] - b["left"], c["P1"]["top"] - b["top"]


def face_off(c):
    b = inko.BASE["P14"]
    return c["P14"]["left"] - b["left"], c["P14"]["top"] - b["top"]


LOOP_L = "M17 8 C12 2 4 0 1.5 4 C0 8 4 13 10 12 C13 11.5 15.5 10 17 8 Z"
LOOP_R = "M1 8 C6 2 14 0 16.5 4 C18 8 14 13 8 12 C5 11.5 2.5 10 1 8 Z"
TAIL = "M2 1 C4 6 5 11 4 17 L8 17 C9 11 8 6 6 1 Z"
DOT = "M20 2 C30 2 38 10 38 20 C38 30 30 38 20 38 C10 38 2 30 2 20 C2 10 10 2 20 2 Z"  # 40x40 の丸(手描きの揺れが目立たない大きさ)


def mizuhiki(c, k=1.35):
    """頭の右上に紅白の水引飾り(白い輪・赤い輪・金の結び目・赤白の垂れ)。k は大きさ。"""
    ox, oy = head_off(c)
    x, y = 194 + ox, 146 + oy  # 結び目の中心(頭の右上の輪郭の少し内側)

    def put(key, fill, w, h, dx, dy, d, rot):
        add(c, key, fill, inko.INK, 2, w * k, h * k, x + dx * k, y + dy * k, d, rot=rot)
        c[key].update(vw=w, vh=h)
    put("ACC1_tailW", "#FFFFFF", 9, 18, -8, 1, TAIL, 18)
    put("ACC2_tailR", "#E0352B", 9, 18, -1, 1, TAIL, -12)
    put("ACC3_loopW", "#FFFFFF", 18, 14, -17, -9, LOOP_L, -8)
    put("ACC4_loopR", "#E0352B", 18, 14, 0, -10, LOOP_R, 8)
    put("ACC5_knot", GOLD, 10, 10, -5, -5, DOT, 0)
    c["ACC5_knot"].update(vw=40, vh=40)


SCARF = "M1 4 C30 13 76 13 105 4 L105 16 C76 25 30 25 1 16 Z"
SCARF_TAIL = "M2 1 L16 1 L17 30 L14 34 L11 30 L8 34 L5 30 L2 34 Z"
STRIPE = "M1 1 L15 1 L15 5 L1 5 Z"


def scarf(color, stripe, k=1.0):
    """首(くちばしの下)に巻くマフラー。体と羽の間に入れる。
    k: 顔が下がった分のうち、マフラーを下げる割合(おじぎで体からはみ出さないよう 0.55 にする)。"""
    def f(c):
        ox, oy = face_off(c)
        oy *= k
        add(c, "MID1_tail", color, inko.INK, 2, 18, 35, 184 + ox, 210 + oy, SCARF_TAIL, rot=-6)
        add(c, "MID2_tailst", stripe, None, 0, 16, 6, 185 + ox, 224 + oy, STRIPE, rot=-6)
        add(c, "MID3_band", color, inko.INK, 2, 106, 26, 107 + ox, 198 + oy, SCARF)
        add(c, "MID4_bandst", stripe, None, 0, 90, 4, 115 + ox, 207 + oy,
            "M1 1 C30 7 60 7 89 1 L89 3.5 C60 9.5 30 9.5 1 3.5 Z")
    return f


HAT_DOME = "M2 30 C2 12 20 2 40 2 C60 2 78 12 78 30 Z"
HAT_BAND = "M1 2 C30 9 58 9 87 2 L87 12 C58 19 30 19 1 12 Z"


def knit_hat(dome, band):
    """毛糸の帽子(ぼんぼり付き)。頭の毛の位置から置くので、頭について行く。"""
    def f(c):
        ox, oy = head_off(c)
        add(c, "ACC1_hat", dome, inko.INK, 2, 80, 32, 120 + ox, 124 + oy, HAT_DOME)
        add(c, "ACC2_band", band, inko.INK, 2, 88, 18, 116 + ox, 150 + oy, HAT_BAND)
        add(c, "ACC3_pom", "#FFFFFF", inko.INK, 2, 20, 20, 150 + ox, 110 + oy, DOT)
        c["ACC3_pom"].update(vw=40, vh=40)
    return f


SUN = "M40 2 C61 2 78 19 78 40 C78 61 61 78 40 78 C19 78 2 61 2 40 C2 19 19 2 40 2 Z"
CLOUD = ("M8 22 C2 22 1 14 7 12 C7 5 15 3 19 8 C22 2 32 2 35 9 C41 7 47 12 44 18 "
         "C49 19 49 26 43 26 L10 26 C7 26 6 23 8 22 Z")
RAY = "M2 1 L12 1 C13.5 1 13.5 4 12 4 L2 4 C0.5 4 0.5 1 2 1 Z"


def sunrise(k):
    """体の後ろ(右上)に初日の出。光の線はコマごとに長さを変えてきらめかせる(体には付いて行かない)。"""
    def f(c):
        cx, cy, r = 194, 150, 36
        for j, a in enumerate((-160, -125, -90, -55, -20, 15)):
            ra = math.radians(a)
            L = 10  # 光の線は動かさない(容量を抑えて色数を保つ)
            d = r + 7
            x, y = cx + d * math.cos(ra), cy + d * math.sin(ra)
            add(c, f"BG1_ray{j}", "#FFD24D", inko.INK, 1.5, L, 5,
                x + (L / 2) * math.cos(ra) - L / 2, y + (L / 2) * math.sin(ra) - 2.5, RAY, rot=a)
        add(c, "BG2_sun", "#FFA94D", inko.INK, 2, 2 * r, 2 * r, cx - r, cy - r, SUN)
        add(c, "BG3_cloud", "#FFFFFF", inko.INK, 2, 50, 28, cx + 2, cy + 14, CLOUD)
    return f


# ---- 前面の演出(セリフと同じ層) -----------------------------------------------

_draw_marks = soft.draw_marks


def draw_marks(layer, marks, ox, oy):
    d = ImageDraw.Draw(layer)
    rest = []
    for m in marks:
        kind, x, y, s = m[:4]
        x, y = ox + x, oy + y
        if kind == "snow":  # 雪の粒
            d.ellipse((x - s, y - s, x + s, y + s), fill="white", outline=soft.LINE, width=2)
        elif kind == "flake":  # 雪の結晶(6本の腕)
            for a in (0, 60, 120):
                ra = math.radians(a + m[4] if len(m) > 4 else a)
                p0 = (x - s * math.cos(ra), y - s * math.sin(ra))
                p1 = (x + s * math.cos(ra), y + s * math.sin(ra))
                d.line([p0, p1], fill=soft.LINE, width=6)
            for a in (0, 60, 120):
                ra = math.radians(a + m[4] if len(m) > 4 else a)
                p0 = (x - s * math.cos(ra), y - s * math.sin(ra))
                p1 = (x + s * math.cos(ra), y + s * math.sin(ra))
                d.line([p0, p1], fill="white", width=3)
        elif kind == "confetti":  # 紙ふぶき(金・赤・白の小さな四角)
            color, rot = m[4], m[5]
            r = math.radians(rot)
            pts = [(x + px * math.cos(r) - py * math.sin(r), y + px * math.sin(r) + py * math.cos(r))
                   for px, py in ((-s, -s * 0.6), (s, -s * 0.6), (s, s * 0.6), (-s, s * 0.6))]
            d.polygon(pts, fill=color, outline=soft.LINE, width=2)
        elif kind == "breath":  # 白い息(丸を3つ重ねたもや)
            for bx, by, br in ((0, 0, s), (-s * 0.9, s * 0.25, s * 0.7), (s * 0.85, s * 0.3, s * 0.65)):
                d.ellipse((x + bx - br, y + by - br, x + bx + br, y + by + br), fill="white", outline=soft.LINE,
                          width=2)
            for bx, by, br in ((0, 0, s - 2), (-s * 0.9, s * 0.25, s * 0.7 - 2), (s * 0.85, s * 0.3, s * 0.65 - 2)):
                d.ellipse((x + bx - br, y + by - br, x + bx + br, y + by + br), fill="white")
        else:
            rest.append(m)
    _draw_marks(layer, rest, ox, oy)


soft.draw_marks = draw_marks


def confetti(seed, n=7, fall=0, box=(18, 18, 302, 140)):
    """紙ふぶき。seed ごとに位置を決め、fall で下へ流す(コマごとに fall を増やす)。"""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        x = rnd.uniform(box[0], box[2])
        y = box[1] + (rnd.uniform(0, box[3] - box[1]) + fall * (0.8 + 0.4 * (i % 3))) % (box[3] - box[1])
        out.append(("confetti", x, y, rnd.choice((7, 8)), rnd.choice((GOLD, "#E0352B", "#FFFFFF", GOLD)),
                    rnd.uniform(0, 180) + fall * 7))
    return out


def snow(seed, n=8, fall=0, box=(30, 30, 290, 246), avoid=()):
    """雪の粒。avoid の四角(キャラ・文字)に入る粒は描かない。"""
    rnd = random.Random(seed)
    out = []
    for i in range(n * 3):
        x = rnd.uniform(box[0], box[2]) + 4 * math.sin(fall * 0.7 + i)
        y = box[1] + (rnd.uniform(0, box[3] - box[1]) + fall * 8) % (box[3] - box[1])
        flake = i % 3 == 0
        r = rnd.choice((9, 10, 11)) if flake else rnd.choice((4, 5, 6))
        if any(a[0] - r < x < a[2] + r and a[1] - r < y < a[3] + r for a in avoid):
            continue
        out.append(("flake", x, y, r, fall * 12) if flake else ("snow", x, y, r))
    return out


# ---- セリフ ------------------------------------------------------------------

def say(pal, *parts):
    """parts: (文字, 中心x, 中心y, 大きさ, 傾き, 強調?, 追加の設定) を並べる。"""
    key, rest, rim = PAL[pal]
    ws = []
    for i, (text, x, y, size, rot, strong, extra) in enumerate(parts):
        w = word(text, x, y, size, key if strong else rest, rot=rot, seed=i + 1, arc=0 if strong else 0.15,
                 **extra)
        if strong and rim:
            w.update(rim=rim, rim_w=4)
        ws.append(w)
    return ws


# 05 あけまして/おめでとう/ございます: 「あけまして」がポン、跳ねて着地したら「おめでとうございます」。
def t05(n1=None, last1=1.0, n2=0, n3=0, s1=1.0, s2=1.0, bob=0):
    parts = [("あけまして", 148, 46 + bob, 46, -4, True, dict(count=n1, last=last1, scale=s1))]
    if n2:  # 年賀状のように、右の列から縦に書く
        parts.append(("おめでとう", 84, 158 + bob, 28, 0, False, dict(count=n2, scale=s2, vertical=True)))
    if n3:
        parts.append(("ございます", 48, 164 + bob, 27, 0, False, dict(count=n3, scale=s2, vertical=True)))
    return say("new", *parts)


M05 = dict(scale=1.2, anchor=(200, 252))
SUN05 = [sunrise(k) for k in range(2)]


def cf(i):
    return confetti(5, 6, i, box=(120, 74, 292, 120))


# 12 寒く/なりましたね: 全文を出したまま、「寒く」だけぶるぶる(C型)。マフラーで震え、白い息。
def t12(shiver=None, bob=0):
    return say("win", ("寒く", 92, 52 + bob, 64, -6, True, dict(shiver=shiver)),
               ("なりましたね", 114, 104 + bob, 31, -3, False, {}))


M12 = dict(scale=1.12, anchor=(226, 254))
HAT_W = knit_hat("#8FB8EE", "#FFFFFF")


SCARF_W = scarf("#5B8FE0", "#CFE0FA")


def hug(c):
    """寒くて羽を体に寄せる(肩を支点に内側へ 12°)。"""
    flap("P6", -12)(c)
    flap("P7", -12)(c)


def X(c):
    inko.eyes(c, "X")


def sh(dx):
    return inko.shake(dx)


def snow12(fall):
    return snow(12, 9, fall, avoid=((150, 84, 300, 262), (14, 14, 236, 128), (86, 136, 160, 200)))


def br(i):
    """白い息: くちばしの左下からふわっと出て、少しずつ大きく・上へ。"""
    return [("breath", 138 - i * 7, 176 - i * 5, 9 + i * 2)] if i >= 0 else []


STAMPS = {
    "05": [kf([S, happy, mizuhiki, SUN05[0]], t05(n2=5, n3=5), cf(0), **M05),
           kf([J0, happy, mizuhiki, SUN05[1]], [], cf(1), **M05),
           kf([J1, happy, mizuhiki, SUN05[0]], t05(n1=2, last1=1.3), cf(2), **M05),
           kf([J1, happy, J2, mizuhiki, SUN05[1]], t05(n1=4, last1=1.3), cf(3), **M05),
           kf([J1, happy, mizuhiki, SUN05[0]], t05(s1=1.1), cf(4), **M05),
           kf([J0, happy, mizuhiki, SUN05[1]], t05(s1=0.96), cf(5), **M05),
           kf([S, happy, mizuhiki, SUN05[0]], t05(n2=3), cf(6), **M05),
           kf([B1, happy, mizuhiki, SUN05[1]], t05(n2=5, s2=1.15), cf(7), **M05),
           kf([B2, happy, mizuhiki, SUN05[0]], t05(n2=5, n3=3), cf(8), **M05),
           kf([B1, happy, mizuhiki, SUN05[1]], t05(n2=5, n3=5, s2=1.1), cf(9), **M05),
           kf([S, happy, mizuhiki, SUN05[0]], t05(n2=5, n3=5, bob=1), cf(10), **M05),
           kf([S, happy, mizuhiki, SUN05[1]], t05(n2=5, n3=5), cf(11), **M05)],
    "12": [kf([S, X, hug, SCARF_W, HAT_W], t12(), snow12(0), **M12),
           kf([S, X, hug, sh(-2), SCARF_W, HAT_W], t12(shiver=(2, 4, 1)), snow12(1), **M12),
           kf([S, X, hug, sh(2), SCARF_W, HAT_W], t12(shiver=(2, 4, 2)), snow12(2) + br(0), **M12),
           kf([S, X, hug, sh(-2), SCARF_W, HAT_W], t12(shiver=(2, 4, 3)), snow12(3) + br(1), **M12),
           kf([S, X, hug, sh(2), SCARF_W, HAT_W], t12(shiver=(2, 4, 4)), snow12(4) + br(2), **M12),
           kf([S, X, hug, sh(-2), SCARF_W, HAT_W], t12(shiver=(2, 4, 5)), snow12(5) + br(3), **M12),
           kf([S, X, hug, sh(2), SCARF_W, HAT_W], t12(shiver=(1, 2, 6)), snow12(6), **M12),
           kf([S, X, hug, sh(-2), SCARF_W, HAT_W], t12(shiver=(2, 4, 7)), snow12(7), **M12),
           kf([S, X, hug, sh(2), SCARF_W, HAT_W], t12(shiver=(2, 4, 8)), snow12(8) + br(0), **M12),
           kf([S, X, hug, sh(-2), SCARF_W, HAT_W], t12(shiver=(2, 4, 9)), snow12(9) + br(1), **M12),
           kf([S, X, hug, sh(2), SCARF_W, HAT_W], t12(shiver=(2, 4, 10)), snow12(10) + br(2), **M12),
           kf([S, X, hug, SCARF_W, HAT_W], t12(), snow12(11) + br(3), **M12)],
}

ARMS = {  # (左腕, 右腕)  肩を支点に最大16°。左右で角度とタイミングを変える
    "05": ([0, -6, 14, 16, 12, -4, 4, -8, -12, -8, 6, 2],     # 跳ぶときは羽を開き、おじぎで体の前へ
           [0, -4, 10, 14, 16, -6, 8, -6, -10, -6, 2, 6]),
    "12": ([0, 3, -2, 3, -2, 3, -1, 3, -2, 3, -2, 1],         # 寄せた羽をこまかく震わせる(左右で逆)
           [0, -2, 3, -2, 3, -2, 1, -2, 3, -2, 3, -1]),
}

# ==== 残りの14個 ===============================================================

# ---- 小物(追加) ----------------------------------------------------------------

def shape_of(poses):
    """ポーズを当てたあとの部品(頭・顔のずれを知るため)。"""
    import copy
    c = copy.deepcopy(inko.BASE)
    for p in poses:
        p(c)
    return c


SANTA_TAIL = "M2 10 C14 0 30 4 34 24 L27 26 C25 15 17 11 5 17 Z"


def santa_hat(lag=0):
    """サンタ帽。先っぽとぼんぼりは lag だけ遅れて揺れる。"""
    def f(c):
        ox, oy = head_off(c)
        add(c, "ACC1_hat", "#E5404F", inko.INK, 2, 80, 32, 120 + ox, 124 + oy, HAT_DOME)
        add(c, "ACC2_tail", "#E5404F", inko.INK, 2, 36, 28, 176 + ox + lag * 0.4, 112 + oy, SANTA_TAIL, rot=lag * 2)
        add(c, "ACC3_band", "#FFFFFF", inko.INK, 2, 88, 18, 116 + ox, 150 + oy, HAT_BAND)
        add(c, "ACC4_pom", "#FFFFFF", inko.INK, 2, 20, 20, 200 + ox + lag, 128 + oy, DOT)
        c["ACC4_pom"].update(vw=40, vh=40)
    return f


VEST_L = "M10 3 C20 1 34 6 40 14 L38 64 C26 66 13 60 7 50 C1 38 1 18 10 3 Z"
VEST_R = "M30 3 C20 1 6 6 0 14 L2 64 C14 66 27 60 33 50 C39 38 39 18 30 3 Z"


def hanten(c):
    """えんじ色のはんてん(体の左右を包む。羽より後ろ)。"""
    ox, oy = face_off(c)
    add(c, "MID1_vl", "#A8324A", inko.INK, 2, 34, 48, 110 + ox, 202 + oy, VEST_L)
    add(c, "MID2_vr", "#A8324A", inko.INK, 2, 32, 48, 178 + ox, 202 + oy, VEST_R)
    for k in ("MID1_vl", "MID2_vr"):
        c[k].update(vw=42 if k == "MID1_vl" else 40, vh=66)


CUP = "M2 2 L26 2 C26 14 23 22 14 22 C5 22 2 14 2 2 Z"


def cup(c):
    """湯のみ(体の前で両羽に持つ)。"""
    ox, oy = face_off(c)
    add(c, "ACC1_cup", "#F3E3C3", inko.INK, 2, 28, 24, 146 + ox, 220 + oy, CUP)
    add(c, "ACC2_cupband", "#7A9AD6", None, 0, 22, 4, 149 + ox, 226 + oy, STRIPE)
    c["ACC2_cupband"].update(vw=16, vh=6)


FAN_SEG = "M0 0 L60 -8 C61 -3 61 3 60 8 Z"


def fan(c):
    """後ろで開く紅白の扇(体には付いて行かない)。"""
    cx, cy = 160, 168
    for j, a in enumerate(range(-170, -5, 15)):
        col = "#E0352B" if j % 2 == 0 else "#FFFFFF"
        e = inko.part(col, inko.INK, 1.5, 62, 18, cx, cy - 9, FAN_SEG.replace("-8", "1").replace("0 0", "0 9")
                      .replace("60 1", "60 1").replace("60 8", "60 17").replace("61 -3", "61 6").replace("61 3", "61 12"))
        e.update(vw=62, vh=18, rot=a)
        # 扇の要(かなめ)を中心に回す: 左端の中央が (cx, cy) に来るよう、中心を回した位置に置く
        ra = math.radians(a)
        mx, my = cx + 31 * math.cos(ra), cy + 31 * math.sin(ra)
        e["left"], e["top"] = mx - 31, my - 9
        c_items = list(c.items())
        c.clear()
        c[f"BG1_fan{j:02d}"] = e
        c.update(c_items)
    add(c, "BG2_rim", GOLD, inko.INK, 1.5, 12, 12, cx - 6, cy - 6, DOT)
    c["BG2_rim"].update(vw=40, vh=40)


HOOD = soft.scallop(124, 104, bumps=16, depth=3.2)
FRINGE = "M2 14 C4 4 12 2 16 8 C20 0 30 0 34 8 C38 0 48 0 52 8 C56 0 66 0 70 8 C74 2 82 4 84 14 C60 20 26 20 2 14 Z"
HORN = "M14 2 C24 2 28 12 24 20 C20 27 10 26 8 19 C6 13 12 10 16 13 C19 15 17 19 14 18 C10 4 4 8 4 8 C6 3 10 2 14 2 Z"


def sheep_hood(c):
    """ひつじのもこもこフード(頭のうしろ・前髪・くるんとした角)。頭について行く。"""
    ox, oy = head_off(c)
    add(c, "BG1_hood", "#FFFFFF", inko.INK, 2, 124, 104, 98 + ox, 118 + oy, HOOD)
    c["BG1_hood"].update(vw=124, vh=104)
    add(c, "ACC1_fringe", "#FFFFFF", inko.INK, 2, 86, 20, 117 + ox, 130 + oy, FRINGE)
    add(c, "ACC2_hornL", "#F3D9A8", inko.INK, 2, 28, 28, 92 + ox, 146 + oy, HORN, rot=-10)
    add(c, "ACC3_hornR", "#F3D9A8", inko.INK, 2, 28, 28, 200 + ox, 146 + oy, HORN, rot=190 - 360)
    c["ACC3_hornR"]["d"] = HORN  # 右の角は左右反転の代わりに回して置く


DARUMA = "M22 2 C36 2 42 14 42 26 C42 40 34 46 22 46 C10 46 2 40 2 26 C2 14 8 2 22 2 Z"
DFACE = "M13 2 C20 2 24 6 24 10 C24 15 20 18 13 18 C6 18 2 15 2 10 C2 6 6 2 13 2 Z"


def daruma(rot=0):
    """赤いだるま(体の前で抱える)。rot で起き上がりこぼしのように揺れる(底を支点)。"""
    def f(c):
        ox, oy = face_off(c)
        px, py = 160 + ox, 250 + oy  # 底(支点)
        ra = math.radians(rot)

        def put(key, fill, sw, w, h, cx, cy, d):
            dx, dy = cx - px, cy - py
            x = px + dx * math.cos(ra) - dy * math.sin(ra)
            y = py + dx * math.sin(ra) + dy * math.cos(ra)
            add(c, key, fill, inko.INK if sw else None, sw, w, h, x - w / 2, y - h / 2, d, rot=rot)
        put("ACC1_daruma", "#E0352B", 2, 44, 48, 160 + ox, 226 + oy, DARUMA)
        put("ACC2_dface", "#FFF6E8", 1.5, 26, 20, 160 + ox, 218 + oy, DFACE)
        put("ACC3_deyeL", "#3A2E39", 0, 5, 5, 155 + ox, 218 + oy, DOT)
        put("ACC4_deyeR", "#3A2E39", 0, 5, 5, 165 + ox, 218 + oy, DOT)
        put("ACC5_dbelly", GOLD, 0, 18, 5, 160 + ox, 238 + oy, STRIPE)
        for k in ("ACC3_deyeL", "ACC4_deyeR"):
            c[k].update(vw=40, vh=40)
        c["ACC5_dbelly"].update(vw=16, vh=6)
    return f


CRANE = "M1 15 L13 11 L16 1 L19 11 L31 6 L24 16 L15 22 Z"


def crane(rise=0):
    """折り鶴(差し出した右の羽の上に、ふわっと浮かぶ)。"""
    def f(c):
        ox, oy = face_off(c)
        add(c, "ACC1_crane", "#E0352B", inko.INK, 2, 46, 32, 180 + ox, 146 + oy - rise, CRANE, rot=-8)
        c["ACC1_crane"].update(vw=34, vh=24)
    return f


PAPER = "M2 2 L26 2 L26 40 L2 40 Z"


def omikuji(c):
    """おみくじの紙(両羽で体の前に持つ)。"大吉" の文字はセリフの層に描く。"""
    ox, oy = face_off(c)
    add(c, "ACC1_paper", "#FFFFFF", inko.INK, 2, 30, 42, 145 + ox, 202 + oy, PAPER)
    add(c, "ACC2_paperband", "#E0352B", None, 0, 26, 6, 147 + ox, 205 + oy, STRIPE)
    c["ACC2_paperband"].update(vw=16, vh=6)


BOOT = "M5 1 L17 1 L17 11 C21 11 24 14 24 19 L2 19 L2 11 Z"


def boots(c):
    """赤い長ぐつ(足の部品を長ぐつの形に替える。足ぶみはそのまま)。"""
    for k in ("P2", "P3"):
        c[k].update(d=BOOT, fill="#E0352B", h=18, top=c[k]["top"] - 6, vw=26, vh=20)


SNOWBANK = "M2 26 C30 10 80 4 120 8 C160 12 200 14 236 26 Z"


def snowbank(c):
    """足元の雪(体には付いて行かない)。"""
    add(c, "BG1_snow", "#FFFFFF", inko.INK, 2, 136, 16, 92, 246, SNOWBANK)
    c["BG1_snow"].update(vw=238, vh=28)


YUTANPO = "M8 2 L40 2 C45 2 46 6 46 10 L46 24 C46 28 44 30 40 30 L8 30 C3 30 2 27 2 24 L2 10 C2 6 3 2 8 2 Z"


def yutanpo(c):
    """湯たんぽ(体の前で両羽に持つ)。"""
    ox, oy = face_off(c)
    add(c, "ACC1_yt", "#F07A4A", inko.INK, 2, 48, 32, 136 + ox, 208 + oy, YUTANPO)
    for j in range(3):
        add(c, f"ACC2_ytl{j}", "#F8A27E", None, 0, 36, 3, 142 + ox, 216 + oy + j * 6, STRIPE)
        c[f"ACC2_ytl{j}"].update(vw=16, vh=6)
    add(c, "ACC3_ytcap", "#FFD24D", inko.INK, 1.5, 10, 10, 176 + ox, 203 + oy, DOT)
    c["ACC3_ytcap"].update(vw=40, vh=40)


KOTATSU_TOP = "M4 2 L184 2 C188 2 190 4 190 8 L190 12 C190 15 188 16 184 16 L4 16 C2 16 0 15 0 12 L0 8 C0 4 2 2 4 2 Z"
FUTON = "M8 2 L160 2 C166 2 170 8 170 16 L170 46 L0 46 L0 16 C0 8 2 2 8 2 Z"


def kotatsu(c):
    """こたつ(体の前。体には付いて行かない)。天板の上にみかん。"""
    add(c, "ACC1_futon", "#B5334A", inko.INK, 2, 140, 46, 90, 216, FUTON)
    c["ACC1_futon"].update(vw=172, vh=48)
    for j, x in enumerate((104, 132, 160, 188, 214)):
        add(c, f"ACC2_fdot{j}", "#E7899A", None, 0, 9, 9, x, 236 + (j % 2) * 8, DOT)
        c[f"ACC2_fdot{j}"].update(vw=40, vh=40)
    add(c, "ACC3_top", "#C8925C", inko.INK, 2, 160, 16, 80, 204, KOTATSU_TOP)
    c["ACC3_top"].update(vw=192, vh=18)
    add(c, "ACC4_mikan", "#FFA234", inko.INK, 2, 20, 18, 206, 188, DOT)
    add(c, "ACC5_cup", "#F3E3C3", inko.INK, 2, 20, 18, 92, 188, CUP)
    c["ACC5_cup"].update(vw=28, vh=24)
    c["ACC4_mikan"].update(vw=40, vh=40)


MUFF_BAND = "M4 38 C4 14 26 2 50 2 C74 2 96 14 96 38 L88 38 C88 20 72 10 50 10 C28 10 12 20 12 38 Z"


def earmuffs(c):
    """桃色のふわふわ耳あて(頭について行く)。"""
    ox, oy = head_off(c)
    add(c, "ACC1_band", "#F49CB4", inko.INK, 2, 100, 40, 110 + ox, 128 + oy, MUFF_BAND)
    for k, x in (("ACC2_muffL", 98), ("ACC3_muffR", 196)):
        add(c, k, "#FFC4D2", inko.INK, 2, 26, 28, x + ox, 152 + oy, soft.scallop(26, 28, bumps=10, depth=1.6))
        c[k].update(vw=26, vh=28)


def hold(deg=12):
    """両羽を体の前に寄せて、物を持つ・胸に当てる(肩を支点に内側へ)。"""
    def f(c):
        flap("P6", -deg)(c)
        flap("P7", -deg)(c)
    return f


def raise_r(deg=14):
    def f(c):
        flap("P7", deg)(c)
    return f


# ---- 前面の演出(追加) ------------------------------------------------------------

_draw_marks2 = soft.draw_marks


def draw_marks2(layer, marks, ox, oy):
    d = ImageDraw.Draw(layer)
    rest = []
    for m in marks:
        kind, x, y, s = m[:4]
        x, y = ox + x, oy + y
        if kind == "bell":  # 金のベル(上の点を支点に揺れる)
            rot = math.radians(m[4])
            pts = []
            for t in [k / 12 for k in range(13)]:
                pts.append((-s * (0.25 + 0.55 * t ** 0.7), s * 1.6 * t))
            pts = pts + [(-px, py) for px, py in reversed(pts)]
            pts = [(x + px * math.cos(rot) - py * math.sin(rot), y + px * math.sin(rot) + py * math.cos(rot))
                   for px, py in pts]
            d.polygon(pts, fill=GOLD, outline=soft.LINE, width=2)
            bx, by = x - s * 1.7 * math.sin(rot), y + s * 1.7 * math.cos(rot)
            d.ellipse((bx - s * 0.25, by - s * 0.25, bx + s * 0.25, by + s * 0.25), fill=GOLD, outline=soft.LINE,
                      width=2)
            d.ellipse((x - s * 0.3, y - s * 0.5, x + s * 0.3, y + s * 0.1), fill="#E5404F", outline=soft.LINE,
                      width=2)
        elif kind == "kane":  # 釣鐘(除夜の鐘)
            w, h = s, s * 1.3
            d.rounded_rectangle((x - w * 0.15, y - h * 0.72, x + w * 0.15, y - h * 0.5), radius=2, fill="#B07A4A",
                                outline=soft.LINE, width=2)
            pts = [(x - w * 0.45, y + h * 0.5), (x - w * 0.45, y - h * 0.15), (x - w * 0.3, y - h * 0.5),
                   (x + w * 0.3, y - h * 0.5), (x + w * 0.45, y - h * 0.15), (x + w * 0.45, y + h * 0.5)]
            d.polygon(pts, fill="#C9955A", outline=soft.LINE, width=2)
            d.line([(x - w * 0.45, y + h * 0.2), (x + w * 0.45, y + h * 0.2)], fill=soft.LINE, width=2)
            d.line([(x - w * 0.52, y + h * 0.5), (x + w * 0.52, y + h * 0.5)], fill=soft.LINE, width=3)
        elif kind == "ring":  # 鐘の音の輪(弧)
            for col, wd in ((soft.LINE, 7), (GOLD, 4)):
                d.arc((x - s, y - s, x + s, y + s), 110, 200, fill=col, width=wd)
        elif kind == "steam":  # 湯気(波線)
            pts = [(x + 4 * math.sin(m[4] + t * 0.5), y - t * 2) for t in range(int(s))]
            d.line(pts, fill=soft.LINE, width=7, joint="curve")
            d.line(pts, fill="white", width=4, joint="curve")
        elif kind == "swish":  # すべった跡の線
            for k in range(2):
                d.arc((x - s, y - s / 2 + k * 7, x + s, y + s / 2 + k * 7), 200, 340, fill=soft.LINE, width=3)
        elif kind == "ume":  # 梅の花
            for k in range(5):
                a = math.radians(k * 72 - 90)
                px, py = x + s * 0.55 * math.cos(a), y + s * 0.55 * math.sin(a)
                d.ellipse((px - s * 0.45, py - s * 0.45, px + s * 0.45, py + s * 0.45), fill="#F49CB4",
                          outline=soft.LINE, width=2)
            for k in range(5):
                a = math.radians(k * 72 - 90)
                px, py = x + s * 0.55 * math.cos(a), y + s * 0.55 * math.sin(a)
                d.ellipse((px - s * 0.45 + 2, py - s * 0.45 + 2, px + s * 0.45 - 2, py + s * 0.45 - 2),
                          fill="#F49CB4")
            d.ellipse((x - s * 0.22, y - s * 0.22, x + s * 0.22, y + s * 0.22), fill="#FFD24D")
        elif kind == "branch":  # 梅の枝(茶色の線)
            pts = [(ox + px, oy + py) for px, py in m[4]]
            d.line(pts, fill=soft.LINE, width=7, joint="curve")
            d.line(pts, fill="#B07A4A", width=4, joint="curve")
        else:
            rest.append(m)
    _draw_marks2(layer, rest, ox, oy)


soft.draw_marks = draw_marks2


# ---- セリフの並べ方と出し方 -------------------------------------------------------

def block(pal, lines, x0=28, y0=24, indent=8):
    """左上から、行を上から順に並べる。lines: (文字, 大きさ, 強調?)。
    戻り値: say() に渡す部品の並び(1コマ分の基本形)。"""
    out, y = [], y0
    for i, (text, size, strong) in enumerate(lines):
        w = len(text) * size * 0.98
        cy = y + size * 0.62
        out.append((text, x0 + i * indent + w / 2, cy, size, -4 if strong else -2, strong))
        y += size * 1.27  # 次の行の白フチが上の行の字にかからない間隔
    return out


def frame_words(pal, base, typ, i, wave_amp=3, shiver=None):
    """型 A/B/C ごとに、i コマ目のセリフを作る(0コマ目は全文の完成形)。"""
    n = len(base)
    show, extras = n, [dict() for _ in base]
    if typ == "A":  # 強調語がポンと出て、残りの行が順に出る
        steps = {1: 0, 2: 0.5, 3: 1, 4: 1, 5: 1.5, 6: 2, 7: 2.5, 8: 3}
        if i in steps:
            st = steps[i]
            show = math.ceil(st) if st else 0
            if st and st != int(st):  # 書いている途中の行
                k = int(st)
                extras[k] = dict(count=max(1, len(base[k][0]) // 2), last=1.3)
            if i == 3:
                extras[0] = dict(scale=1.08)
            if i == 4:
                extras[0] = dict(scale=0.96)
        if i >= 9:
            extras[0] = dict(wave=(wave_amp, i * 1.6))
    elif typ == "B":  # 強調語と残りが交互に跳ねる
        if i == 1:
            show = 0
        elif i == 2:
            show, extras[0] = 1, dict(scale=1.06)
        elif i >= 3:
            for k in range(n):
                extras[k] = dict(scale=1.08 if (k == 0) == (i % 2 == 0) else 1.0)
    else:  # C: 全文を出したまま、強調語だけ跳ねる・震える
        if i:
            extras[0] = dict(shiver=(shiver[0], shiver[1], i)) if shiver else dict(wave=(wave_amp, i * 1.6))
    parts = []
    for k, (text, x, y, size, rot, strong) in enumerate(base[:show]):
        e = extras[k]
        if strong and k and typ == "C" and not shiver:
            e = dict(wave=(wave_amp, i * 1.6 + 1)) if i else {}
        parts.append((text, x, y, size, rot, strong, e))
    return say(pal, *parts)


SMALL = dict(scale=1.0, anchor=(236, 256))
MID = dict(scale=1.12, anchor=(226, 254))


def avoid_boxes(base, m):
    """雪などを避ける四角(セリフの行とキャラ)。"""
    boxes = [(x - len(t) * s * 0.49 - 10, y - s * 0.6 - 8, x + len(t) * s * 0.49 + 10, y + s * 0.6 + 8)
             for t, x, y, s, r, st in base]
    ax, ay = m["anchor"]
    k = m["scale"]
    boxes.append((ax - 78 * k, ay - 160 * k, ax + 78 * k, ay + 6))
    return tuple(boxes)


def make(pal, lines, typ, poses, marks, m=MID, **kw):
    """12コマぶんの台本を作る。poses/marks は i を受け取る関数。"""
    base = block(pal, lines)
    return [kf(poses(i), frame_words(pal, base, typ, i, **kw), marks(i, avoid_boxes(base, m)), **m)
            for i in range(12)]


def snowf(seed, n=8, speed=8):
    def f(i, av):
        return [mk if mk[0] != "snow" else mk for mk in snow(seed, n, i * speed / 8, avoid=av)]
    return f


def sparks(pts):
    """キラキラ(金)。コマごとに大きさを変える。"""
    def f(i, av):
        return [("spark", x, y, s + (3 if (i + j) % 2 else 0)) for j, (x, y, s) in enumerate(pts)]
    return f


def both(*fs):
    return lambda i, av: sum((f(i, av) for f in fs), [])


SWAY = [0, -3, 0, 3, 0, -3, 0, 3, 0, -3, 0, 3]
HOP = [S, J0, S, J0, S, J0, S, J0, S, J0, S, S]

STAMPS.update({
    # 01 メリー/クリスマス(B): サンタ帽でゆらゆら。ぼんぼりが遅れて揺れる。金のベルと雪
    "01": make("end", [("メリー", 56, True), ("クリスマス", 40, False)], "B",
               lambda i: [S, happy, sh(SWAY[i]), santa_hat(-SWAY[i - 1] * 1.5 if i else 0)],
               both(lambda i, av: [("bell", 254, 28, 17, 14 * math.sin(i * 1.05)),
                                   ("bell", 290, 40, 14, -14 * math.sin(i * 1.05))], snowf(1, 7, 6))),
    # 02 今年も/お世話に/なりました(A): 赤いマフラーで深くゆっくりおじぎ。雪がゆっくり降る
    "02": make("end", [("今年も", 54, True), ("お世話に", 34, False), ("なりました", 34, False)], "A",
               lambda i: [[B1], [S, blink], [S, blink], [S, blink], [B1], [B2], [B2], [B2], [B2], [B1], [S, blink],
                          [S, blink]][i] + [scarf("#E5404F", "#FFD6DA", 0.55)],
               snowf(2, 7, 4)),
    # 03 良いお年を/お迎え/ください(A): しましまの毛糸の帽子。右の羽で手を振り、小さく弾む。除夜の鐘の輪
    "03": make("end", [("良いお年を", 44, True), ("お迎え", 34, False), ("ください", 34, False)], "A",
               lambda i: [HOP[i], happy, knit_hat("#E5404F", "#FFFFFF")],
               both(lambda i, av: [("ring", 286, 44, 22 + (i % 3) * 8), ("ring", 286, 44, 14 + ((i + 1) % 3) * 8),
                                    ("kane", 286, 44, 24)],
                    snowf(3, 5, 5))),
    # 04 仕事納め/お疲れさま/でした(C): はんてんで湯のみを持って、ほっと一息。湯気
    "04": make("end", [("仕事納め", 50, True), ("お疲れさま", 34, False), ("でした", 34, False)], "C",
               lambda i: [S, happy, sh([0, 0, 1, 1, 0, -1, -1, 0, 1, 1, 0, 0][i]), hanten, hold(12), cup],
               lambda i, av: [("steam", 218 + j * 16, 208, 7 + (i + j) % 3 * 2, i * 0.9 + j) for j in range(2)]),
    # 06 本年も/よろしく/お願い/いたします(A): 両羽をそろえて最敬礼。後ろに紅白の扇
    "06": make("new", [("本年も", 48, True), ("よろしく", 32, False), ("お願い", 30, False), ("いたします", 28, False)],
               "A",
               lambda i: [[B2], [S, blink], [S, blink], [S, blink], [B1], [B2], [B2], [B2], [B2], [B2], [B1],
                          [S, blink]][i] + [mizuhiki, fan],
               sparks([(290, 120, 10), (292, 210, 8)]), m=SMALL),
    # 07 謹賀新年(C): ひつじのもこもこフードで、ぽよんと弾む。金の紙ふぶき
    "07": make("new", [("謹賀新年", 58, True)], "C",
               lambda i: [HOP[i], happy, sh(SWAY[i]), sheep_hood],
               lambda i, av: confetti(7, 8, i, box=(24, 92, 120, 250)) + confetti(8, 4, i, box=(260, 30, 300, 90)),
               wave_amp=5),
    # 08 旧年中は/お世話に/なりました(B): だるまを抱えて一緒にゆらゆら。金のキラキラ
    "08": make("new", [("旧年中は", 50, True), ("お世話に", 34, False), ("なりました", 34, False)], "B",
               lambda i: [S, happy, sh(SWAY[i]), hold(10), daruma(SWAY[i] * 4)],
               sparks([(288, 110, 10), (44, 222, 9)])),
    # 09 ご多幸を/お祈り/いたします(A): 右の羽をそっと差し出すと、折り鶴がふわっと浮かぶ
    "09": make("new", [("ご多幸を", 50, True), ("お祈り", 34, False), ("いたします", 34, False)], "A",
               lambda i: [S, happy, raise_r(10), crane([0, 0, 2, 4, 6, 8, 6, 4, 2, 4, 6, 4][i])],
               sparks([(288, 118, 9), (292, 200, 7), (44, 230, 8)])),
    # 10 今年の運勢/大吉/でした!(B): おみくじを見て目がきらっ。ぴょんぴょん。紙ふぶき
    "10": make("new", [("今年の運勢", 42, True), ("大吉", 50, True), ("でした!", 34, False)], "B",
               lambda i: [HOP[i], hold(10), omikuji],
               lambda i, av: confetti(10, 6, i, box=(250, 30, 300, 110)) + [("spark", 290, 150, 10 + i % 2 * 3)]),
    # 11 寒中/お見舞い/申し上げます(A): 白い毛糸の帽子で小さくおじぎ。梅の花と雪の結晶
    "11": make("win", [("寒中", 56, True), ("お見舞い", 34, False), ("申し上げます", 26, False)], "A",
               lambda i: [[B1], [S, blink], [S, blink], [S, blink], [S, blink], [B1], [B1], [B1], [S, blink],
                          [B1], [S, blink], [S, blink]][i] + [knit_hat("#FFFFFF", "#8FB8EE")],
               both(lambda i, av: [("branch", 0, 0, 0, [(306, 40), (284, 50), (262, 70)]),
                                   ("ume", 284, 48, 12), ("ume", 262, 72, 10)], snowf(11, 6, 6)),
               m=SMALL),
    # 13 どうぞ/ご自愛/ください(A): ストールを巻いて、湯たんぽを両羽で持つ。ハートの湯気
    "13": make("win", [("どうぞ", 54, True), ("ご自愛", 38, False), ("ください", 34, False)], "A",
               lambda i: [S, happy, scarf("#FFF1D6", "#F49CB4"), hold(12), yutanpo],
               lambda i, av: [("heart", 300 - (i % 3) * 4, 150 - (i % 4) * 8, 8 + i % 3 * 2),
                              ("heart", 44, 228 - (i % 4) * 6, 7 + (i + 1) % 3)]),
    # 14 足元に/お気を/つけください(B): 長ぐつで雪道をつるっ。羽でバランス。足元に雪
    "14": make("win", [("足元に", 52, True), ("お気を", 34, False), ("つけください", 28, False)], "B",
               lambda i: [S, sh([0, 4, -4, 4, -4, 3, -3, 2, -2, 1, 0, 0][i]), boots, snowbank,
                          knit_hat("#4F6FB8", "#FFFFFF")],
               lambda i, av: [("sweat", 296, 120, 10)] + ([("swish", 236, 256, 26)] if i in (1, 2, 3, 4) else []) +
               snow(14, 4, i, avoid=av), m=SMALL),
    # 15 あたたかく/お過ごし/ください(A): こたつでほっこり、左右にゆれる。みかんと湯気
    "15": make("win", [("あたたかく", 44, True), ("お過ごし", 34, False), ("ください", 34, False)], "A",
               lambda i: [S, happy, sh([0, 0, 2, 2, 0, -2, -2, 0, 2, 2, 0, 0][i]), kotatsu],
               lambda i, av: [("steam", 120 + j * 10, 186, 12 + (i + j) % 3 * 3, i * 0.9 + j) for j in range(2)],
               m=dict(scale=1.12, anchor=(214, 254))),
    # 16 あたたかい/お言葉/ありがとう/ございます(C): 耳あてで、羽を胸に重ねてぺこり。ハートが上がる
    "16": make("win", [("あたたかい", 38, True), ("お言葉", 38, True), ("ありがとう", 29, False),
                       ("ございます", 29, False)], "C",
               lambda i: [[S, happy], [S, happy], [S, happy], [B1, happy], [B1, happy], [S, happy], [S, happy],
                          [S, happy], [B1, happy], [B1, happy], [S, happy], [S, happy]][i] + [hold(14), earmuffs],
               lambda i, av: [("heart", 294, 150 - i * 6 % 48, 9), ("heart", 300, 210 - (i * 6 + 24) % 48, 7)],
               m=SMALL, wave_amp=3),
})

ARMS.update({  # (左腕, 右腕) 肩を支点に。持つ・寄せる角度との合計で 16° 以内
    "01": ([0, 10, 4, -4, 4, 12, 4, -4, 4, 10, 4, 0], [0, -4, 4, 12, 4, -4, 4, 12, 4, -4, 4, 0]),
    "02": ([0, 2, 4, 2, 4, 2, 4, 2, 4, 2, 4, 2], [0, 4, 2, 4, 2, 4, 2, 4, 2, 4, 2, 4]),  # おじぎの羽は体の前のまま、小さく
    "03": ([0, 2, 4, 2, 4, 2, 4, 2, 4, 2, 4, 2], [0, 10, 16, 10, 16, 10, 16, 10, 16, 10, 16, 8]),
    "04": ([0, 1, 2, 1, 0, -1, 0, 1, 2, 1, 0, 1], [0, -1, 0, 1, 2, 1, 0, -1, 0, 1, 2, 0]),
    "06": ([0, 2, 0, 2, 0, -2, 0, -2, 0, -2, 0, 2], [0, 0, 2, 0, 2, 0, -2, 0, -2, 0, -2, 0]),
    "07": ([0, 8, 14, 8, 14, 8, 14, 8, 14, 8, 14, 6], [0, 14, 8, 14, 8, 14, 8, 14, 8, 14, 8, 10]),
    "08": ([0, 2, 0, -2, 0, 2, 0, -2, 0, 2, 0, 0], [0, -2, 0, 2, 0, -2, 0, 2, 0, -2, 0, 0]),
    "09": ([0, 4, 8, 6, 8, 4, 8, 6, 8, 4, 8, 4], [0, 0, 2, 4, 6, 4, 2, 4, 6, 4, 2, 0]),
    "10": ([0, 2, -2, 2, -2, 4, -2, 2, -2, 4, -2, 0], [0, -2, 2, -2, 4, -2, 2, -2, 4, -2, 2, 0]),
    "11": ([0, 2, 4, 2, 0, -6, -8, -6, 0, -6, 2, 0], [0, 4, 2, 0, 2, -8, -6, -8, 2, -8, 0, 2]),
    "13": ([0, 1, 3, 1, -1, 1, 3, 1, -1, 1, 3, 0], [0, 3, 1, -1, 1, 3, 1, -1, 1, 3, 1, 0]),
    "14": ([0, 16, 4, 14, 2, 12, 4, 10, 2, 6, 2, 0], [0, 4, 16, 2, 14, 4, 12, 2, 10, 2, 6, 0]),
    "15": ([0, 2, 4, 2, 0, -2, 0, 2, 4, 2, 0, 0], [0, 0, -2, 0, 2, 4, 2, 0, -2, 0, 2, 0]),
    "16": ([0, 1, 2, 1, 0, -1, 0, 1, 2, 1, 0, 0], [0, 0, 1, 2, 1, 0, -1, 0, 1, 2, 1, 0]),
})


# 口パク(2,4,6,8,10)・足ぶみ・腕・頭の毛は set01 と同じ決まりで足す
for name, frames in STAMPS.items():
    left, right = ARMS[name]
    for i, fr in enumerate(frames):
        extra = []
        if i in soft.TALK_FRAMES:
            extra.append(talk)
        if i in soft.STEP_FRAMES:
            extra.append(step(soft.STEP_FRAMES[i]))
        if i:
            extra += [flap("P6", left[i]), flap("P7", right[i]), tuft(TUFT[i])]
        fr["poses"] = fr["poses"] + extra


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", choices=sorted(STAMPS))
    ap.add_argument("--chara-png")
    ap.add_argument("--text-png")
    ap.add_argument("--png")
    ap.add_argument("--ops")
    ap.add_argument("--page", default="PAGE_ID")
    a = ap.parse_args()
    frames = STAMPS[a.stamp]
    if a.ops:
        ops = soft.to_ops_merged(frames, a.page)
        Path(a.ops).write_text(json.dumps(ops, ensure_ascii=False, separators=(",", ":")))
        print(f"Canva操作: {a.ops}({len(ops)}個, {Path(a.ops).stat().st_size // 1024}KB)")
    with tempfile.TemporaryDirectory() as tmp:
        cp = a.chara_png or f"{tmp}/c.png"
        tp = a.text_png or f"{tmp}/t.png"
        soft.chara_png(frames, cp)
        soft.text_png(frames, tp)
        if a.png:
            sheet = Image.new("RGBA", (soft.CW * soft.COLS, soft.CH * soft.ROWS), inko.BG)
            sheet.alpha_composite(Image.open(cp).convert("RGBA"))
            sheet.alpha_composite(Image.open(tp).convert("RGBA"))
            sheet.convert("RGB").save(a.png)
            print(f"シート: {a.png}")


if __name__ == "__main__":
    main()
