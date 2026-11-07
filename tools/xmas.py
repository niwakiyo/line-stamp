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


GREEN, GREEN_D = "#2F7D5A", "#245F45"
GOLD_T = "#D08A10"  # 文字用の金(白いフチの上で読める濃さ)


def say_xmas(pal, *parts):
    """クリスマスのセリフ: 強調語は赤と緑を1字ずつ交互(金のフチ)、ほかの語は緑。カーブ・段差・大きさ違い。"""
    ws = newyear.say_curved("xmas", *parts)
    for w, (text, x, y, size, rot, strong, extra) in zip(ws, parts):
        # 3色以上のクリスマスカラーを1文字ずつ(強調語は赤・緑・金、語尾は深い緑・赤・金)
        w["colors"] = [RED, GREEN, GOLD_T] if strong else [GREEN_D, RED_D, GOLD_T]
        w["kanji_font"] = None  # セリフの漢字に筆の書体を使わない(やわらかい手書き風にそろえる)
        if text.isascii():  # 英字は字の間をつめる(日本語と同じ間だとばらばらに見える)
            w.update(spacing=0.6, outline=6, vary=False)
        elif size <= 36:  # 小さい文字は白いフチを細く、字の間を少し広げ、ゆれ・大きさの差を小さくして読みやすく
            w.update(outline=5, rim_w=2, spacing=1.06, vary=False)
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


HOLLY_LEAF = "M2 8 C6 2 10 6 13 2 C16 6 20 2 24 6 C28 4 32 6 34 8 C30 10 28 14 24 12 C20 16 16 12 13 14 C10 12 6 14 2 8 Z"


def holly(c, key, x, y, k=1.0, rot=0):
    """ヒイラギ: 深い緑の葉2枚と赤い実3つ(クリスマスの目印)。"""
    put(c, key + "a", GREEN, 2, 34 * k, 16 * k, x - 32 * k, y - 10 * k, HOLLY_LEAF, rot=rot - 20, vw=36, vh=16)
    put(c, key + "b", GREEN, 2, 34 * k, 16 * k, x - 2 * k, y - 10 * k, mirror(HOLLY_LEAF, 36), rot=rot + 20, vw=36, vh=16)
    for j, (dx, dy) in enumerate(((-6, -4), (2, -8), (5, 0))):
        put(c, key + f"c{j}", RED, 2, 9 * k, 9 * k, x + dx * k - 4.5 * k, y + dy * k - 4.5 * k, soft.ellipse_d(9, 9))


# ---- トナカイ ---------------------------------------------------------------------
DEER, DEER_FACE, DEER_D, DEER_FRONT, HOOF = "#8C5A3A", "#DDB383", "#6B4329", "#D2A675", "#3E2A22"  # 体はこい茶、顔は明るい黄土、前足は明るい茶、後ろ足はこげ茶
MUZZLE, ANTLER, ANTLER_L2 = "#FFF3E2", "#E8C690", "#B58758"   # 角は明るいベージュ(こい茶だと木の枝に見える)
EAR_IN = "#F7C9C3"
# 角(左): 4倍の座標(200x200)。根元(下・太い)は頭のてっぺんに重ねる。大きく枝分かれ。右は鏡うつし
ANTLER_OLD = ("M150 196 C146 168 138 140 124 118 C108 94 84 80 56 70 C40 64 28 52 30 38 C34 26 48 28 52 40 "
             "C56 52 70 60 86 66 C82 50 74 34 62 20 C56 12 62 0 74 6 C90 18 98 40 102 62 "
             "C106 74 112 82 118 86 C118 66 120 46 128 30 C132 20 146 20 146 32 C142 56 136 78 140 100 "
             "C146 128 158 160 170 196 Z")
# 角(左・ベージュ・小さめ): 100x100。下が根元、枝先は丸い。右は鏡うつし
ANTLER_LP = ("M70 98 C68 80 62 64 52 52 C44 42 32 38 22 36 C14 34 10 26 16 22 C22 18 28 24 32 28 "
             "C38 32 44 34 48 34 C46 26 42 18 36 12 C32 6 36 0 42 2 C50 6 54 18 56 30 "
             "C58 36 60 40 62 42 C64 32 68 24 74 18 C78 14 86 16 84 24 C80 32 74 40 72 50 "
             "C72 66 78 82 82 98 Z")
