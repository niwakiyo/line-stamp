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


GREEN, GREEN_D = "#2F7D5A", "#245F45"   # 深い緑(背景の緑と区別できる。G-max(R,B)<40)


def say_xmas(pal, *parts):
    """クリスマスのセリフ: 強調語は赤と緑を1字ずつ交互(金のフチ)、ほかの語は緑。カーブ・段差・大きさ違い。"""
    ws = newyear.say_curved("xmas", *parts)
    for w, (text, x, y, size, rot, strong, extra) in zip(ws, parts):
        w["colors"] = [RED, GREEN] if strong else [GREEN_D]
    return ws


def arm_part(c, key, sx, sy, ang, length, width, fill, cap_fill, cap_w, front=True, lift=0, cuff=None):
    """腕・前足: 付け根 (sx, sy) を支点に ang 度(0 で真下、正で外へ開く…は呼ぶ側で向きを決める)。
    少し先が太くなる、ゆるく曲がった形。先に手(ひづめ・手ぶくろ)を付ける。cuff があれば手首に白い毛。"""
    d = f"M{width * 0.3:.1f} 1 C{width * 0.75:.1f} 1 {width * 0.95:.1f} 6 {width * 0.92:.1f} {length * 0.5:.1f} " \
        f"C{width * 0.9:.1f} {length * 0.8:.1f} {width:.1f} {length - 2:.1f} {width * 0.6:.1f} {length:.1f} " \
        f"L{width * 0.25:.1f} {length:.1f} C{width * 0.02:.1f} {length - 2:.1f} 0 {length * 0.7:.1f} {width * 0.08:.1f} {length * 0.45:.1f} " \
        f"C{width * 0.12:.1f} 6 0 1 {width * 0.3:.1f} 1 Z"
    r = math.radians(ang)
    cx, cy = sx - (length / 2) * math.sin(r), sy + (length / 2) * math.cos(r) - lift
    c.pop(key, None)  # インコの羽の部品は捨てて、腕・前足の形で置き直す
    put(c, key, fill, 2.4, width, length, cx - width / 2, cy - length / 2, d, rot=ang)
    tx, ty = sx - (length - 3) * math.sin(r), sy + (length - 3) * math.cos(r) - lift
    if cuff:
        wx, wy = sx - (length - 10) * math.sin(r), sy + (length - 10) * math.cos(r) - lift
        put(c, key + "_cuff", cuff, 2, width + 4, 10, wx - (width + 4) / 2, wy - 5, soft.ellipse_d(width + 4, 10), rot=ang)
    put(c, key + "_hand", cap_fill, 2.4, cap_w, cap_w * 0.9, tx - cap_w / 2, ty - cap_w * 0.45,
        soft.ellipse_d(cap_w, cap_w * 0.9), rot=ang)


# ---- トナカイ ---------------------------------------------------------------------
DEER, DEER_FACE, DEER_D, DEER_FRONT, HOOF = "#AF7C52", "#C99C70", "#7E5638", "#D2AC82", "#4A3328"
MUZZLE, ANTLER, ANTLER_L2 = "#F4E6D2", "#8A5E40", "#B58758"
EAR_IN = "#F7C9C3"
# 角(左): 4倍の座標(200x200)。根元(下・太い)は頭のてっぺんに重ねる。大きく枝分かれ。右は鏡うつし
ANTLER_LP = ("M150 196 C146 168 138 140 124 118 C108 94 84 80 56 70 C40 64 28 52 30 38 C34 26 48 28 52 40 "
             "C56 52 70 60 86 66 C82 50 74 34 62 20 C56 12 62 0 74 6 C90 18 98 40 102 62 "
             "C106 74 112 82 118 86 C118 66 120 46 128 30 C132 20 146 20 146 32 C142 56 136 78 140 100 "
             "C146 128 158 160 170 196 Z")
