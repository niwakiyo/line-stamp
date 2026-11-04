#!/usr/bin/env python3
"""ていねいインコ set04「クリスマス」: サンタとトナカイのキャラ。

  確認用シート : python3 tools/xmas.py 01 --png sheet.png

決まりごと(docs/stamp_rules.md)を全部守る。とくに:
- インコの形(卵形の体・羽・頭の毛・くちばし)を残さない。サンタは人、トナカイは鹿の形で描く
- 顔まわり(顔・耳・角・ひげ・帽子)は全部「顔のずれ」で動かす(ずれない)
- 左右で対になる部品(角・耳・腕・足)は鏡うつし
- 耳は2色で付け根を顔の後ろに隠して動かす。鼻とほっぺは色を分ける。輪郭は太め
- 腕は肩を支点に最大16°、左右別々。足は小さく動かす
- セリフは newyear の「カーブ・段差・大きさ違い・書体まぜ」(winter.say / winter.block の差し替え)を使う
"""
import argparse
import math
import re
import tempfile
from pathlib import Path

from PIL import Image

import inko
import soft
import winter
import newyear
from soft import kf, S, J0, J1, J2, B1, B2, happy, blink, flap
from winter import add, face_off, confetti, make, MID, SMALL, DOT, STRIPE, sh, SWAY, HOP
from newyear import legs, _circles, EAR01, LEGS, LEG, HOOF_P, NOSE, MOUTH, MOUTH_OPEN

soft.scallop = newyear._scallop  # ひつじ用の大きな毛の波をやめ、ふつうのやわらかい輪郭に戻す
winter.PAL["xmas"] = ("#D93A3A", soft.BROWN, "#E8B33A")

RED, RED_D, WHITE, GOLD = "#D93A3A", "#B32B2E", "#FFFFFF", "#E8B33A"
SKIN, SKIN_D = "#F8DCC4", "#E8A486"
DEER, DEER_L, DEER_D, ANTLER = "#B98A62", "#F3E3CC", "#8A5E40", "#7A5236"
EAR_IN = "#F7C9C3"

_soften = soft.soften


def soften_keep(c):
    """soften はインコの羽・体の形に描き替えるので、keep を付けた部品は自分の形に戻す。"""
    c = _soften(c)  # newyear の soften(輪郭を太くする)のあとで、形だけ戻す
    for e in c.values():
        if e.get("keep"):
            e["d"] = e["keep"]
    return c


soft.soften = soften_keep


def put(c, key, fill, sw, w, h, left, top, d, rot=0, vw=None, vh=None, stroke=inko.INK):
    add(c, key, fill, stroke if sw else None, sw, w, h, left, top, d, rot=rot)
    c[key].update(vw=vw or w, vh=vh or h, keep=d)


def small_eyes(c, k=0.82):
    """目はインコより少し小さく、少し内側へ(soften が 1.4 倍にするので先に小さくしておく)。"""
    for key in ("P8", "P9", "P10", "P11"):
        if key in c:
            e = c[key]
            cx, cy = e["left"] + e["w"] / 2, e["top"] + e["h"] / 2
            e.setdefault("vw", e["w"])
            e.setdefault("vh", e["h"])
            kk = k if key in ("P8", "P9") else k * 0.8
            e["w"], e["h"] = e["w"] * kk, e["h"] * kk
            e["left"], e["top"] = cx - e["w"] / 2 + (3 if key in ("P8", "P10") else -3), cy - e["h"] / 2


def mirror(d, width):
    return re.sub(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)",
                  lambda m: f"{width - float(m.group(1)):g} {m.group(2)}", d)


# ---- トナカイ ---------------------------------------------------------------------
# 角(左): 4倍の座標(160x160)。付け根は下、枝分かれして上へ。右は鏡うつし
ANTLER_L = ("M112 152 C104 120 96 96 84 76 C76 62 60 54 40 44 C30 40 24 32 28 24 C34 18 42 24 48 30 "
            "C58 38 68 44 74 46 C72 34 66 22 58 12 C54 6 60 0 66 4 C76 12 82 28 86 44 "
            "C92 56 96 62 100 64 C102 52 104 40 108 30 C110 22 120 22 120 30 C118 46 112 62 112 78 "
            "C114 100 124 124 132 150 Z")
