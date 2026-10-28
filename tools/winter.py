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
from soft import kf, word, S, J0, J1, J2, B1, B2, happy, talk, step, flap, tuft, TUFT

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


def scarf(color, stripe):
    """首(くちばしの下)に巻くマフラー。体と羽の間に入れる。"""
    def f(c):
        ox, oy = face_off(c)
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


def snow(seed, n=8, fall=0, box=(24, 24, 296, 250), avoid=()):
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