ANTLER_RP = mirror(ANTLER_LP, 200)
EAR_DEER_L = "M2 10 C7 2 22 0 34 7 C33 14 21 18 10 17 C5 16 2 14 2 10 Z"
EAR_DEER_R = mirror(EAR_DEER_L, 36)
EAR_DEER_IN_L = "M7 10 C11 5 21 4 29 8 C27 12 19 14 12 14 C9 14 7 12 7 10 Z"
EAR_DEER_IN_R = mirror(EAR_DEER_IN_L, 36)
CHEST = _circles(120, 70, 70, 30, 8, 30)
CHEST_IN = _circles(120, 70, 70, 30, 8, 30, shrink=8)


def deer_ear(c, bx, by, side, rot):
    """耳: 外側(こげ茶)と内側(桃)の2色。付け根 (bx,by) を支点に rot 度。顔の後ろに置いて付け根を隠す。"""
    for suf, fill, d, sw in (("a", DEER_D, EAR_DEER_L if side < 0 else EAR_DEER_R, 2),
                             ("b", EAR_IN, EAR_DEER_IN_L if side < 0 else EAR_DEER_IN_R, 0)):
        w, h = 38, 19
        ra = math.radians(rot)
        off = side * (w / 2 - 3)
        cx, cy = bx + off * math.cos(ra), by + off * math.sin(ra)
        put(c, "FACE0b_ear" + ("L" if side < 0 else "R") + suf, fill, sw, w, h, cx - w / 2, cy - h / 2, d, rot=rot,
            vw=36, vh=19)


def P(**kw):
    """このコマの動き(腕・足・耳・帽子など)を、キャラを描く関数に渡す。"""
    def f(c):
        c["_p"] = kw
    return f


