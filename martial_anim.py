#!/usr/bin/env python3
"""武闘家の「動くスタンプ」ジェネレーター.

魔法使い・戦士と同じ人形の仕組みに「脚」を加え、腕だけでなく脚も
腰から足先までをひざで曲げて描く (2 本の線をつなぐ簡単な IK)。
これでパンチだけでなく、ハイキック・回し蹴り・飛び蹴りなどの大きな動きができる。
拳や足先が大きく動いたコマには、その軌跡を白い筋で残す。

使い方:
    python3 martial_anim.py                     # martial_stamps.json から生成
"""

import argparse
import copy
import json
import math
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

import anim_stamps as an
import pixel_stamps as ps
import warrior_anim as wr
import wizard_anim as wz
from make_stamps import MAIN_SIZE, TAB_SIZE
from sprites import CHARACTERS, PALETTE

S, GW, GH, GROUND, WINDOW = wz.S, wz.GW, wz.GH, wz.GROUND, wz.WINDOW
CH = CHARACTERS["fighter"]
COLORS = {**PALETTE, **CH["colors"]}
WHITE, GOLD, PINK, CYAN = wz.WHITE, wz.GOLD, wz.PINK, wz.CYAN
PANTS, SHOE, SOLE = "#2A2A3A", "#15151F", "#E8E2D0"
TRAIL_DARK, TRAIL_LIGHT = "#C9B48A", "#FFF3D6"     # 拳・蹴りの軌跡 (風を切る白い筋)
BODY_H = len(CH["pixels"])                         # 上半身の絵の高さ (腰まで)
THIGH = SHIN = 5.5                                 # 脚の長さ (太もも・すね)
OWN_FX = ("impact", "fists", "tiles", "dizzy", "steam", "crack", "hit", "sparks", "glint", "cut", "slash")


def col(c):
    return ps.rgba(COLORS.get(c, c))


# --- 姿勢 --------------------------------------------------------------------
# 魔法使い・戦士と同じ項目に加えて
# hip    : 腰の高さ (地面からのドット数、普通は 10。下げると脚が曲がってしゃがむ)
# lf, rf : 左足・右足の位置 (足元からの相対ドット)。キックは足を高く遠くに置く
# lh, rh : 左右の拳の位置
IDLE = dict(x=24, y=0, tilt=0, squash=1.0, sx=1.0, bow=0, expr="normal", hip=10, ghost=(),
            lh=(-6, -18), rh=(6, -18), lf=(-4, 0), rf=(4, 0), fx=[])


def pose(**kw):
    p = copy.deepcopy(IDLE)
    p.update(kw)
    return p


lerp, tween, with_fx = wr.lerp, wr.tween, wr.with_fx


def stance(**kw):
    """構え: 腰を落とし、拳を顔の前に上げ、足を前後に開く。"""
    return pose(**{**dict(hip=9, lh=(-4, -15), rh=(7, -14), lf=(-5, 0), rf=(5, 0), expr="angry"), **kw})


# --- 体 ----------------------------------------------------------------------
_EL, _ER = 5, 10
FACES = {
    "normal":    [(_EL, 8, "E"), (_EL, 9, "E"), (_ER, 8, "E"), (_ER, 9, "E")],
    "smile":     [(_EL, 8, "E"), (_EL, 9, "E"), (_ER, 8, "E"), (_ER, 9, "E"), (7, 10, "R"), (8, 10, "R")],
    "calm":      [(4, 9, "E"), (5, 9, "E"), (10, 9, "E"), (11, 9, "E")],
    "sleep":     [(4, 9, "E"), (5, 9, "E"), (10, 9, "E"), (11, 9, "E"), (7, 10, "K")],
    "happy":     [(4, 9, "E"), (5, 8, "E"), (6, 9, "E"), (9, 9, "E"), (10, 8, "E"), (11, 9, "E"),
                  (7, 10, "R"), (8, 10, "R")],
    "wink":      [(_EL, 8, "E"), (_EL, 9, "E"), (10, 9, "E"), (11, 9, "E"), (7, 10, "R"), (8, 10, "R")],
    "surprised": [(_EL, 8, "E"), (_EL, 9, "E"), (_ER, 8, "E"), (_ER, 9, "E"), (7, 10, "K"), (8, 10, "K"),
                  (4, 7, "E"), (11, 7, "E")],
    "kira":      [(_EL, 8, "Y"), (_EL, 9, "Y"), (_ER, 8, "Y"), (_ER, 9, "Y"), (7, 10, "R"), (8, 10, "R")],
    "sad":       [(_EL, 9, "E"), (_ER, 9, "E"), (_EL, 10, "L"), (_ER, 10, "L"), (4, 7, "E"), (11, 7, "E")],
    "angry":     [(_EL, 8, "E"), (_EL, 9, "E"), (_ER, 8, "E"), (_ER, 9, "E"), (6, 7, "E"), (9, 7, "E"),
                  (7, 10, "K"), (8, 10, "K")],
    "shout":     [(_EL, 8, "E"), (_EL, 9, "E"), (_ER, 8, "E"), (_ER, 9, "E"), (6, 7, "E"), (9, 7, "E"),
                  (6, 10, "K"), (7, 10, "R"), (8, 10, "R"), (9, 10, "K")],
    "dizzy":     [(4, 8, "E"), (6, 8, "E"), (5, 9, "E"), (9, 8, "E"), (11, 8, "E"), (10, 9, "E"), (7, 10, "K")],
    "worry":     [(_EL, 9, "E"), (_ER, 9, "E"), (4, 7, "E"), (11, 7, "E")],
}