ANTLER_RP = mirror(ANTLER_LP, 100)
TUFT = _circles(120, 60, 70, 26, 7, 30)        # 頭のてっぺんの毛のかたまり(4倍 240x120 → 60x30)
TUFT_IN = _circles(120, 60, 70, 26, 7, 30, shrink=8)
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
    # 角: 前髪(毛のかたまり)の両わきから、外へ広がる。根元は前髪と顔にかくす
    put(c, "ANTL1", ANTLER, 2.6, 56, 56, 96 + fx, 92 + fy, ANTLER_LP, vw=100, vh=100)
    put(c, "ANTL2", ANTLER, 2.6, 56, 56, 168 + fx, 92 + fy, ANTLER_RP, vw=100, vh=100)
    deer_ear(c, 130 + fx, 160 + fy, -1, -20 + p.get("el", 0))
    deer_ear(c, 190 + fx, 160 + fy, 1, 20 + p.get("er", 0))
    put(c, "FACE1", DEER_FACE, 3.4, 80, 70, 120 + fx, 140 + fy, soft.ellipse_d(80, 70))
    put(c, "FACE2_muzzle", MUZZLE, 2.4, 54, 32, 133 + fx, 176 + fy, soft.ellipse_d(54, 32))
    # 頭のてっぺんの毛のかたまり(つるつるに見えないように)とヒイラギ
    put(c, "P7y_tuft", DEER, 2.4, 60, 30, 130 + fx, 128 + fy, TUFT, vw=240, vh=120)
    put(c, "P7y_tuftin", DEER, 0, 60, 30, 130 + fx, 128 + fy, TUFT_IN, vw=240, vh=120)
    holly(c, "P7z_holly", 182 + fx, 140 + fy, 0.8)
    small_eyes(c)
    inko.move(c, ["P8", "P9", "P10", "P11"], dy=-13)  # 目は口元よりはっきり上(顔の上半分)
    inko.move(c, ["P8", "P10"], dx=-3)
    inko.move(c, ["P9", "P11"], dx=3)
    c["P12"]["left"] += 8
    c["P13"]["left"] -= 8
    glow = False  # 鼻は点滅させない(目のまわりがちかちかしないように)
    nx, ny = 160 + fx, 185 + fy
    c["P14"].update(d=soft.ellipse_d(20, 16), fill="#FF6157" if glow else "#E2463F", w=20, h=16, vw=20, vh=16,
                    left=nx - 10, top=ny - 9, sw=2, stroke=inko.INK, keep=soft.ellipse_d(20, 16))
    put(c, "P14z_shine", WHITE, 0, 6, 4, nx - 6, ny - 6, soft.ellipse_d(6, 4))
    c["P15"].update(d=MOUTH, fill=soft.LINE, sw=0, stroke=None, top=ny + 5)


_order = winter.inko_order