def reindeer(c):
    """トナカイ: 体(茶)と顔(明るい茶)を色で分け、白い口元、光る赤い鼻、2色の耳、大きな角、
    あごの下のふわふわの毛、赤い首輪と金の鈴。前足は明るい茶+こげ茶のひづめで体の前、後ろ足は濃い茶で体の後ろ。"""
    p = c.pop("_p", {})
    fx, fy = face_off(c)
    b = c["P4"]
    for k in ("P0", "P4"):
        e = c[k]
        w = min(e["h"] * 1.1, 118)
        cx = e["left"] + e["w"] / 2
        e.update(w=w, left=cx - w / 2, vw=w, vh=e["h"])
    b["fill"] = DEER
    c.pop("P1", None)
    c.pop("P5", None)
    bx, by, bw, bh = b["left"], b["top"], b["w"], b["h"]
    bcx = bx + bw / 2
    # 後ろ足(体の後ろ、濃い茶)
    for k, x, up in (("P2", bcx - 36, p.get("hl", 0)), ("P3", bcx + 36, p.get("hr", 0))):
        c[k].update(d=LEG, fill=DEER_D, w=18, h=20, vw=14, vh=16, left=x - 9, top=by + bh - 18 - up, keep=LEG)
    # あごの下のふわふわ(おなかの袋にしない)・首輪と鈴
    # 首輪と鈴: あごのすぐ下(顔について行く)。鈴は左右にゆれる
    put(c, "NECK1_collar", RED, 2.4, 70, 14, 125 + fx, 204 + fy, "M2 2 C24 12 46 12 68 2 L68 10 C46 20 24 20 2 10 Z",
        vw=70, vh=20)
    sw_ = p.get("bell", 0)
    put(c, "NECK2_bell", GOLD, 2.4, 18, 18, 151 + fx + sw_, 212 + fy, soft.ellipse_d(18, 18))
    put(c, "NECK3_bellline", HOOF, 0, 10, 3, 155 + fx + sw_, 222 + fy, soft.ellipse_d(10, 3))
    # 前足(体の前、明るい茶+ひづめ)。付け根を支点に大きく動かす
    fl, fr_ = p.get("fl", 0), p.get("fr", 0)
    arm_part(c, "P6", bcx - 28, by + bh - 38, fl, 34, 20, DEER_FRONT, HOOF, 20, lift=p.get("lfl", 0))
    arm_part(c, "P7", bcx + 28, by + bh - 38, -fr_, 34, 20, DEER_FRONT, HOOF, 20, lift=p.get("lfr", 0))
    # 角: 頭のてっぺんから(根元は顔に重ねて隠す)。顔より後ろ、体より前
    put(c, "ANTL1", ANTLER, 2.4, 64, 64, 96 + fx, 82 + fy, ANTLER_LP, vw=200, vh=200)
    put(c, "ANTL2", ANTLER, 2.4, 64, 64, 160 + fx, 82 + fy, ANTLER_RP, vw=200, vh=200)
    # 根元のこぶ(頭のてっぺんにのせる)
    put(c, "ANTL3", ANTLER_L2, 2, 16, 10, 136 + fx, 141 + fy, soft.ellipse_d(16, 10))
    put(c, "ANTL4", ANTLER_L2, 2, 16, 10, 168 + fx, 141 + fy, soft.ellipse_d(16, 10))
    deer_ear(c, 130 + fx, 160 + fy, -1, -20 + p.get("el", 0))
    deer_ear(c, 190 + fx, 160 + fy, 1, 20 + p.get("er", 0))
    put(c, "FACE1", DEER_FACE, 3.4, 80, 70, 120 + fx, 140 + fy, soft.ellipse_d(80, 70))
    put(c, "FACE2_muzzle", MUZZLE, 2, 46, 28, 137 + fx, 182 + fy, soft.ellipse_d(46, 28))
    small_eyes(c)
    c["P12"]["left"] += 8
    c["P13"]["left"] -= 8
    glow = False  # 鼻は点滅させない(目のまわりがちかちかしないように)
    nx, ny = 160 + fx, 188 + fy
    c["P14"].update(d=soft.ellipse_d(20, 16), fill="#FF6157" if glow else "#E2463F", w=20, h=16, vw=20, vh=16,
                    left=nx - 10, top=ny - 9, sw=2, stroke=inko.INK, keep=soft.ellipse_d(20, 16))
    put(c, "P14z_shine", WHITE, 0, 6, 4, nx - 6, ny - 6, soft.ellipse_d(6, 4))
    c["P15"].update(d=MOUTH, fill=soft.LINE, sw=0, stroke=None, top=ny + 6)


_order = winter.inko_order


def xmas_order(key):
    if key.startswith("FACE0a"):  # 角: 体より前、顔より後ろ
        return winter.ORDER.index("P5") - 0.7
    if key.startswith("FACE0b"):  # 耳
        return winter.ORDER.index("P5") - 0.6
    if key.startswith("ANTL"):  # 角: 顔より前(根元が頭のてっぺんにのって見える)、目より後ろ
        return winter.ORDER.index("P5") - 0.3
    if key.startswith("NECK"):  # トナカイの首輪と鈴: 体より前、角・顔より後ろ…ではなく、あごの下に見せるので顔より前
        return winter.ORDER.index("P5") - 0.4
    if key.startswith("BEARD"):  # サンタのひげ: ベルトより前、鼻と口より後ろ
        return winter.ORDER.index("P14") - 0.2
    return _order(key)


winter.inko_order = xmas_order
soft.inko_order = xmas_order