def fighter_sprite(expr):
    grid = [list(r) for r in CH["pixels"]]
    for x, y, c in FACES[expr]:
        grid[y][x] = c
    return ps.pixels_to_image(["".join(r) for r in grid], COLORS)


def body_image(p):
    img = fighter_sprite(p["expr"])
    bow = round(p["bow"])
    if bow:  # 頭 (髪〜あご) を下げて、おじぎ・うなずきに見せる
        head = img.crop((0, 0, img.width, 11))
        rest = img.crop((0, 11, img.width, img.height))
        img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        img.alpha_composite(rest, (0, 11))
        img.alpha_composite(head, (0, bow))
    w = max(2, round(img.width * abs(p["sx"])))
    h = max(4, round(img.height * p["squash"]))
    if (w, h) != img.size:
        img = img.resize((w, h), Image.NEAREST)
    if p["sx"] < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def lean_body(body, tilt):
    """体を傾ける。ドット絵を回転させると顔が崩れるので、頭・胸・腰の 3 つのかたまりを
    それぞれ横にずらして傾いて見せる (頭がいちばん大きくずれる)。"""
    tmp = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    h = body.height
    top = 45 - h
    k = -math.tan(math.radians(tilt))
    head_end, chest_end = round(h * 0.58), round(h * 0.82)
    for y0, y1 in ((0, head_end), (head_end, chest_end), (chest_end, h)):
        mid = h - (y0 + y1) / 2
        part = body.crop((0, y0, body.width, y1))
        tmp.alpha_composite(part, (24 - body.width // 2 + round(k * mid), top + y0))
    return tmp


def clamp(p):
    """頭が画面の上で切れないように、跳ぶ高さをおさえる。"""
    q = copy.deepcopy(p)
    q["y"] = max(q["y"], 2 + BODY_H * q["squash"] - GROUND + q["hip"])
    return q


def geometry(p):
    ax, ay = p["x"], GROUND + p["y"]
    hip = (ax, ay - p["hip"])
    flip = 1 if p["sx"] >= 0 else -1

    def upper(rel):  # 上半身についた点: 体の傾きに合わせて腰を中心に回す
        dx, dy = wz.rot((ax + rel[0] * flip) - hip[0], (ay + rel[1]) - hip[1], p["tilt"])
        return hip[0] + dx, hip[1] + dy

    shoulders = []
    for sx, sy in CH["shoulders"]:
        dx, dy = wz.rot((sx - 7.5) * abs(p["sx"]) * flip, (sy - (BODY_H - 1)) * p["squash"], p["tilt"])
        shoulders.append((hip[0] + dx, hip[1] + dy))
    hips = []
    for hx in (-2.5, 2.5):
        dx, dy = wz.rot(hx * abs(p["sx"]) * flip, 0, p["tilt"])
        hips.append((hip[0] + dx, hip[1] + dy))
    feet = {"l": (ax + p["lf"][0], ay + p["lf"][1]), "r": (ax + p["rf"][0], ay + p["rf"][1])}
    hands = {"l": upper(p["lh"]), "r": upper(p["rh"])}
    return dict(anchor=(ax, ay), hip=hip, shoulders=shoulders, hips=hips, hands=hands, feet=feet,
                orb=hands["r"])


def knee(hip, foot, center_x):
    """太ももとすねの長さから、ひざの位置を求める。足が近いほどひざが外へ曲がる。"""
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    d = math.hypot(dx, dy) or 0.01
    if d >= THIGH + SHIN:
        return ((hip[0] + foot[0]) / 2, (hip[1] + foot[1]) / 2)
    h = math.sqrt(max(0.0, THIGH ** 2 - (d / 2) ** 2))
    mx, my = (hip[0] + foot[0]) / 2, (hip[1] + foot[1]) / 2
    nx, ny = -dy / d, dx / d
    a, b = (mx + nx * h, my + ny * h), (mx - nx * h, my - ny * h)
    return a if abs(a[0] - center_x) > abs(b[0] - center_x) else b


# --- 武闘家用のエフェクト ----------------------------------------------------
def draw_own_fx(img, d, fx, g, phase):
    for e in fx:
        kind = e.get("type")
        if kind == "impact":  # 打撃の瞬間: 放射状の線と白い星
            x, y, r = e["x"], e["y"], e.get("r", 6)
            for i in range(10):
                a = 2 * math.pi * i / 10 + 0.15
                r0, r1 = r * 0.55, r * (1.0 if i % 2 == 0 else 0.8)
                d.line([(x + r0 * math.cos(a), y + r0 * math.sin(a)), (x + r1 * math.cos(a), y + r1 * math.sin(a))],
                       fill=col(WHITE if i % 2 == 0 else wr.SPARK_YELLOW))
            wr.draw_sword_fx(d, [{"type": "hit", "x": x, "y": y, "r": max(2, r * 0.45)}])
        elif kind == "fists":  # 連打の残像の拳
            for x, y in e["pts"]:
                x, y = round(x), round(y)
                d.rectangle([x - 2, y - 2, x + 2, y + 2], fill=col("#3A3A4A"))
                d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=col("#F2C9A0"))
        elif kind == "tiles":  # 瓦の山 (broken で真ん中から割れて飛ぶ)
            x, y, n, br = e["x"], e["y"], e.get("n", 4), e.get("broken", 0)
            for i in range(n):
                ty = y - i * 3
                for side in (-1, 1):
                    off = br * side * (1 + i * 0.5)
                    lift = -br * (i * 0.6)
                    x0 = x + (0 if side > 0 else -5) + off
                    d.rectangle([x0, ty - 2 + lift, x0 + 5, ty + lift], fill=col("#B9C0CE"), outline=col("#3A3F4E"))
                    d.line([(x0 + 1, ty - 1 + lift), (x0 + 4, ty - 1 + lift)], fill=col("#E4E8F0"))
            d.rectangle([x - 6, y + 1, x - 4, y + 3], fill=col("#9A927E"), outline=col("K"))
            d.rectangle([x + 4, y + 1, x + 6, y + 3], fill=col("#9A927E"), outline=col("K"))
        elif kind == "dizzy":  # 頭のまわりを回る星 (目が回る)
            hx, hy = g["hip"][0], g["hip"][1] - BODY_H - 1
            for i in range(3):
                a = 2 * math.pi * i / 3 + phase * 0.8
                x, y = hx + 7 * math.cos(a), hy + 2 * math.sin(a)
                d.point([(round(x), round(y)), (round(x) - 1, round(y)), (round(x) + 1, round(y)),
                         (round(x), round(y) - 1), (round(x), round(y) + 1)], fill=col(GOLD))
        elif kind == "steam":  # 頭から立ちのぼる湯気 (気合・疲れ)
            hx, hy = g["hip"][0], g["hip"][1] - BODY_H * 1.0
            for i, dx in enumerate((-4, 0, 4)):
                o = (phase + i) % 2
                pts = [(hx + dx + (1 if (k + o) % 2 else -1) * 0.8, hy - 2 - k * 2) for k in range(4)]
                d.line(pts, fill=col(e.get("color", WHITE)))
        elif kind == "crack":  # 地面のひび割れ
            x = e["x"]
            for s in (-1, 1):
                pts = [(x, GROUND - 1)] + [(x + s * (3 + 3 * k), GROUND - 1 + (k % 2)) for k in range(e.get("n", 3))]
                d.line(pts, fill=col("K"), width=1)
    wr.draw_sword_fx(d, [e for e in fx if e.get("type") in ("hit", "sparks", "glint", "cut")])


# --- 描画 --------------------------------------------------------------------
def draw_leg(d, hip, foot, center_x):
    k = knee(hip, foot, center_x)
    d.line([hip, k, foot], fill=col("K"), width=5, joint="curve")
    d.line([hip, k, foot], fill=col(PANTS), width=3, joint="curve")
    fx, fy = round(foot[0]), round(foot[1])
    side = 1 if foot[0] >= center_x else -1
    d.rectangle([min(fx, fx + side * 3) - 1, fy - 2, max(fx, fx + side * 3) + 1, fy + 1], fill=col("K"))
    d.rectangle([min(fx, fx + side * 3), fy - 1, max(fx, fx + side * 3), fy], fill=col(SHOE))
    d.point((fx + side * 2, fy), fill=col(SOLE))


def draw_arm(d, shoulder, hand):
    d.line([shoulder, hand], fill=col("K"), width=4)
    d.line([shoulder, hand], fill=col("S"), width=2)
    sleeve = (shoulder[0] + (hand[0] - shoulder[0]) * 0.4, shoulder[1] + (hand[1] - shoulder[1]) * 0.4)
    d.line([shoulder, sleeve], fill=col("C"), width=2)


def draw_fist(d, h):
    x, y = round(h[0]), round(h[1])
    d.rectangle([x - 2, y - 2, x + 2, y + 2], fill=col("K"))
    d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=col("S"))
    d.point((x - 1, y + 1), fill=col("W"))  # 手首のバンド