ANTLER_R = mirror(ANTLER_L, 160)
EAR_DEER_L = "M2 9 C6 2 20 0 30 6 C29 12 18 16 9 15 C5 14 2 12 2 9 Z"
EAR_DEER_R = mirror(EAR_DEER_L, 32)
EAR_DEER_IN_L = "M6 9 C10 5 19 4 26 7 C24 10 17 12 11 12 C8 12 6 11 6 9 Z"
EAR_DEER_IN_R = mirror(EAR_DEER_IN_L, 32)


def deer_ear(c, key, bx, by, side, rot):
    """耳: 外側(茶)と内側(桃)の2色。付け根 (bx,by) を支点に rot 度。顔の後ろに置いて付け根を隠す。"""
    for suf, fill, d, sw, k in (("a", DEER_D, EAR_DEER_L if side < 0 else EAR_DEER_R, 2, 1.0),
                                ("b", EAR_IN, EAR_DEER_IN_L if side < 0 else EAR_DEER_IN_R, 0, 1.0)):
        w, h = 34 * k, 17 * k
        ra = math.radians(rot)
        off = side * (w / 2 - 3)
        cx, cy = bx + off * math.cos(ra), by + off * math.sin(ra)
        put(c, "FACE0_ear" + ("L" if side < 0 else "R") + suf, fill, sw, w, h, cx - w / 2, cy - h / 2, d, rot=rot,
            vw=32, vh=17)


def ears(dl, dr):
    def f(c):
        c["_earL"], c["_earR"] = dl, dr
    return f


def reindeer(c, glow=False):
    """トナカイ: 茶色の体と顔、白っぽい口元、大きな赤い鼻、2色の耳、左右対称の角、短い4本の足(こげ茶)。"""
    fx, fy = face_off(c)
    for k in ("P0", "P4"):
        e = c[k]
        w = min(e["h"] * 1.12, 120)
        cx = e["left"] + e["w"] / 2
        e.update(w=w, left=cx - w / 2, vw=w, vh=e["h"])
    c["P4"]["fill"] = DEER
    p5 = c["P5"]
    p5.update(fill="#EAD3B6", w=p5["w"] * 0.78, h=p5["h"] * 0.6, left=p5["left"] + p5["w"] * 0.1,
              top=p5["top"] + 16)
    c.pop("P1", None)
    bottom = c["P4"]["top"] + c["P4"]["h"]
    for k, x in (("P6", 160 - 17), ("P7", 160 + 17)):  # 前足
        c[k].update(d=LEG, fill=DEER_D, w=14, h=18, vw=14, vh=16, left=x - 7, top=bottom - 18, rot=0, keep=LEG)
    for k, x in (("P2", 160 - 38), ("P3", 160 + 38)):  # 後ろ足
        c[k].update(d=LEG, fill=DEER_D, w=14, h=18, vw=14, vh=16, left=x - 7, top=bottom - 18, keep=LEG)
    put(c, "FACE1", DEER, 3.4, 78, 68, 121 + fx, 142 + fy, soft.ellipse_d(78, 68))
    put(c, "FACE2_muzzle", DEER_L, 2, 46, 26, 137 + fx, 182 + fy, soft.ellipse_d(46, 26))
    deer_ear(c, "", 128 + fx, 164 + fy, -1, -18 + c.get("_earL", 0))
    deer_ear(c, "", 192 + fx, 164 + fy, 1, 18 + c.get("_earR", 0))
    # 角: 頭のてっぺんの左右から、鏡うつしで同じ形・同じ角度
    put(c, "BG5_antlerL", ANTLER, 2, 44, 44, 112 + fx, 104 + fy, ANTLER_L, vw=160, vh=160)
    put(c, "BG5_antlerR", ANTLER, 2, 44, 44, 164 + fx, 104 + fy, ANTLER_R, vw=160, vh=160)
    small_eyes(c)
    c["P12"]["left"] += 8
    c["P13"]["left"] -= 8
    # 鼻: 大きな赤い丸(ほっぺの桃色と分ける)。光るコマは明るい赤
    nx, ny = 160 + fx, 186 + fy
    c["P14"].update(d=soft.ellipse_d(18, 15), fill="#FF5E54" if glow else "#E2463F", w=18, h=15, vw=18, vh=15,
                    left=nx - 9, top=ny - 9, sw=2, stroke=inko.INK, keep=soft.ellipse_d(18, 15))
    c["P15"].update(d=MOUTH, fill=soft.LINE, sw=0, stroke=None, top=c["P15"]["top"] + 12)
    c.pop("_earL", None)
    c.pop("_earR", None)