def xmas_order(key):
    if key.startswith("FACE0a"):  # 角: 体より前、顔より後ろ
        return winter.ORDER.index("P5") - 0.7
    if key.startswith("FACE0b"):  # 耳
        return winter.ORDER.index("P5") - 0.6
    if key.startswith("P0a") or key.startswith("P0b"):  # サンタの袋: 体の後ろ
        return -0.2
    if key.startswith("GLS1") or key.startswith("GLS2"):  # レンズと光: 目より後ろ(目は見える)
        return winter.ORDER.index("P8") - 0.2 + (0.05 if key.startswith("GLS2") else 0)
    if key.startswith("GLS"):  # つる・ふち・びょう: 目より前
        return len(winter.ORDER) + 0.5
    if key.startswith("ANTL"):  # 角: 体より前、顔より後ろ(根元は顔の上のふちでかくれる)
        return winter.ORDER.index("P5") - 0.8
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
    HEAD = -12  # 頭を体の上にのせる(顔の部品ごと上へ)
    inko.move(c, ["P8", "P9", "P10", "P11", "P12", "P13", "P14", "P15"], dy=HEAD)
    fy += HEAD
    b = c["P4"]
    for k in ("P0", "P4"):  # 体は短く(上を下げる)、横に広い丸
        e = c[k]
        e["top"] += 18
        e["h"] -= 18
        w = min(e["h"] * 1.25, 122)
        cx = e["left"] + e["w"] / 2
        e.update(w=w, left=cx - w / 2, vw=w, vh=e["h"])
        e["d"] = e["keep"] = soft.ellipse_d(w, e["h"])
    b["fill"] = RED
    c.pop("P1", None)
    c.pop("P5", None)
    bx, by, bw, bh = b["left"], b["top"], b["w"], b["h"]
    bcx = bx + bw / 2
    if p.get("sack", True):  # 白い大きな袋を背中にかつぐ(体の後ろ・体について行く)
        sack = "M30 4 C44 2 60 8 66 22 C72 38 66 58 48 64 C30 70 10 62 4 46 C-2 30 8 10 30 4 Z"
        put(c, "P0a_sack", "#F4EEE2", 2.6, 70, 66, bx - 34, by - 30, sack, vw=70, vh=68)
        put(c, "P0b_sacktie", RED, 2, 20, 10, bx + 18, by - 26, soft.ellipse_d(20, 10), rot=30)
    # すその白い毛・ベルト・バックル(すべて体の位置から置く → 体と一緒に動く)
    put(c, "MID0_hem", WHITE, 2.4, bw * 0.7, 12, bcx - bw * 0.35, by + bh - 12, soft.ellipse_d(bw * 0.7, 12))
    put(c, "MID1_belt", "#3A2E2E", 2, bw * 0.92, 13, bcx - bw * 0.46, by + bh * 0.66, soft.ellipse_d(bw * 0.92, 13))
    put(c, "MID2_buckle", GOLD, 2, 20, 16, bcx - 10, by + bh * 0.66 - 2, "M3 1 L17 1 C19 1 19 3 19 3 L19 13 C19 15 17 15 17 15 L3 15 C1 15 1 13 1 13 L1 3 C1 1 3 1 3 1 Z")
    # 長ぐつ(黒+白い毛のふち)
    for k, x, up in (("P2", bcx - 22, p.get("hl", 0)), ("P3", bcx + 22, p.get("hr", 0))):
        d = BOOT if k == "P3" else mirror(BOOT, 28)
        c[k].update(d=d, fill="#3A2E2E", w=28, h=20, vw=28, vh=20, left=x - 14, top=by + bh - 10 - up, keep=d)
    # 腕: 太い袖(赤)+白い毛の袖口+白い手ぶくろ。肩を支点に大きく動く
    al, ar = p.get("al", 0), p.get("ar", 0)
    # 肩より上へ上げるときは腕を少しずつ長くする(短いままだと手が顔の横で止まり「上げた」に見えない)
    lal, lar = 34 + max(0, al - 50) * 0.3, 34 + max(0, ar - 50) * 0.3
    arm_part(c, "P6", bx + 12, by + bh * 0.3, 30 + al, lal, 22, RED_D, WHITE, 20, cuff=WHITE)
    arm_part(c, "P7", bx + bw - 12, by + bh * 0.3, -30 - ar, lar, 22, RED_D, WHITE, 20, cuff=WHITE)
    hold = p.get("hold", "gift" if p.get("gift", True) else None)
    if hold:  # 右手(見て左)に持つ物。手について行く
        h_ = c[p.get("hand", "P6") + "_hand"]
        hx_, hy_ = h_["left"] + h_["w"] / 2, h_["top"] + h_["h"] / 2
        if hold in ("gift", "biggift"):
            g = 1.0 if hold == "gift" else 1.6
            bx_ = hx_ - 22 * g
            put(c, "P7zz_box", GREEN, 2.4, 28 * g, 24 * g, bx_, hy_ - 22 * g,
                "M3 1 L25 1 C27 1 27 3 27 3 L27 21 C27 23 25 23 25 23 L3 23 C1 23 1 21 1 21 L1 3 C1 1 3 1 3 1 Z", vw=28, vh=24)
            put(c, "P7zz_rib1", GOLD, 0, 6 * g, 24 * g, bx_ + 11 * g, hy_ - 22 * g, soft.ellipse_d(6, 24), vw=6, vh=24)
            put(c, "P7zz_rib2", GOLD, 0, 28 * g, 6 * g, bx_, hy_ - 13 * g, soft.ellipse_d(28, 6), vw=28, vh=6)
            put(c, "P7zz_bowL", GOLD, 2, 12 * g, 9 * g, bx_ + 2 * g, hy_ - 29 * g, winter.LOOP_L, vw=18, vh=14)
            put(c, "P7zz_bowR", GOLD, 2, 12 * g, 9 * g, bx_ + 14 * g, hy_ - 29 * g, winter.LOOP_R, vw=18, vh=14)
        elif hold == "glass":  # シャンパングラス(金色の中身と泡)
            put(c, "P7zz_gbowl", "#F7E3A0", 2.4, 20, 26, hx_ - 10, hy_ - 40,
                "M2 2 L18 2 C18 14 15 22 10 24 C5 22 2 14 2 2 Z", vw=20, vh=26)
            put(c, "P7zz_gstem", "#EAF6FF", 2, 4, 14, hx_ - 2, hy_ - 16, soft.ellipse_d(4, 14), vw=4, vh=14)
            put(c, "P7zz_gbase", "#EAF6FF", 2, 16, 5, hx_ - 8, hy_ - 4, soft.ellipse_d(16, 5), vw=16, vh=5)
            for j, (dx, dy) in enumerate(((-3, -30), (3, -24), (-1, -20))):
                put(c, f"P7zz_gb{j}", WHITE, 0, 3, 3, hx_ + dx, hy_ + dy, soft.ellipse_d(3, 3))
        elif hold == "star":  # ツリーのてっぺんにのせる金の星
            put(c, "P7zz_star", GOLD, 2.4, 34, 34, hx_ - 17, hy_ - 36, star_path(17), vw=34, vh=34)
    # 顔
    put(c, "FACE1", SKIN, 3.4, 80, 72, 120 + fx, 140 + fy, soft.ellipse_d(80, 72))
    # ひげ: ほっぺの横から胸まで覆う大きなもこもこ。横の白い髪(帽子のふちの下)とつながる
    put(c, "BEARD1", WHITE, 2.4, 96, 52, 112 + fx, 194 + fy, BEARD, vw=368, vh=192)
    put(c, "BEARD2_in", WHITE, 0, 96, 52, 112 + fx, 194 + fy, BEARD_IN, vw=368, vh=192)
    for side, x0 in ((-1, 121), (1, 199)):  # もみあげ: 帽子のふちの下から、ひげへなめらかにつながる白い楕円
        put(c, f"BEARD0_hair{side}", WHITE, 2.4, 18, 40, x0 - 9 + fx, 160 + fy, soft.ellipse_d(18, 40))
    small_eyes(c, 0.86)
    # 白くてふさふさの眉毛(おじいさん)。外側は少し下がる。左右は鏡うつし
    # ふさふさ: 上のふちを小さく3つ波打たせ、外側の毛先が下へたれる
    BROW_R = ("M2 13 C2 7 6 4 10 5 C12 1 18 0 21 3 C24 1 30 3 31 8 C34 10 35 15 33 18 "
              "C31 15 28 14 25 15 C21 12 16 13 12 15 C8 13 5 14 2 13 Z")
    for side, key in ((-1, "P8"), (1, "P9")):
        e = c[key]
        ex, ey = e["left"] + e["w"] / 2, e["top"] + e["h"] / 2 + 5
        d = BROW_R if side > 0 else mirror(BROW_R, 35)
        put(c, f"GLS4_brow{side}", WHITE, 2.4, 32, 17, ex - 16 + side * 3, ey - 18, d, vw=35, vh=19)
    c["P12"]["left"] += 6
    c["P13"]["left"] -= 6
    # 鼻(目の間の少し下)
    c["P14"].update(d=soft.ellipse_d(15, 12), fill=SKIN_D, w=15, h=12, vw=15, vh=12,
                    left=152.5 + fx, top=187 + fy, sw=2, stroke=inko.INK, keep=soft.ellipse_d(15, 12))
    # 口ひげ(鼻の下)と口(口ひげの下、人のにっこり)
    put(c, "P14y_stacheL", WHITE, 2, 24, 11, 136 + fx, 195 + fy, STACHE_L, vw=34, vh=16)
    put(c, "P14y_stacheR", WHITE, 2, 24, 11, 160 + fx, 195 + fy, STACHE_R, vw=34, vh=16)
    c["P15"].update(d=SMILE, fill=soft.LINE, sw=0, stroke=None, w=20, h=10, vw=22, vh=12, left=150 + fx, top=204 + fy,
                    keep=SMILE)
    # 帽子: ふち(白)は顔について行く。円すい部分は、ぼんぼりと一緒に swing 度だけ遅れてゆれる
    sw_ = p.get("hat", 0)
    band_cx, band_cy = 160 + fx, 158 + fy  # 帽子のふちは眉の高さ(はだ色のおでこを見せない)
    r = math.radians(sw_)
    cone_cx, cone_cy = band_cx + 4, band_cy - 24
    ccx = band_cx + (cone_cx - band_cx) * math.cos(r) - (cone_cy - band_cy) * math.sin(r)
    ccy = band_cy + (cone_cx - band_cx) * math.sin(r) + (cone_cy - band_cy) * math.cos(r)
    put(c, "ACC1_hat", RED, 2.6, 100, 56, ccx - 50, ccy - 28, HAT_CONE, rot=sw_, vw=80, vh=46)  # 顔より広く
    tip_x, tip_y = 77 / 80 * 100 - 50, 22 / 46 * 56 - 28  # 帽子の先(箱の中心から)
    px_ = ccx + tip_x * math.cos(r) - tip_y * math.sin(r)
    py_ = ccy + tip_x * math.sin(r) + tip_y * math.cos(r)
    band = "M10 6 C60 0 120 0 170 6 C180 8 182 14 182 20 C182 28 176 32 168 32 C120 26 60 26 12 32 C4 32 -2 28 -2 20 C-2 12 2 7 10 6 Z"
    put(c, "ACC2_hatband", WHITE, 2.6, 100, 22, band_cx - 50, band_cy - 11, band, vw=180, vh=36)  # ふちもゆるく弧に
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