# ---- サンタ -----------------------------------------------------------------------
HAT_CONE = "M4 42 C6 24 20 8 42 5 C56 3 68 8 76 16 C80 20 79 25 75 27 C70 22 64 21 60 24 C58 30 62 36 66 42 C46 46 22 46 4 42 Z"  # 80x46。全部カーブ、先は右へたれる
BEARD = _circles(184, 96, 128, 54, 10, 42)        # 4倍(368x192 → 92x48)
BEARD_IN = _circles(184, 96, 128, 54, 10, 42, shrink=9)
STACHE_L = "M30 10 C24 2 12 0 4 6 C0 10 4 16 10 14 C16 12 22 14 30 14 Z"
STACHE_R = mirror(STACHE_L, 34)
SMILE = "M2 3 C6 11 16 11 20 3 C20 1 18 1 17.5 3 C14 8 8 8 4.5 3 C4 1 2 1 2 3 Z"
SMILE_OPEN = "M3 2 C3 1 19 1 19 2 C19 10 15 14 11 14 C7 14 3 10 3 2 Z"
BOOT = "M4 2 L18 2 L18 10 C23 10 26 13 26 18 L2 18 L2 10 C2 6 2 2 4 2 Z"


def santa(c):
    """サンタ(人の形): 顔 → 鼻(目の間の少し下)→ 白い口ひげ → 口(人のにっこり)。白いあごひげ。
    赤い帽子は顔について行き、先とぼんぼりは体より遅れて大きくゆれる。赤い服、白いすその毛、
    黒いベルトと金のバックルは体について行く。太い袖の腕と白い手、黒い長ぐつ。"""
    p = c.pop("_p", {})
    fx, fy = face_off(c)
    b = c["P4"]
    for k in ("P0", "P4"):
        e = c[k]
        w = min(e["h"] * 1.16, 124)
        cx = e["left"] + e["w"] / 2
        e.update(w=w, left=cx - w / 2, vw=w, vh=e["h"])
        e["d"] = e["keep"] = soft.ellipse_d(w, e["h"])
    b["fill"] = RED
    c.pop("P1", None)
    c.pop("P5", None)
    bx, by, bw, bh = b["left"], b["top"], b["w"], b["h"]
    bcx = bx + bw / 2
    # すその白い毛・ベルト・バックル(すべて体の位置から置く → 体と一緒に動く)
    put(c, "MID0_hem", WHITE, 2.4, bw * 0.7, 12, bcx - bw * 0.35, by + bh - 12, soft.ellipse_d(bw * 0.7, 12))
    put(c, "MID1_belt", "#3A2E2E", 2, bw * 0.9, 13, bcx - bw * 0.45, by + bh * 0.74, soft.ellipse_d(bw * 0.9, 13))
    put(c, "MID2_buckle", GOLD, 2, 20, 16, bcx - 10, by + bh * 0.74 - 2, "M3 1 L17 1 C19 1 19 3 19 3 L19 13 C19 15 17 15 17 15 L3 15 C1 15 1 13 1 13 L1 3 C1 1 3 1 3 1 Z")
    # 長ぐつ(黒+白い毛のふち)
    for k, x, up in (("P2", bcx - 22, p.get("hl", 0)), ("P3", bcx + 22, p.get("hr", 0))):
        d = BOOT if k == "P3" else mirror(BOOT, 28)
        c[k].update(d=d, fill="#3A2E2E", w=28, h=20, vw=28, vh=20, left=x - 14, top=by + bh - 10 - up, keep=d)
    # 腕: 太い袖(赤)+白い毛の袖口+白い手ぶくろ。肩を支点に大きく動く
    al, ar = p.get("al", 0), p.get("ar", 0)
    arm_part(c, "P6", bx + 10, by + bh * 0.45, 30 + al, 34, 22, RED_D, WHITE, 20, cuff=WHITE)
    arm_part(c, "P7", bx + bw - 10, by + bh * 0.45, -30 - ar, 34, 22, RED_D, WHITE, 20, cuff=WHITE)
    # 顔
    put(c, "FACE1", SKIN, 3.4, 80, 72, 120 + fx, 140 + fy, soft.ellipse_d(80, 72))
    put(c, "BEARD1", WHITE, 2, 86, 42, 117 + fx, 190 + fy, BEARD, vw=368, vh=192)
    put(c, "BEARD2_in", WHITE, 0, 86, 42, 117 + fx, 190 + fy, BEARD_IN, vw=368, vh=192)
    small_eyes(c, 0.86)
    c["P12"]["left"] += 6
    c["P13"]["left"] -= 6
    # 鼻(目の間の少し下)
    c["P14"].update(d=soft.ellipse_d(15, 12), fill=SKIN_D, w=15, h=12, vw=15, vh=12,
                    left=152.5 + fx, top=184 + fy, sw=2, stroke=inko.INK, keep=soft.ellipse_d(15, 12))
    # 口ひげ(鼻の下)と口(口ひげの下、人のにっこり)
    put(c, "P14y_stacheL", WHITE, 2, 24, 11, 136 + fx, 193 + fy, STACHE_L, vw=34, vh=16)
    put(c, "P14y_stacheR", WHITE, 2, 24, 11, 160 + fx, 193 + fy, STACHE_R, vw=34, vh=16)
    c["P15"].update(d=SMILE, fill=soft.LINE, sw=0, stroke=None, w=20, h=10, vw=22, vh=12, left=150 + fx, top=203 + fy,
                    keep=SMILE)
    # 帽子: ふち(白)は顔について行く。円すい部分は、ぼんぼりと一緒に swing 度だけ遅れてゆれる
    sw_ = p.get("hat", 0)
    band_cx, band_cy = 160 + fx, 146 + fy
    r = math.radians(sw_)
    cone_cx, cone_cy = band_cx + 4, band_cy - 20
    ccx = band_cx + (cone_cx - band_cx) * math.cos(r) - (cone_cy - band_cy) * math.sin(r)
    ccy = band_cy + (cone_cx - band_cx) * math.sin(r) + (cone_cy - band_cy) * math.cos(r)
    put(c, "ACC1_hat", RED, 2.4, 86, 48, ccx - 43, ccy - 24, HAT_CONE, rot=sw_, vw=80, vh=46)
    tip_x, tip_y = 77 / 80 * 86 - 43, 22 / 46 * 48 - 24  # 帽子の先(箱の中心から)
    px_ = ccx + tip_x * math.cos(r) - tip_y * math.sin(r)
    py_ = ccy + tip_x * math.sin(r) + tip_y * math.cos(r)
    band = "M10 6 C60 0 120 0 170 6 C180 8 182 14 182 20 C182 28 176 32 168 32 C120 26 60 26 12 32 C4 32 -2 28 -2 20 C-2 12 2 7 10 6 Z"
    put(c, "ACC2_hatband", WHITE, 2.4, 92, 20, band_cx - 46, band_cy - 10, band, vw=180, vh=36)  # ふちもゆるく弧に
    put(c, "ACC3_pom", WHITE, 2.4, 22, 22, px_ - 11, py_ - 11, soft.ellipse_d(22, 22))