def render_grid(p, phase=0, trail=()):
    jumped = p["y"] <= -2
    p = clamp(p)
    gimg = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    d = ImageDraw.Draw(gimg)
    g = geometry(p)
    ax, ay = g["anchor"]
    wz.draw_fx(gimg, d, [e for e in p["fx"] if e.get("type") not in OWN_FX], g, phase, back=True)

    char = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))   # キャラ本体 (残像を作るため別の層に描く)
    cd = ImageDraw.Draw(char)
    for hp, fk in zip(g["hips"], ("l", "r")):
        draw_leg(cd, hp, g["feet"][fk], ax)
    char.alpha_composite(lean_body(body_image(p), p["tilt"]), (round(g["hip"][0]) - 24, round(g["hip"][1]) - 44))
    for sh, hk in zip(g["shoulders"], ("l", "r")):
        draw_arm(cd, sh, g["hands"][hk])
    for h in g["hands"].values():
        draw_fist(cd, h)

    for i, gdx in enumerate(p.get("ghost", ())):  # 残像: キャラの形を薄い色で後ろに残す
        sil = Image.new("RGBA", char.size, col(TRAIL_LIGHT)[:3] + (0,))
        sil.putalpha(char.getchannel("A").point(lambda v, k=i: (80 if k == 0 else 45) if v else 0))
        gimg.alpha_composite(sil, (round(gdx), 0))
    if len(trail) >= 2:
        pts = list(trail)
        colors = [TRAIL_DARK, TRAIL_LIGHT, WHITE]
        for i in range(len(pts) - 1):
            c = colors[max(0, len(colors) - (len(pts) - 1) + i)]
            d.line([pts[i], pts[i + 1]], fill=col(c), width=4 if i == len(pts) - 2 else 2)
    gimg.alpha_composite(char)

    if jumped:
        for dx in (-4, 0, 4):
            x = round(ax + dx)
            d.line([(x, round(ay) + 2), (x, min(GROUND - 1, round(ay) + 5))], fill=col(WHITE))
    wz.draw_fx(gimg, d, [e for e in p["fx"] if e.get("type") not in OWN_FX], g, phase, back=False)
    draw_own_fx(gimg, d, p["fx"], g, phase)
    return gimg