def tree(x, y, k=1.0, lights=0, style="ball"):
    """ツリー(左上 x, y、高さ約 150*k)。深い緑の3段、赤と金の玉、てっぺんに金の星、茶色の幹。
    lights: 玉の色を順番に入れかえる(点滅ではなく、ゆっくり色が変わる)。"""
    def f(c):
        def tp(key, fill, sw, w, h, dx, dy, d):
            put(c, key, fill, sw, w * k, h * k, x + dx * k, y + dy * k, d, vw=w, vh=h)
        tp("BG3_trunk", "#8A5E40", 2.4, 22, 22, 49, 126, "M4 1 C8 0 14 0 18 1 C20 6 21 14 20 21 C14 22 8 22 2 21 C1 14 2 6 4 1 Z")
        tp("BG4_t3", GREEN, 2.4, 120, 54, 0, 80, tier_path(120, 54))
        tp("BG5_t2", GREEN, 2.4, 96, 50, 12, 46, tier_path(96, 50))
        tp("BG6_t1", GREEN, 2.4, 70, 48, 25, 12, tier_path(70, 48))
        if style == "ball":  # 金のモール(ゆるい弧)と赤・金の玉、てっぺんに金の星
            for j, (y0, w0) in enumerate(((40, 34), (74, 54), (110, 76))):  # 段の内側に収まる幅
                tp(f"BG7_garland{j}", GOLD, 0, w0, 7, 60 - w0 / 2, y0, "M1 1 C30 9 60 9 89 1 L89 4 C60 12 30 12 1 4 Z")
                c[f"BG7_garland{j}"].update(vw=90, vh=12)
            cols = [RED, GOLD, RED, "#FFFFFF", RED, GOLD]
            spots = [(44, 38), (76, 60), (30, 88), (62, 98), (94, 108), (50, 66)]
            for j, (ox, oy) in enumerate(spots):
                tp(f"BG7_orn{j}", cols[(j + lights) % len(cols)], 2, 13, 13, ox - 6.5, oy - 6.5, soft.ellipse_d(13, 13))
            tp("BG8_star", GOLD, 2.4, 32, 32, 44, -10, star_path(16))
        elif style == "lights":  # 電球のツリー: 電球をたくさん、てっぺんの星から光の線が出る
            for j, (y0, w0) in enumerate(((36, 40), (70, 62), (106, 86))):
                tp(f"BG7_wire{j}", GOLD, 0, w0, 7, 60 - w0 / 2, y0, "M1 1 C30 9 60 9 89 1 L89 4 C60 12 30 12 1 4 Z")
                c[f"BG7_wire{j}"].update(vw=90, vh=12)
            lc = [GOLD, RED, "#7FC4FF", "#FF9AC8", WHITE]
            spots = [(42, 38), (58, 42), (76, 38), (30, 72), (46, 76), (62, 78), (80, 76), (94, 72),
                     (18, 108), (34, 112), (50, 114), (66, 114), (84, 112), (100, 108)]
            for j, (ox, oy) in enumerate(spots):
                tp(f"BG7_light{j}", lc[(j + lights) % 5], 1.5, 10, 11, ox - 5, oy - 3, soft.ellipse_d(10, 11))
            for j, a in enumerate((-150, -110, -70, -30)):  # 星の光の線(長さが交互に変わる)
                ra = math.radians(a)
                ln = 14 + 6 * ((j + lights) % 2)
                tp(f"BG7z_ray{j}", "#FFE27A", 1.5, ln, 5, 60 + 22 * math.cos(ra) - ln / 2, 6 + 22 * math.sin(ra), winter.RAY)
                c[f"BG7z_ray{j}"].update(vw=14, vh=5, rot=a)
            tp("BG8_star", GOLD, 2.4, 34, 34, 43, -12, star_path(17))
        else:  # 雪をかぶったツリー: 段の上に白い雪、赤いリボン、てっぺんは赤い大きなリボン、根元にプレゼント
            snowcap = "M2 10 C8 2 20 0 30 4 C40 0 52 2 58 10 C52 14 46 12 42 16 C36 12 24 12 18 16 C14 12 8 14 2 10 Z"
            for j, (oy, w0) in enumerate(((10, 34), (46, 54), (82, 74))):  # 段の上のふちにのる白い雪
                tp(f"BG7_snow{j}", WHITE, 2, w0, 12, 60 - w0 / 2, oy + 4, snowcap)
                c[f"BG7_snow{j}"].update(vw=60, vh=18)
            for j, (ox, oy) in enumerate(((60, 42), (40, 80), (82, 84), (60, 116))):  # 大きめの赤いリボン4つ
                tp(f"BG7_bowL{j}", RED, 2, 18, 14, ox - 18, oy - 7, winter.LOOP_L)
                c[f"BG7_bowL{j}"].update(vw=18, vh=14)
                tp(f"BG7_bowR{j}", RED, 2, 18, 14, ox, oy - 7, winter.LOOP_R)
                c[f"BG7_bowR{j}"].update(vw=18, vh=14)
                tp(f"BG7_bowK{j}", GOLD, 1.5, 7, 7, ox - 3.5, oy - 3.5, soft.ellipse_d(7, 7))
            for j, (y0, w0) in enumerate(((30, 40), (64, 62), (100, 86))):  # 電球をつなぐ金のひも(ゆるい弧)
                tp(f"BG7_wire{j}", GOLD, 0, w0, 7, 60 - w0 / 2, y0, "M1 1 C30 9 60 9 89 1 L89 4 C60 12 30 12 1 4 Z")
                c[f"BG7_wire{j}"].update(vw=90, vh=12)
            lcols = [GOLD, RED, "#FFFFFF", "#7FC4FF", "#FF9AC8"]  # 電球はコマごとに色が入れかわって点滅
            lspots = [(44, 32), (60, 34), (76, 32), (32, 66), (50, 70), (70, 70), (88, 66),
                      (22, 102), (40, 106), (60, 108), (80, 106), (98, 102)]
            for j, (ox, oy) in enumerate(lspots):
                tp(f"BG7_light{j}", lcols[(j + lights) % 5], 1.5, 9, 10, ox - 4.5, oy - 3, soft.ellipse_d(9, 10))
            tp("BG8_topL", RED, 2, 20, 16, 40, 2, winter.LOOP_L)
            tp("BG8_topR", RED, 2, 20, 16, 60, 2, winter.LOOP_R)
            c["BG8_topL"].update(vw=18, vh=14)
            c["BG8_topR"].update(vw=18, vh=14)
            tp("BG8_star", GOLD, 2.4, 30, 30, 45, -22, star_path(15))
            # 根元: 雪の山、杖のキャンディ
            tp("BG8z_mound", WHITE, 2.4, 150, 22, -15, 138, "M2 20 C20 6 50 2 75 4 C100 2 130 6 148 20 C100 24 50 24 2 20 Z")
            c["BG8z_mound"].update(vw=150, vh=24)
            cane = "M14 46 L14 12 C14 6 10 3 6 3 C3 3 1 6 1 9 L5 9 C5 8 5 7 6 7 C8 7 10 9 10 12 L10 46 Z"
            tp("BG9_cane", WHITE, 2, 16, 48, 112, 96, cane)
            c["BG9_cane"].update(vw=16, vh=48)
            for j in range(4):
                tp(f"BG9_canest{j}", RED, 0, 5, 4, 122, 106 + j * 9, soft.ellipse_d(5, 4))
            tp("BG9_giftA", RED, 2.4, 30, 24, -6, 126, "M3 1 L27 1 C29 1 29 3 29 3 L29 21 C29 23 27 23 27 23 L3 23 C1 23 1 21 1 21 L1 3 C1 1 3 1 3 1 Z")
            tp("BG9_ribA", GOLD, 0, 6, 24, 6, 126, soft.ellipse_d(6, 24))
            tp("BG9_giftC", "#7FC4FF", 2.4, 22, 18, 22, 134, "M3 1 L19 1 C21 1 21 3 21 3 L21 15 C21 17 19 17 19 17 L3 17 C1 17 1 15 1 15 L1 3 C1 1 3 1 3 1 Z")
            tp("BG9_ribC", WHITE, 0, 22, 4, 22, 141, soft.ellipse_d(22, 4))
            tp("BG9_giftB", GOLD, 2.4, 26, 20, 94, 130, "M3 1 L23 1 C25 1 25 3 25 3 L25 17 C25 19 23 19 23 19 L3 19 C1 19 1 17 1 17 L1 3 C1 1 3 1 3 1 Z")
            tp("BG9_ribB", RED, 0, 5, 20, 104, 130, soft.ellipse_d(5, 20))
    return f