def talk_santa(c):
    c["P15"].update(d=SMILE_OPEN, fill=soft.BEAK_OPEN_FILL, sw=1.5, stroke=inko.INK, keep=SMILE_OPEN)


def talk_deer(c):
    c["P15"].update(d=MOUTH_OPEN, fill=soft.BEAK_OPEN_FILL, sw=1.5, stroke=inko.INK, keep=MOUTH_OPEN)


# ---- ツリー(背景に置く。キャラには付いて行かない) ------------------------------------

def tier_path(w, h):
    """ツリーの段: 上はとがらせず丸く、横はふくらんだカーブ、下のふちは3つの波。直線を使わない。"""
    c = w / 2
    return (f"M{c - 4:.1f} 2 C{c - 2:.1f} 0 {c + 2:.1f} 0 {c + 4:.1f} 2 "
            f"C{c + w * 0.2:.1f} {h * 0.3:.1f} {w * 0.92:.1f} {h * 0.62:.1f} {w - 2:.1f} {h * 0.86:.1f} "
            f"C{w:.1f} {h - 1:.1f} {w * 0.84:.1f} {h:.1f} {w * 0.75:.1f} {h * 0.94:.1f} "
            f"C{w * 0.66:.1f} {h:.1f} {w * 0.56:.1f} {h:.1f} {c:.1f} {h * 0.94:.1f} "
            f"C{w * 0.44:.1f} {h:.1f} {w * 0.34:.1f} {h:.1f} {w * 0.25:.1f} {h * 0.94:.1f} "
            f"C{w * 0.16:.1f} {h:.1f} 0 {h - 1:.1f} 2 {h * 0.86:.1f} "
            f"C{w * 0.08:.1f} {h * 0.62:.1f} {c - w * 0.2:.1f} {h * 0.3:.1f} {c - 4:.1f} 2 Z")