def render(p, text, style, phase=0, trail=(), sfx=()):
    img = Image.new("RGBA", (GW * S, GH * S), (0, 0, 0, 0))
    ps.draw_window(img, style)
    x0, y0, x1, y1 = WINDOW
    t = ps.pixel_text(text, style.get("text", "#FFFFFF"), style.get("shadow", "#0A0D3A"))
    k = max(1, min((x1 - x0 - 28) // t.width, (y1 - y0 - 24) // t.height, 3))
    t = ps.scaled(t, k)
    img.alpha_composite(t, ((x0 + x1 - t.width) // 2, (y0 + y1 - t.height) // 2 + 2))
    img.alpha_composite(ps.scaled(render_grid(p, phase, trail), S))
    for s in sfx:
        im = wz.sfx_image(s["text"], s.get("style", "impact"), s["k"])
        cx, cy = s["x"] * S + s["w"] // 2, s["y"] * S + s["h"] // 2
        img.alpha_composite(im, (max(0, min(GW * S - im.width, cx - im.width // 2)),
                                 max(0, min(WINDOW[1] - im.height, cy - im.height // 2))))
    return img


def limbs(p):
    g = geometry(clamp(p))
    return {"lh": g["hands"]["l"], "rh": g["hands"]["r"], "lf": g["feet"]["l"], "rf": g["feet"]["r"]}


def render_sequence(poses, text, style, item):
    """コマを順に描く。拳か足がいちばん大きく動いたら、その通り道に風を切る筋を残す。"""
    imgs, hist = [], []
    sfx = wz.frame_sfx(item, len(poses))
    for i, p in enumerate(poses):
        cur = limbs(p)
        trail = ()
        if i >= 2 and len(hist) >= 1 and hist[-1] is not None:
            prev = hist[-1]
            key = max(cur, key=lambda k: math.hypot(cur[k][0] - prev[k][0], cur[k][1] - prev[k][1]))
            if math.hypot(cur[key][0] - prev[key][0], cur[key][1] - prev[key][1]) > 5:
                pts = [h[key] for h in hist[-2:] if h is not None] + [cur[key]]
                trail = pts
        imgs.append(render(p, text, style, phase=i, trail=trail, sfx=sfx[i]))
        hist.append(cur if i >= 1 else None)
    return imgs


# --- エフェクトの部品 --------------------------------------------------------
spr, speed, puff, confetti = wz.spr, wz.speed, wz.puff, wz.confetti
dust, hit, sparks, cut = wr.dust, wr.hit, wr.sparks, wr.cut


def impact(x, y, r=6):
    return {"type": "impact", "x": x, "y": y, "r": r}


def fists(*pts):
    return {"type": "fists", "pts": list(pts)}


def tiles(x, y, n=4, broken=0):
    return {"type": "tiles", "x": x, "y": y, "n": n, "broken": broken}


def at_hand(p, side="r"):
    return geometry(clamp(p))["hands"][side]


def at_foot(p, side="r"):
    return geometry(clamp(p))["feet"][side]


DIZZY, STEAM = {"type": "dizzy"}, {"type": "steam"}


# --- 技 (よく使う姿勢) -------------------------------------------------------
def punch(side="r", **kw):
    """正拳突き: 腰を落として踏み込み、片方の拳をまっすぐ前へ伸ばす。"""
    if side == "r":
        base = dict(x=25, tilt=-8, hip=8, rh=(15, -17), lh=(-2, -16), lf=(-6, 0), rf=(6, 0), expr="shout")
    else:
        base = dict(x=23, tilt=8, hip=8, lh=(-15, -17), rh=(2, -16), lf=(-6, 0), rf=(6, 0), expr="shout")
    return pose(**{**base, **kw})


def high_kick(**kw):
    """右のハイキック: 軸足で立ち、右足を頭の高さまで蹴り上げる。体は後ろへ傾く。"""
    return pose(**{**dict(x=22, tilt=18, hip=10, lf=(-2, 0), rf=(16, -18), lh=(-9, -20), rh=(-2, -14),
                          expr="shout"), **kw})


def chamber(**kw):
    """蹴りの前の溜め: ひざを胸まで引き上げる。"""
    return pose(**{**dict(x=23, tilt=6, hip=10, lf=(-2, 0), rf=(5, -9), lh=(-6, -19), rh=(4, -20), expr="angry"), **kw})


def run(x, i, **kw):
    ph = i % 2
    return pose(x=x, y=-2 * ph, tilt=-14, hip=9, lf=(-7, -2) if ph else (5, 0), rf=(6, 0) if ph else (-6, -3),
                lh=(6, -19) if ph else (-6, -15), rh=(-6, -15) if ph else (7, -19), ghost=(-6, -12),
                fx=[speed(x - 14, GROUND - 16, n=3, length=6)] + ([puff(x)] if ph == 0 else []), **kw)


def spin(base, sxs=(0.5, -0.5, -1.0, -0.5, 0.5)):
    out = []
    for sx in sxs:
        q = copy.deepcopy(base)
        q["sx"] = sx
        out.append(q)
    return out


# --- 動き (24 種) ------------------------------------------------------------
def m_thanks():   # ありがとう!: 拳を手のひらで包む拳法の礼 → 深くおじぎ
    salute = pose(hip=10, lh=(-1, -16), rh=(1, -16), expr="calm", lf=(-3, 0), rf=(3, 0))
    final = pose(hip=10, bow=4, squash=0.88, lh=(-1, -14), rh=(1, -14), expr="calm", lf=(-3, 0), rf=(3, 0),
                 fx=[spr("sparkle", 44, 4)])
    seq = [final] + tween(stance(), 1, punch(), 1, stance(), 1, salute, 2, final) + [final] * 4
    return seq, an.split(3000, len(seq)), 1


def m_morning():  # おはよう!: シャドーボクシングでワン・ツー → 大きく伸び
    final = pose(hip=10, squash=1.1, lh=(-6, -28), rh=(6, -28), expr="happy", lf=(-3, 0), rf=(3, 0),
                 fx=[spr("sparkle", 46, 6)])
    seq = [final, stance(), punch("l", fx=[impact(9, 21, 4)]), stance(), punch("r", fx=[impact(39, 21, 5)]),
           stance(), lerp(stance(), final, 0.5), final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_ok():       # OK!: 溜めてから右のハイキック → 片足立ちでビシッ
    hk = high_kick()
    tip = at_foot(hk)
    final = high_kick(expr="wink", fx=[impact(tip[0] + 2, tip[1], 5)])
    seq = [final, stance(), chamber(), hk, with_fx(hk, impact(tip[0] + 2, tip[1], 8)), final, final, final]
    return seq, an.split(2000, len(seq)), 1


def m_roger():    # 了解!: 鋭い正拳突き! → 拳を胸に引いてビシッ
    p = punch()
    tip = at_hand(p)
    final = pose(hip=10, lh=(-1, -16), rh=(3, -17), expr="kira", lf=(-3, 0), rf=(3, 0), fx=[spr("exclaim", 44, 6)])
    seq = [final, stance(), pose(**{**stance(), "rh": (-2, -14), "tilt": 6}),
           with_fx(p, impact(tip[0] + 3, tip[1], 6), speed(4, 18, n=3, length=6)), with_fx(p, impact(tip[0] + 3, tip[1], 9)),
           stance(), final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_sorry():    # ごめん!: 正座して何度も深く頭を下げる (土下座)
    final = pose(hip=4, bow=6, squash=0.8, lh=(-3, -6), rh=(3, -6), lf=(-6, 0), rf=(6, 0), expr="sad",
                 fx=[spr("sweats", 34, 10), spr("sweat", 10, 12)])
    up = pose(hip=5, squash=1.0, lh=(-4, -11), rh=(4, -11), lf=(-6, 0), rf=(6, 0), expr="sad", fx=[spr("sweat", 34, 10)])
    seq = [final] + tween(final, 2, up, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_otsukare():  # おつかれ!: 稽古の最後の一撃 → 汗をぬぐい、頭から湯気
    p = punch()
    tip = at_hand(p)
    final = pose(hip=10, lh=(-6, -9), rh=(4, -24), expr="calm", lf=(-3, 0), rf=(3, 0),
                 fx=[STEAM, spr("sweat", 40, 8)])
    seq = [final, stance(), with_fx(p, impact(tip[0] + 3, tip[1], 7)), stance(),
           pose(hip=10, lh=(-6, -9), rh=(6, -20), expr="calm", fx=[STEAM]), final, final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_congrats():  # おめでとう!: 回転ジャンプからの飛び蹴り、紙吹雪
    air = pose(y=-5, hip=10, lf=(-3, -4), rf=(3, -4), lh=(-8, -20), rh=(8, -20), expr="happy", fx=[confetti(0)])
    fk = pose(y=-5, x=22, tilt=12, hip=10, lf=(-4, -5), rf=(16, -10), lh=(-9, -20), rh=(-2, -15), expr="shout",
              fx=[confetti(2)])
    tip = at_foot(fk)
    final = with_fx(fk, confetti(3), impact(tip[0] + 2, tip[1], 6))
    seq = [final, pose(hip=7, expr="smile", lh=(-6, -12), rh=(6, -12))] + spin(air, (0.5, -0.5, -1.0, -0.5)) + \
        [fk, final, pose(hip=7, expr="happy", fx=[dust(24, 12), puff(24), confetti(4)]), final]
    return seq, an.split(3000, len(seq)), 1


def m_goodnight():  # おやすみ: あぐらで瞑想していたら、こっくり → ハッ!
    final = pose(hip=4, bow=3, lh=(-3, -9), rh=(3, -9), lf=(-7, 0), rf=(7, 0), expr="sleep", fx=[spr("zzz", 40, 8)])
    awake = pose(hip=5, squash=1.05, lh=(-6, -14), rh=(6, -14), lf=(-7, 0), rf=(7, 0), expr="surprised",
                 fx=[spr("exclaim", 42, 10)])
    seq = [final] + tween(final, 3, awake, 1, awake, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_ittekimasu():  # いってきます!: 拳を突き上げてから、全速力で走っていく
    final = pose(hip=10, lh=(-6, -12), rh=(3, -29), expr="happy", lf=(-3, 0), rf=(3, 0), fx=[spr("note", 44, 6)])
    seq = [final, stance(expr="smile"), final] + [run(26 + 8 * i, i, expr="angry") for i in range(1, 6)] + \
        [run(-6 + 8 * i, i, expr="angry") for i in range(1, 4)] + [stance(expr="happy"), final]
    return seq, an.split(4000, len(seq)), 1


def m_tadaima():  # ただいま!: 宙返りしながら飛びこんで、シュタッと着地して構える
    final = stance(expr="happy", fx=[dust(24, 10), spr("note", 46, 6)])
    seq = [final]
    for i, (x, y, sx) in enumerate([(4, -4, 1.0), (10, -6, 0.5), (15, -6, -0.5), (20, -4, -1.0)]):
        seq.append(pose(x=x, y=y, sx=sx, hip=8, lf=(-3, -5), rf=(3, -5), lh=(-4, -12), rh=(4, -12), expr="happy",
                        ghost=(-5,)))
    seq += [pose(hip=6, expr="angry", lh=(-8, -14), rh=(8, -14), lf=(-7, 0), rf=(7, 0), fx=[dust(24, 14), puff(24)]),
            final, final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_osu():      # 押忍!: 両腕を顔の前で交差させ、気合とともに振り下ろす
    cross = pose(hip=9, lh=(3, -21), rh=(-3, -21), expr="shout", lf=(-5, 0), rf=(5, 0))
    final = pose(hip=9, lh=(-8, -10), rh=(8, -10), expr="shout", lf=(-5, 0), rf=(5, 0),
                 fx=[impact(15, 28, 5), impact(33, 28, 5), dust(24, 12)])
    seq = [final, stance(), cross, cross, final,
           with_fx(final, impact(15, 28, 8), impact(33, 28, 8), dust(24, 16)), final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_ganbare():  # がんばれ!: 目にも止まらぬ連続パンチ (拳の残像)
    a = punch("r", fx=[fists((40, 16), (38, 22), (41, 26)), speed(54, 14, left=False)])
    b = punch("l", fx=[fists((9, 16), (11, 22), (7, 26)), speed(2, 14, left=True)])
    ta, tb = at_hand(a, "r"), at_hand(b, "l")
    seq = [with_fx(a, *a["fx"], impact(ta[0] + 2, ta[1], 5)), b, a, with_fx(b, *b["fx"], impact(tb[0] - 2, tb[1], 5))]
    return seq + [stance(expr="shout")], an.split(1000, 5), 3


def m_sugoi():    # すごい!: 手刀で瓦を一撃で割る
    top = pose(x=20, hip=9, lh=(-6, -14), rh=(6, -28), expr="shout", lf=(-5, 0), rf=(5, 0), fx=[tiles(38, 34, 4)])
    chop = pose(x=22, tilt=-12, hip=7, lh=(-6, -14), rh=(15, -10), expr="shout", lf=(-6, 0), rf=(5, 0),
                fx=[tiles(38, 34, 4, broken=1), impact(38, 24, 8)])
    final = with_fx(chop, tiles(38, 34, 4, broken=2), spr("exclaim", 50, 4), dust(38, 10))
    seq = [final, pose(x=20, hip=10, expr="normal", fx=[tiles(38, 34, 4)]), top, top, chop, final,
           with_fx(final, tiles(38, 34, 4, broken=3), spr("exclaim", 50, 4), dust(38, 14), puff(38)), final, final]
    return seq, an.split(3000, len(seq)), 1


def m_iine():     # いいね!: 回し蹴りを決めてウインク
    hk = high_kick(rf=(17, -14))
    tip = at_foot(hk)
    final = high_kick(rf=(17, -14), expr="wink", fx=[impact(tip[0] + 2, tip[1], 5)])
    seq = [final, stance(), chamber(sx=0.6), chamber(sx=-0.6), hk, with_fx(hk, impact(tip[0] + 2, tip[1], 9)),
           final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_sorena():   # それな!: こっちへ向かって一直線のストレート
    p = punch(rh=(16, -19))
    tip = at_hand(p)
    final = with_fx(p, impact(tip[0] + 3, tip[1], 8), spr("exclaim", 52, 2))
    seq = [final, stance(), pose(**{**stance(), "rh": (-3, -15), "tilt": 8, "x": 22}), with_fx(p, speed(4, 20, n=3, length=6)),
           final, final]
    return seq, an.split(2000, len(seq)), 1


def m_wakaru():   # わかる〜: 腕を組んで、深くうなずく
    arms = dict(lh=(3, -14), rh=(-3, -14), lf=(-4, 0), rf=(4, 0))
    final = pose(hip=10, bow=3, expr="calm", **arms, fx=[spr("note", 44, 6)])
    up = pose(hip=10, expr="calm", **arms)
    seq = [final] + tween(up, 2, final, 2, up, 2, final)[1:]
    return seq, an.split(2000, len(seq)), 2


def m_nandeyanen():  # なんでやねん!: 横向きにツッコミの手刀 (裏拳)
    p = pose(x=22, tilt=-14, hip=9, lh=(-5, -15), rh=(17, -16), expr="shout", lf=(-5, 0), rf=(6, 0))
    tip = at_hand(p)
    final = with_fx(p, impact(tip[0] + 3, tip[1], 7), speed(4, 16, n=3, length=6))
    seq = [final, stance(expr="normal"), pose(x=22, tilt=10, hip=9, lh=(-5, -15), rh=(-6, -20), expr="shout"),
           with_fx(p, impact(tip[0] + 3, tip[1], 5)), final, final, final]
    return seq, an.split(2000, len(seq)), 1


def m_muri():     # もうムリ…: ふらふらして倒れ、目を回す (KO)
    final = pose(x=24, hip=3, tilt=0, bow=3, squash=0.85, lh=(-8, -2), rh=(8, -2), lf=(-9, 0), rf=(9, 0), expr="dizzy",
                 fx=[DIZZY, spr("sweats", 36, 14)])
    wob = [pose(tilt=t, hip=9, lh=(-7, -10), rh=(7, -10), expr="dizzy", fx=[DIZZY]) for t in (12, -12, 10)]
    seq = [final] + wob + [pose(tilt=-6, hip=6, lh=(-8, -6), rh=(8, -6), expr="dizzy", lf=(-7, 0), rf=(7, 0), fx=[DIZZY]),
                           with_fx(final, DIZZY, puff(24)), final, final]
    return seq, an.split(3000, len(seq)), 1


def m_ureshii():  # うれしい!: 両拳を突き上げて、何度も跳びはねる
    up = pose(y=-6, hip=10, lh=(-6, -29), rh=(6, -29), lf=(-3, -2), rf=(3, -2), expr="happy",
              fx=[spr("note", 44, 6), spr("heart", 4, 8)])
    dn = pose(hip=7, lh=(-6, -18), rh=(6, -18), lf=(-6, 0), rf=(6, 0), expr="happy", fx=[spr("note", 44, 10)])
    seq = [up, lerp(up, dn, 0.5), dn, lerp(dn, up, 0.5)]
    return seq + [up], an.split(1000, 5), 3


def m_shock():    # ショック…: 見えない一撃を受けたように吹っ飛ばされ、ひざから崩れる
    final = pose(hip=5, bow=2, lh=(-5, -6), rh=(5, -6), lf=(-6, 0), rf=(6, 0), expr="sad", fx=[spr("sweats", 34, 10)])
    hit_p = pose(x=20, tilt=22, hip=9, lh=(-12, -20), rh=(2, -24), lf=(-6, 0), rf=(4, -3), expr="surprised",
                 fx=[impact(34, 16, 8)])
    seq = [final, stance(expr="normal"), hit_p, pose(x=16, tilt=26, hip=8, lh=(-12, -20), rh=(2, -24), expr="surprised"),
           lerp(hit_p, final, 0.5), final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_makasero():  # 任せろ!: 胸をドンと叩いてから、拳を前に突き出す
    p = punch(expr="kira")
    tip = at_hand(p)
    final = with_fx(p, impact(tip[0] + 3, tip[1], 6), spr("exclaim", 50, 4))
    thump = pose(hip=10, lh=(-6, -14), rh=(-1, -15), expr="angry", fx=[impact(22, 22, 4)])
    seq = [final, stance(), thump, stance(), thump, p, final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_kakattekoi():  # かかってこい!: 構えたまま、指先でクイクイと手招き
    a = stance(rh=(12, -18), expr="angry", fx=[speed(50, 14, n=2, length=4, left=False)])
    b = stance(rh=(10, -21), expr="angry")
    seq = [a, b, a, b]
    return seq + [a], an.split(1000, 5), 2


def m_yoroshiku():  # よろしく!: 前蹴りを見せてから、拳法の礼でおじぎ
    fk = pose(x=22, tilt=10, hip=10, lf=(-2, 0), rf=(15, -9), lh=(-6, -19), rh=(4, -19), expr="shout")
    tip = at_foot(fk)
    final = pose(hip=10, bow=4, squash=0.88, lh=(-1, -14), rh=(1, -14), expr="calm", lf=(-3, 0), rf=(3, 0),
                 fx=[spr("sparkle", 44, 4)])
    seq = [final, stance(), chamber(), with_fx(fk, impact(tip[0] + 2, tip[1], 6)), stance(), lerp(stance(), final, 0.5),
           final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_kiai():     # 気合だ!: 腰を落として力をため、全身から気合を放つ (地面にひび)
    crouch = pose(hip=6, lh=(-9, -12), rh=(9, -12), lf=(-8, 0), rf=(8, 0), expr="angry", fx=[STEAM])
    final = pose(hip=8, lh=(-12, -18), rh=(12, -18), lf=(-8, 0), rf=(8, 0), expr="shout",
                 fx=[STEAM, {"type": "crack", "x": 24, "n": 4}, dust(24, 16), speed(6, 8, n=3, length=5),
                     speed(56, 8, n=3, length=5, left=False)])
    shake1, shake2 = copy.deepcopy(final), copy.deepcopy(final)
    shake1["x"], shake2["x"] = 23, 25
    seq = [final, stance(), crouch, crouch, final, shake1, shake2, final, final]
    return seq, an.split(3000, len(seq)), 1


MOTIONS = {
    "thanks": m_thanks, "morning": m_morning, "ok": m_ok, "roger": m_roger, "sorry": m_sorry,
    "otsukare": m_otsukare, "congrats": m_congrats, "goodnight": m_goodnight, "ittekimasu": m_ittekimasu,
    "tadaima": m_tadaima, "osu": m_osu, "ganbare": m_ganbare, "sugoi": m_sugoi, "iine": m_iine,
    "sorena": m_sorena, "wakaru": m_wakaru, "nandeyanen": m_nandeyanen, "muri": m_muri, "ureshii": m_ureshii,
    "shock": m_shock, "makasero": m_makasero, "kakattekoi": m_kakattekoi, "yoroshiku": m_yoroshiku, "kiai": m_kiai,
}


# --- 書き出し ----------------------------------------------------------------
def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = cfg_path.parent / cfg.get("output", "output_martial")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    style = cfg.get("window", {})

    problems, all_frames = [], []
    for i, item in enumerate(cfg["stamps"], 1):
        poses, ms, loops = MOTIONS[item["motion"]]()
        if len(poses) > 20:
            raise SystemExit(f"{item['motion']}: フレーム数 {len(poses)} が 20 を超えています")
        imgs = render_sequence(poses, item["text"], style, item)
        path = out / f"{i:02d}.png"
        an.save_apng(imgs, ms, loops, path)
        all_frames.append((imgs, ms, loops))
        info, errs = an.check_anim(path, "stamp")
        problems += [f"{path.name}: {e}" for e in errs]
        print(f"  {path.name}  {item['motion']:<10} {info['frames']:>2}f {info['ms'] * info['loops']:>4}ms "
              f"{info['bytes'] // 1024:>3}KB  {item['text']!r}")

    # メイン画像 (240x240): 構えて、ときどきまばたき
    grids = [render_grid(stance(expr=e), phase=j) for j, e in enumerate(["angry"] * 5 + ["calm"] + ["angry"] * 4)]
    box = (8, 4, 42, GROUND + 2)
    k = min((MAIN_SIZE[0] - 20) // (box[2] - box[0]), (MAIN_SIZE[1] - 20) // (box[3] - box[1]))
    mains = []
    for g in grids:
        big = ps.scaled(g.crop(box), k)
        canvas = Image.new("RGBA", MAIN_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(big, ((MAIN_SIZE[0] - big.width) // 2, (MAIN_SIZE[1] - big.height) // 2))
        mains.append(canvas)
    an.save_apng(mains, an.split(2000, len(mains)), 2, out / "main.png")
    problems += [f"main.png: {e}" for e in an.check_anim(out / "main.png", "main")[1]]
    ps.fit_square(render_grid(stance(expr="smile")), TAB_SIZE, 2).save(out / "tab.png")

    an.make_preview_gif(all_frames, cfg_path.parent / cfg.get("preview", "preview_martial.gif"))
    zip_path = cfg_path.parent / f"{cfg.get('name', 'martial_anim_stamp')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.glob("[0-9][0-9].png")) + [out / "main.png", out / "tab.png"]:
            z.write(p, p.name)
    if problems:
        print("\n❌ 仕様チェックで問題が見つかりました:")
        for p in problems:
            print("  -", p)
    else:
        print("\n✔ 仕様チェック OK (サイズ・フレーム数・再生時間・ループ・300KB以下・個数)")
    print(f"\n✅ 出力: {out}/  提出用 ZIP: {zip_path}")


def main():
    ap = argparse.ArgumentParser(description="武闘家の動くスタンプ")
    ap.add_argument("-c", "--config", default="martial_stamps.json")
    build(ap.parse_args().config)


if __name__ == "__main__":
    main()