_dm = soft.draw_marks


def _bez(p0, p1, p2, p3, n=14):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
            for t in [i / n for i in range(n + 1)]]


def sleigh_image(k=1.0, tilt=0, part="all"):
    """そり(右向き)を1枚の画像に描く。3倍の大きさで描いてから縮めて、線をなめらかにする。
    - 本体: 赤。うしろ(左)は丸く高い背もたれ、前(右)は大きく反り上がってくるっと巻く。金のふちどりと金のうず飾り
    - すべり木: 金。前は上へ大きく巻き上がる。本体とは金の支柱2本でつなぐ
    - 荷物: プレゼントの箱を3つ積む(緑+金のリボン、金+赤のリボン、水色+白のリボン)。どれもリボン結び付き"""
    from PIL import ImageDraw
    S = 3 * k
    W, H = int(150 * S), int(110 * S)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    L = soft.LINE
    lw = max(2, round(2.6 * S))

    def P(pts):
        return [(x * S, y * S) for x, y in pts]

    def box(x, y, w, h, fill, rib, bow=True):
        d.rounded_rectangle(P([(x, y), (x + w, y + h)]), radius=2 * S, fill=fill, outline=L, width=lw)
        d.rectangle(P([(x + w / 2 - 2.5, y + 1), (x + w / 2 + 2.5, y + h - 1)]), fill=rib)
        d.rectangle(P([(x + 1, y + h / 2 - 2.2), (x + w - 1, y + h / 2 + 2.2)]), fill=rib)
        if bow:
            cx, cy = x + w / 2, y
            d.ellipse(P([(cx - 9, cy - 7), (cx - 1, cy + 1)]), fill=rib, outline=L, width=lw)
            d.ellipse(P([(cx + 1, cy - 7), (cx + 9, cy + 1)]), fill=rib, outline=L, width=lw)
            d.ellipse(P([(cx - 2.5, cy - 4), (cx + 2.5, cy + 1)]), fill=rib, outline=L, width=lw)

    # 荷物(本体のうしろにのせる): 左から大・中・上に小
    # part="gifts" は「サンタが乗るとき」の荷物だけ(背もたれの上・うしろに高く積む)、part="body" はそりだけ
    if part == "all":
        box(40, 22, 32, 30, GREEN, GOLD)
        box(70, 30, 26, 24, GOLD, RED)
        box(50, 2, 22, 20, "#7FC4FF", WHITE)
    elif part == "gifts":
        box(4, 20, 30, 30, GREEN, GOLD)
        box(26, 30, 22, 22, GOLD, RED)
        box(10, 2, 20, 18, "#7FC4FF", WHITE)
        im = im.resize((W // 3, H // 3), Image.LANCZOS)
        return im.rotate(tilt, resample=Image.BICUBIC, expand=True) if tilt else im
    # すべり木(金): 下の線と、前の巻き上がり
    run = _bez((14, 92), (40, 98), (96, 98), (116, 90)) + _bez((116, 90), (134, 84), (140, 64), (128, 60)) \
        + _bez((128, 60), (120, 58), (116, 68), (124, 70))
    d.line(P(run), fill=L, width=round(7 * S), joint="curve")
    d.line(P(run), fill=GOLD, width=round(4 * S), joint="curve")
    for x in (36, 88):  # 支柱
        d.line(P([(x, 80), (x, 92)]), fill=L, width=round(6 * S))
        d.line(P([(x, 80), (x, 92)]), fill=GOLD, width=round(3 * S))
    # 本体(赤): 背もたれは丸く高く、前は反り上がってくるっと巻く
    body = (_bez((10, 48), (6, 30), (14, 22), (26, 26)) + _bez((26, 26), (32, 30), (30, 46), (40, 52))
            + _bez((40, 52), (64, 58), (90, 54), (106, 44)) + _bez((106, 44), (116, 36), (128, 34), (128, 44))
            + _bez((128, 44), (128, 52), (120, 56), (114, 54)) + _bez((114, 54), (112, 70), (100, 82), (80, 84))
            + _bez((80, 84), (56, 86), (28, 84), (16, 74)) + _bez((16, 74), (10, 66), (10, 56), (10, 48)))
    d.polygon(P(body), fill=RED, outline=L)
    d.line(P(body + body[:1]), fill=L, width=lw, joint="curve")
    # 金のふちどり(本体のふちに沿う線)と、横の金のうず飾り
    trim = _bez((18, 70), (40, 78), (80, 78), (108, 60))
    d.line(P(trim), fill=GOLD, width=round(3.2 * S), joint="curve")
    swirl = _bez((60, 66), (52, 60), (60, 54), (66, 58)) + _bez((66, 58), (70, 62), (66, 66), (63, 63))
    d.line(P(swirl), fill=GOLD, width=round(2.6 * S), joint="curve")
    d.ellipse(P([(118, 39), (124, 45)]), fill=GOLD, outline=L, width=max(1, lw // 2))  # 巻きの先の金の玉
    im = im.resize((W // 3, H // 3), Image.LANCZOS)
    if tilt:
        im = im.rotate(tilt, resample=Image.BICUBIC, expand=True)
    return im


_SLEIGH_CACHE = {}


def draw_marks_x(layer, marks, ox, oy):
    """空を飛ぶそり(右向き・プレゼントを積む)と、うしろに続く金の星くず。"""
    from PIL import ImageDraw
    d = ImageDraw.Draw(layer)
    rest = []
    for m in marks:
        if m[0] != "sleigh":
            rest.append(m)
            continue
        _, x, y, k, tilt = m
        x, y = ox + x, oy + y
        for j in range(5):  # 星くず: そりのうしろ(左下)へ、だんだん小さく
            r = 4.6 - j * 0.55
            sx, sy = x - 44 * k - j * 9, y + 22 * k + j * 4
            if sx - r < 12:
                break
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=GOLD if j % 2 == 0 else WHITE, outline=soft.LINE)
        key = (round(k, 2), round(tilt))
        if key not in _SLEIGH_CACHE:
            _SLEIGH_CACHE[key] = sleigh_image(k, tilt)
        im = _SLEIGH_CACHE[key]
        layer.alpha_composite(im, (round(x - im.width / 2), round(y - im.height / 2)))
    _dm(layer, rest, ox, oy)


soft.draw_marks = draw_marks_x


# ---- 台本 -------------------------------------------------------------------------
winter.say = say_xmas


def snowf(seed, n=6):
    return lambda i, av: winter.snow(seed, n, i, avoid=av)


def bells_travel(i, av):
    """ベル2つ: ゆれながら、上の方を左から右へ跳ねて進む(その場でゆれるだけにしない)。"""
    # 文字の四角(av)にかからない右上だけで、跳ねながら左右に行き来する
    t = i / 11 * 2 * math.pi
    x = 262 + 14 * math.sin(t)
    y = 34 - 10 * abs(math.sin(t * 2))
    return [("bell", x, y + 4, 21, 18 * math.sin(i * 1.3)), ("bell", x + 20 * math.cos(t) - 6, y + 44, 17, -18 * math.sin(i * 1.3))]


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
MOVE01 = [dict(), dict(ar=10, al=-8, hat=-6, hl=3), dict(ar=34, al=-4, hat=-14), dict(ar=50, al=8, hat=-4, hr=4),
          dict(ar=36, al=22, hat=12, hl=4), dict(ar=52, al=12, hat=18), dict(ar=30, al=-6, hat=6, hr=3),
          dict(ar=-4, al=-14, hat=-10), dict(ar=-12, al=-20, hat=6), dict(ar=-6, al=-12, hat=14),
          dict(ar=24, al=0, hat=-4, hl=3), dict(ar=40, al=10, hat=4, hr=3)]
# 05 トナカイ「おつかれ/さまです」: 左に置いて、文字は右に。前足を交互に大きく上げて歩く。鼻がぴかっ
MOVE05_OLD = [dict(), dict(fl=26, lfl=8, el=-14, er=8, bell=3, glow=True), dict(fr=26, lfr=8, el=8, er=-14, bell=-3),
          dict(fl=30, lfl=10, el=-12, er=6, bell=3, glow=True), dict(fr=30, lfr=10, el=6, er=-12, bell=-3),
          dict(fl=24, lfl=8, hr=3, el=-14, er=8, bell=3, glow=True), dict(fr=24, lfr=8, hl=3, el=8, er=-14, bell=-3),
          dict(fl=30, lfl=10, el=-10, er=6, bell=2, glow=True), dict(fr=30, lfr=10, el=6, er=-10, bell=-2),
          dict(fl=20, lfl=6, el=-12, er=8, bell=3, glow=True), dict(fr=20, lfr=6, el=8, er=-12, bell=-3), dict(glow=True)]
MOVE05 = [dict(), dict(fl=30, lfl=10, hr=5, el=-16, er=8, bell=4), dict(fr=30, lfr=10, hl=5, el=8, er=-16, bell=-4),
          dict(fl=30, lfl=10, hr=5, el=-16, er=8, bell=4), dict(fr=30, lfr=10, hl=5, el=8, er=-16, bell=-4),
          dict(fl=24, lfl=8, hr=4, el=-12, er=6, bell=3), dict(el=6, er=-6, bell=-2), dict(el=-8, er=8, bell=2),
          dict(fl=28, fr=28, lfl=8, lfr=8, el=-14, er=-14, bell=4), dict(fl=34, fr=34, lfl=12, lfr=12, hl=4, hr=4, el=-18, er=-18, bell=-4),
          dict(fl=20, fr=20, lfl=6, lfr=6, el=-8, er=-8, bell=3), dict(el=4, er=-4)]
BOB05 = [0] * 12


def bob(dy):
    return lambda c: winter.move(c, list(c), dy=dy) if hasattr(winter, "move") else inko.move(c, list(c), dy=dy)


# 01 サンタ: ツリーの方(右)から、跳ねながら左へ歩いてきて、止まって手をふる
WALK01 = [(132, 256), (168, 252), (162, 246), (160, 252), (150, 246), (140, 252), (132, 256), (132, 256), (132, 251),
          (132, 252), (132, 250), (132, 256)]
S01, S05 = 0.92, 0.92


def tree_page(px, py, ph, anchor, scale, lights, style="ball"):
    """ツリーを、スタンプの上の位置(左上 px,py・高さ ph)で置く(キャラの拡大・位置に左右されない)。"""
    k = ph / 160 / scale
    return tree(160 + (px - anchor[0]) / scale, 258 + (py - anchor[1]) / scale + 10 * k, k, lights, style)
# 05 トナカイ: 右から走ってきて(体がはずむ)、止まって、ぴょんと跳ねる
# 空を飛ぶ大きなそり: 右から左上へ、波打ちながら(文字の右側の空)。1コマ目は完成形の位置
# そり: 右から左へ、空を一気に駆け抜ける(1コマ約45px)。駆け抜けたあとは消える。1コマ目は真ん中
# そり: 左下から右上へ、だんだん速く空へかけ上がる(12コマずっと見える)。1コマ目は真ん中
SLEIGH05 = [(150, 54)] + [(78 + 10 * t + 0.7 * t * t, 74 - 2.0 * t) for t in range(11)]
RUN05 = [(206, 258), (228, 252), (223, 258), (218, 250), (216, 258), (210, 252), (206, 258), (206, 258), (206, 250),
         (206, 245), (206, 252), (206, 258)]
STAMPS = {
    "01": make("xmas", [("メリー", 44, True), ("クリスマス", 32, True)], "B",
               lambda i: [POSE01[i], happy, P(**MOVE01[i]), santa,
                          tree_page(120, 34, 222, WALK01[i], S01, i)],
               both(bells_travel, snowf(1)),
               m=dict(scale=S01, anchor=(132, 256)), x0=18),
    "05": make("xmas", [("おつかれ", 34, True), ("さまです", 30, False)], "A",
               lambda i: [S, happy, (lambda c, d=BOB05[i]: inko.move(c, list(c), dy=d)), P(**MOVE05[i]), reindeer,
                          tree_page(30, 70, 176, RUN05[i], S05, i, style="snow")],
               lambda i, av: winter.snow(5, 5, i, avoid=av)
               + ([("sleigh", SLEIGH05[i][0], SLEIGH05[i][1], 0.68, 12)] if SLEIGH05[i] else []),
               m=dict(scale=S05, anchor=(206, 258)), x0=18, y0=156),
}

for name, path in (("01", WALK01), ("05", RUN05)):
    for i, fr in enumerate(STAMPS[name]):
        fr["anchor"] = path[i]

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