def star_path(r):
    """角を丸めた5つの角の星(直線を使わない)。"""
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.48
        pts.append((r + rr * math.cos(a), r + rr * math.sin(a)))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for k in range(1, 11):
        x0, y0 = pts[k - 1]
        x1, y1 = pts[k % 10]
        d += f" C{x0 + (x1 - x0) * 0.4:.1f} {y0 + (y1 - y0) * 0.4 + (1 if k % 2 else -1):.1f} " \
             f"{x0 + (x1 - x0) * 0.6:.1f} {y0 + (y1 - y0) * 0.6:.1f} {x1:.1f} {y1:.1f}"
    return d + " Z"


def tree(x, y, k=1.0, lights=0):
    """ツリー(左上 x, y、高さ約 150*k)。深い緑の3段、赤と金の玉、てっぺんに金の星、茶色の幹。
    lights: 玉の色を順番に入れかえる(点滅ではなく、ゆっくり色が変わる)。"""
    def f(c):
        def tp(key, fill, sw, w, h, dx, dy, d):
            put(c, key, fill, sw, w * k, h * k, x + dx * k, y + dy * k, d, vw=w, vh=h)
        tp("BG3_trunk", "#8A5E40", 2.4, 22, 22, 49, 126, "M4 1 C8 0 14 0 18 1 C20 6 21 14 20 21 C14 22 8 22 2 21 C1 14 2 6 4 1 Z")
        tp("BG4_t3", GREEN, 2.4, 120, 54, 0, 80, tier_path(120, 54))
        tp("BG5_t2", GREEN, 2.4, 96, 50, 12, 46, tier_path(96, 50))
        tp("BG6_t1", GREEN, 2.4, 70, 48, 25, 12, tier_path(70, 48))
        cols = [RED, GOLD, "#FFFFFF", RED, GOLD, RED]
        spots = [(44, 50), (74, 64), (30, 90), (62, 100), (92, 108), (52, 72)]
        for j, (ox, oy) in enumerate(spots):
            tp(f"BG7_orn{j}", cols[(j + lights) % len(cols)], 2, 12, 12, ox - 6, oy - 6, soft.ellipse_d(12, 12))
        tp("BG8_star", GOLD, 2.4, 30, 30, 45, -8, star_path(15))
    return f


# ---- 台本 -------------------------------------------------------------------------
winter.say = say_xmas


def snowf(seed, n=6):
    return lambda i, av: winter.snow(seed, n, i, avoid=av)


def bells_travel(i, av):
    """ベル2つ: ゆれながら、上の方を左から右へ跳ねて進む(その場でゆれるだけにしない)。"""
    x = 40 + (i * 20) % 220
    y = 26 + abs(math.sin(i * 0.9)) * -10 + 14
    return [("bell", x, y, 14, 18 * math.sin(i * 1.3)), ("bell", (x + 110) % 230 + 40, y + 8, 12, -18 * math.sin(i * 1.3))]


def both(*fs):
    return lambda i, av: sum((f(i, av) for f in fs), [])