# 背景より後ろの重なり順(角は顔の後ろ、体よりも後ろ)
_order = winter.inko_order


def xmas_order(key):
    if key.startswith("BG5"):
        return -0.5
    return _order(key)


winter.inko_order = xmas_order
soft.inko_order = xmas_order


# ---- サンタ -----------------------------------------------------------------------
HAT = "M4 46 C8 24 24 6 46 6 C64 6 78 16 86 30 C88 34 84 38 80 36 C74 30 68 30 66 34 C70 40 74 44 84 46 Z"
ARM = "M8 1 C13 1 15 4 15 8 L15 30 C15 34 12 36 8 36 C4 36 1 34 1 30 L1 8 C1 4 3 1 8 1 Z"  # 16x37 の袖
BEARD = _circles(176, 88, 120, 56, 10, 40)        # 4倍の座標(352x200 → 88x50)
BEARD_IN = _circles(176, 88, 120, 56, 10, 40, shrink=9)


def santa(c):
    """サンタ: はだ色の顔、白いひげ(丸を並べた雲)、赤い帽子(白いふち・ぼんぼり)、赤い服、
    黒いベルトと金のバックル、赤い袖の腕(肩が支点)、白い手、黒い長ぐつ。"""
    fx, fy = face_off(c)
    for k in ("P0", "P4"):  # 体: 横に広い丸(インコの卵形にしない)
        e = c[k]
        w = min(e["h"] * 1.18, 124)
        cx = e["left"] + e["w"] / 2
        e.update(w=w, left=cx - w / 2, vw=w, vh=e["h"])
        e["d"] = soft.ellipse_d(w, e["h"])
        e["keep"] = e["d"]
    c["P4"]["fill"] = RED
    c.pop("P1", None)
    c.pop("P5")
    bottom = c["P4"]["top"] + c["P4"]["h"]
    put(c, "MID1_belt", "#3A2E2E", 2, 96, 12, 112, bottom - 34, "M2 2 L94 2 L94 10 L2 10 Z")
    put(c, "MID2_buckle", GOLD, 2, 18, 14, 151, bottom - 35, "M2 2 L16 2 L16 12 L2 12 Z")
    # 腕(袖): 体の左右の肩から下へ。flap で肩を支点に動く
    by = c["P4"]["top"] + c["P4"]["h"] * 0.22
    for k, x in (("P6", c["P4"]["left"] + 2), ("P7", c["P4"]["left"] + c["P4"]["w"] - 18)):
        c[k].update(d=ARM, fill=RED_D, w=16, h=37, vw=16, vh=37, left=x, top=by, rot=0, keep=ARM)
    for k in ("P2", "P3"):  # 長ぐつ
        c[k].update(d=HOOF_P, fill="#3A2E2E", w=22, h=13, vw=20, vh=12, keep=HOOF_P)
    put(c, "FACE1", SKIN, 3.4, 80, 64, 120 + fx, 144 + fy, soft.ellipse_d(80, 64))
    # ひげ: あごの下の白い雲(目・ほっぺ・鼻にかけない)。口はひげの上に見える
    put(c, "FACE2_beard", WHITE, 2, 84, 42, 118 + fx, 190 + fy, BEARD, vw=352, vh=200)
    put(c, "FACE3_beardin", WHITE, 0, 84, 42, 118 + fx, 190 + fy, BEARD_IN, vw=352, vh=200)
    # 帽子: 前髪の位置にかぶる。白いふちとぼんぼり(左右に少し傾いた形)
    put(c, "ACC1_hat", RED, 2, 88, 48, 118 + fx, 104 + fy, HAT)
    band = "M10 4 L170 4 C178 4 182 10 182 18 C182 26 178 32 170 32 L10 32 C2 32 -2 26 -2 18 C-2 10 2 4 10 4 Z"
    put(c, "ACC2_hatband", WHITE, 2, 90, 18, 115 + fx, 140 + fy, band, vw=180, vh=36)
    put(c, "ACC3_pom", WHITE, 2, 18, 18, 196 + fx, 130 + fy, soft.ellipse_d(18, 18))
    small_eyes(c, 0.86)
    c["P12"]["left"] += 8
    c["P13"]["left"] -= 8
    c["P14"].update(d=soft.ellipse_d(16, 12), fill=SKIN_D, w=16, h=12, vw=16, vh=12,
                    left=152 + fx, top=172 + fy, sw=2, stroke=inko.INK, keep=soft.ellipse_d(16, 12))
    c["P15"].update(d=MOUTH, fill=soft.LINE, sw=0, stroke=None, top=c["P15"]["top"] + 4)