# 01 サンタ「メリー/クリスマス」: 真ん中の少し左に大きく。文字は右上へ斜めに。
#    跳ねて両手を上げ(ばんざい)、着地でぺこり。帽子の先は遅れて大きくゆれる。
POSE01 = [S, J0, J1, J1, J1, J0, S, B1, B2, B1, S, S]  # 高く跳ねすぎて文字にかからないよう J2 は使わない
MOVE01_OLD = [dict(), dict(al=-6, ar=-6, hat=-6), dict(al=30, ar=26, hat=-14, hl=4), dict(al=36, ar=34, hat=10, hl=6, hr=6),
          dict(al=26, ar=30, hat=18), dict(al=4, ar=8, hat=6, hr=4), dict(al=-4, ar=-2, hat=-8),
          dict(al=-14, ar=-14, hat=-12), dict(al=-18, ar=-18, hat=8), dict(al=-12, ar=-10, hat=14),
          dict(al=10, ar=-4, hat=-6, hl=3), dict(al=-4, ar=12, hat=4, hr=3)]
# 左手は大きくふり上げて手をふる、右手は少し遅れて小さく(左右で別の動き)
MOVE01 = [dict(), dict(al=10, ar=-8, hat=-6, hl=3), dict(al=34, ar=-4, hat=-14), dict(al=50, ar=8, hat=-4, hr=4),
          dict(al=36, ar=22, hat=12, hl=4), dict(al=52, ar=12, hat=18), dict(al=30, ar=-6, hat=6, hr=3),
          dict(al=-4, ar=-14, hat=-10), dict(al=-12, ar=-20, hat=6), dict(al=-6, ar=-12, hat=14),
          dict(al=24, ar=0, hat=-4, hl=3), dict(al=40, ar=10, hat=4, hr=3)]
# 05 トナカイ「おつかれ/さまです」: 左に置いて、文字は右に。前足を交互に大きく上げて歩く。鼻がぴかっ
MOVE05 = [dict(), dict(fl=26, lfl=8, el=-14, er=8, bell=3, glow=True), dict(fr=26, lfr=8, el=8, er=-14, bell=-3),
          dict(fl=30, lfl=10, el=-12, er=6, bell=3, glow=True), dict(fr=30, lfr=10, el=6, er=-12, bell=-3),
          dict(fl=24, lfl=8, hr=3, el=-14, er=8, bell=3, glow=True), dict(fr=24, lfr=8, hl=3, el=8, er=-14, bell=-3),
          dict(fl=30, lfl=10, el=-10, er=6, bell=2, glow=True), dict(fr=30, lfr=10, el=6, er=-10, bell=-2),
          dict(fl=20, lfl=6, el=-12, er=8, bell=3, glow=True), dict(fr=20, lfr=6, el=8, er=-12, bell=-3), dict(glow=True)]
BOB05 = [0, -3, 0, -3, 0, -3, 0, -3, 0, -3, 0, 0]


def bob(dy):
    return lambda c: winter.move(c, list(c), dy=dy) if hasattr(winter, "move") else inko.move(c, list(c), dy=dy)


STAMPS = {
    "01": make("xmas", [("メリー", 44, True), ("クリスマス", 32, True)], "B",
               lambda i: [POSE01[i], happy, P(**MOVE01[i]), santa, tree(300, 104, 0.9, i // 3)],
               both(bells_travel, snowf(1)),
               m=dict(scale=0.76, anchor=(100, 253)), x0=22),
    "05": make("xmas", [("おつかれ", 40, True), ("さまです", 30, False)], "A",
               lambda i: [S, happy, (lambda c, d=BOB05[i]: inko.move(c, list(c), dy=d)), P(**MOVE05[i]), reindeer,
                          tree(-80, 118, 0.77, i // 3)],
               lambda i, av: winter.snow(5, 5, i, avoid=av), m=dict(scale=0.88, anchor=(232, 258)), x0=20),
}

for name, frames in STAMPS.items():
    for i, fr in enumerate(frames):
        if i in soft.TALK_FRAMES:
            fr["poses"] = fr["poses"] + [talk_santa if name in ("01",) else talk_deer]


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