def hands(c):
    """袖の先に白い手(手ぶくろ)を付ける。腕の回転のあとで、袖の先の位置に置く(腕について行く)。"""
    for k in ("P6", "P7"):
        e = c[k]
        r = math.radians(e.get("rot", 0))
        cx, cy = e["left"] + e["w"] / 2, e["top"] + e["h"] / 2
        tx, ty = cx - (e["h"] / 2 - 3) * math.sin(r), cy + (e["h"] / 2 - 3) * math.cos(r)
        put(c, "P7z_hand" + k, WHITE, 2, 16, 15, tx - 8, ty - 7.5, soft.ellipse_d(16, 15))


def talk(c):
    c["P15"].update(d=MOUTH_OPEN, fill=soft.BEAK_OPEN_FILL, sw=1.5, stroke=inko.INK)


# ---- 台本 -------------------------------------------------------------------------

def snowf(seed, n=6):
    return lambda i, av: winter.snow(seed, n, i, avoid=av)


def bells(i, av):
    return [("bell", 262, 30, 14, 14 * math.sin(i * 1.05)), ("bell", 292, 44, 12, -14 * math.sin(i * 1.05))]


def both(*fs):
    return lambda i, av: sum((f(i, av) for f in fs), [])


JUMP_BOW = [[S, happy], [J0, happy], [J1, happy], [J1, happy, J2], [J1, happy], [J0, happy],
            [S, happy], [B1, happy], [B2, happy], [B1, happy], [S, happy], [S, happy]]

STAMPS = {
    # 01 メリー/クリスマス(B): サンタが跳ねて、ぺこり。金のベルと雪
    "01": make("xmas", [("メリー", 46, True), ("クリスマス", 34, True)], "B",
               lambda i: list(JUMP_BOW[i]) + [santa], both(bells, snowf(1)), m=dict(scale=0.92, anchor=(244, 254)), x0=18),
    # 05 おつかれさま/です(A): トナカイの鼻がぴかっと光る。左右にゆれる
    "05": make("xmas", [("おつかれさま", 38, True), ("です", 36, False)], "A",
               lambda i: [S, happy, sh(SWAY[i]), ears(EAR01[0][i], EAR01[1][i]),
                          (lambda c: reindeer(c, glow=(i % 2 == 1)))],
               lambda i, av: ([("spark", 204, 178, 7 + (i % 2) * 4), ("spark", 118, 178, 6 + (i % 2) * 3)]
                              if i % 2 else []) + winter.snow(5, 5, i, avoid=av), m=dict(scale=1.05, anchor=(230, 258))),
}

ARMS = {  # サンタの腕: (左, 右) 肩を支点に最大16°、左右で別々
    "01": ([0, -8, 14, 16, 12, -4, 6, 4, 2, 4, 8, 4], [0, -6, 12, 16, 14, -6, 10, 2, 4, 2, 6, 8]),
}

for name, frames in STAMPS.items():
    for i, fr in enumerate(frames):
        extra = []
        if i in soft.TALK_FRAMES:
            extra.append(talk)
        if name in ARMS:  # サンタ: 腕を振って手を付ける、長ぐつは交互に少し上げる
            if i:
                extra += [flap("P6", ARMS[name][0][i]), flap("P7", ARMS[name][1][i])]
                if i in soft.STEP_FRAMES:
                    extra.append(soft.step(soft.STEP_FRAMES[i]))
            extra.append(hands)
        else:  # トナカイ: 4本の足
            if i:
                extra.append(legs(*(LEGS["01"][k][i] for k in range(5))))
        fr["poses"] = fr["poses"] + extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stamp", choices=sorted(STAMPS))
    ap.add_argument("--png", required=True)
    a = ap.parse_args()
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
