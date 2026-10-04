#!/usr/bin/env python3
"""剣と盾の戦士の「動くスタンプ」ジェネレーター.

魔法使い (wizard_anim.py) と同じ仕組みで、戦士を 体 / 腕 / 剣 / 盾 の部品に分けた
ドット絵の人形として描き、コマごとに姿勢と剣・盾の角度を変えて全身で大きく動かす。
剣を振ると刃先が斬撃の軌跡を残し、盾は向きを変えたり前に構えたりできる。
魔法陣・稲妻・衝撃波・擬音 (音の代わりの文字) などは wizard_anim.py の部品を使う。

使い方:
    python3 warrior_anim.py                     # warrior_stamps.json から生成
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
import wizard_anim as wz
from make_stamps import MAIN_SIZE, TAB_SIZE
from sprites import CHARACTERS, PALETTE

S, GW, GH, GROUND, WINDOW = wz.S, wz.GW, wz.GH, wz.GROUND, wz.WINDOW
CH = CHARACTERS["warrior"]
COLORS = {**PALETTE, **CH["colors"]}
CYAN, VIOLET, PINK, GOLD, WHITE = wz.CYAN, wz.VIOLET, wz.PINK, wz.GOLD, wz.WHITE
BLADE, BLADE_EDGE, GRIP = "#EEF3FB", "#9AA7BD", "#6B4226"
SCABBARD = "#5A3A22"
STEEL, STEEL_LIGHT = "#6F8DBA", "#CFDDF2"          # 斬撃・残像の鋼色
SPARK_ORANGE, SPARK_YELLOW = "#FF9A3C", "#FFE14D"  # 金属の火花
OWN_FX = ("slash", "cut", "sparks", "glint", "hit")
SHIELD_FIELD = "#C0343F"
BLADE_LEN = 13

SHIELD = [
    "KKKKKKKKK",
    "KYYYYYYYK",
    "KYFFFFFYK",
    "KYFFYFFYK",
    "KYFYYYFYK",
    "KYFFYFFYK",
    "KYFFFFFYK",
    ".KYFFFYK.",
    "..KYFYK..",
    "...KYK...",
    "....K....",
]


def col(c):
    return ps.rgba(COLORS.get(c, c))


# --- 姿勢 --------------------------------------------------------------------
# 魔法使いと同じ項目 (x, y, tilt, squash, sx, bow, lh, rh, expr, fx) に加えて
# sword  : 剣。ang は刃の向き (0 が真上、プラスで右)、glow で刃がきらめく。free=True で手を離れて (gx, gy) に飛ぶ
# shield : 盾。ang は傾き、w は横幅 (1.0 が正面、小さいほど横向き)、front=False で体の後ろ、
#          free=True で手を離れて (gx, gy) に置かれる
IDLE = dict(x=24, y=0, tilt=0, squash=1.0, sx=1.0, bow=0, expr="normal", ghost=(),
            lh=(-7, -11), rh=(9, -11), sword=dict(ang=25, glow=False),
            shield=dict(ang=0, w=1.0, front=True), fx=[])


def pose(**kw):
    p = copy.deepcopy(IDLE)
    for key in ("sword", "shield"):
        if key in kw:
            v = kw.pop(key)
            p[key] = v if v.get("free") else {**IDLE[key], **v}
    p.update(kw)
    return p


def lerp(a, b, t):
    """2 つの姿勢の間を t で補間する (剣・盾の中身も補間)。表情とエフェクトは後半で切り替える。"""
    def mix(u, v):
        if isinstance(u, bool) or isinstance(v, bool) or u is None or v is None:
            return v if t >= 0.5 else u
        if isinstance(u, (int, float)) and isinstance(v, (int, float)):
            return u + (v - u) * t
        if isinstance(u, tuple) and isinstance(v, tuple):
            return tuple(mix(x, y) for x, y in zip(u, v))
        if isinstance(u, dict) and isinstance(v, dict):
            if u.get("free") != v.get("free"):
                return v if t >= 0.5 else u
            return {k: mix(u.get(k, v[k]), v[k]) for k in v}
        return v if t >= 0.5 else u
    p = {k: mix(a[k], b[k]) for k in a if k != "fx"}
    p["fx"] = b["fx"] if t >= 0.5 else a["fx"]
    return p


def tween(*keys):
    out = []
    for i in range(0, len(keys) - 1, 2):
        a, n, b = keys[i], keys[i + 1], keys[i + 2]
        for j in range(n):
            out.append(lerp(a, b, j / n))
    out.append(keys[-1])
    return out


def with_fx(p, *fx):
    q = copy.deepcopy(p)
    q["fx"] = list(fx)
    return q


# --- 体 ----------------------------------------------------------------------
_EL, _ER = 5, 10  # 兜の目元の開いた部分 (10〜11 行目) に目を描く
FACES = {
    "normal":    [(_EL, 10, "E"), (_EL, 11, "E"), (_ER, 10, "E"), (_ER, 11, "E")],
    "smile":     [(_EL, 10, "E"), (_EL, 11, "E"), (_ER, 10, "E"), (_ER, 11, "E"), (7, 13, "R"), (8, 13, "R")],
    "calm":      [(4, 11, "E"), (5, 11, "E"), (10, 11, "E"), (11, 11, "E")],
    "sleep":     [(4, 11, "E"), (5, 11, "E"), (10, 11, "E"), (11, 11, "E"), (7, 13, "K")],
    "happy":     [(4, 11, "E"), (5, 10, "E"), (6, 11, "E"), (9, 11, "E"), (10, 10, "E"), (11, 11, "E"),
                  (7, 13, "R"), (8, 13, "R")],
    "wink":      [(_EL, 10, "E"), (_EL, 11, "E"), (10, 11, "E"), (11, 11, "E"), (7, 13, "R"), (8, 13, "R")],
    "surprised": [(_EL, 10, "E"), (_EL, 11, "E"), (_ER, 10, "E"), (_ER, 11, "E"), (4, 10, "W"), (11, 10, "W"),
                  (7, 13, "K"), (8, 13, "K")],
    "kira":      [(_EL, 10, "Y"), (_EL, 11, "Y"), (_ER, 10, "Y"), (_ER, 11, "Y"), (7, 13, "R"), (8, 13, "R")],
    "sad":       [(_EL, 11, "E"), (_ER, 11, "E"), (_EL, 12, "L"), (_ER, 12, "L")],
    "angry":     [(_EL, 11, "E"), (_ER, 11, "E"), (6, 10, "E"), (9, 10, "E"), (7, 13, "K"), (8, 13, "K")],
    "worry":     [(_EL, 11, "E"), (_ER, 11, "E"), (4, 10, "E"), (11, 10, "E")],
    "love":      [(_EL, 10, "R"), (_EL, 11, "R"), (_ER, 10, "R"), (_ER, 11, "R"), (7, 13, "R"), (8, 13, "R")],
}


def warrior_sprite(expr):
    grid = [list(r) for r in CH["pixels"]]
    for x, y, c in FACES[expr]:
        grid[y][x] = c
    return ps.pixels_to_image(["".join(r) for r in grid], COLORS)


def body_image(p):
    img = warrior_sprite(p["expr"])
    bow = round(p["bow"])
    if bow:  # かぶとを前に深く下げて顔を隠し、おじぎや うなずき に見せる
        head = img.crop((0, 0, img.width, 10))
        rest = img.crop((0, 10, img.width, img.height))
        img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        img.alpha_composite(rest, (0, 10))
        img.alpha_composite(head, (0, bow))
    w = max(2, round(img.width * abs(p["sx"])))
    h = max(4, round(img.height * p["squash"]))
    if (w, h) != img.size:
        img = img.resize((w, h), Image.NEAREST)
    if p["sx"] < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def geometry(p):
    ax, ay = p["x"], GROUND + p["y"]

    def world(rel):
        dx, dy = wz.rot(rel[0] * (1 if p["sx"] >= 0 else -1), rel[1], p["tilt"])
        return ax + dx, ay + dy

    shoulders = [world(((sx - 8) * abs(p["sx"]), (sy - 28) * p["squash"])) for sx, sy in CH["shoulders"]]
    hands = {"l": world(p["lh"]), "r": world(p["rh"])}
    sw = p["sword"]
    grip = (sw["gx"], sw["gy"]) if sw.get("free") else hands["r"]
    ux, uy = math.sin(math.radians(sw["ang"])), -math.cos(math.radians(sw["ang"]))
    tip = (grip[0] + ux * (BLADE_LEN + 1.5), grip[1] + uy * (BLADE_LEN + 1.5))
    return dict(anchor=(ax, ay), shoulders=shoulders, hands=hands, grip=grip, u=(ux, uy), orb=tip, tip=tip)


def clamp(p):
    q = copy.deepcopy(p)
    q["y"] = max(q["y"], -(GROUND - 2 - 28 * q["squash"]))
    return q


# --- 剣と盾 ------------------------------------------------------------------
def draw_sword(d, g, glow, phase, sheathed=False):
    (hx, hy), (ux, uy) = g["grip"], g["u"]
    nx, ny = -uy, ux
    guard = (hx + ux * 1.5, hy + uy * 1.5)
    tip = g["tip"]
    if sheathed:  # 鞘に収まった剣: 刃の代わりに茶色の鞘と、先の金具
        d.line([guard, tip], fill=col("K"), width=4)
        d.line([guard, (tip[0] - ux, tip[1] - uy)], fill=col(SCABBARD), width=2)
        d.point((round(tip[0] - ux), round(tip[1] - uy)), fill=col("Y"))
    else:  # 刃: 輪郭 → 白い刃 → 刃の影の筋
        d.line([guard, tip], fill=col("K"), width=4)
        d.line([guard, (tip[0] - ux, tip[1] - uy)], fill=col(BLADE), width=2)
        d.line([(guard[0] + nx * 0.6, guard[1] + ny * 0.6), (tip[0] - ux * 2 + nx * 0.6, tip[1] - uy * 2 + ny * 0.6)],
               fill=col(BLADE_EDGE), width=1)
    # つば (金) と柄・柄頭
    a, b = (guard[0] - nx * 3, guard[1] - ny * 3), (guard[0] + nx * 3, guard[1] + ny * 3)
    d.line([a, b], fill=col("K"), width=3)
    d.line([a, b], fill=col("Y"), width=1)
    pa, pb = (hx - ux * 0.5, hy - uy * 0.5), (hx - ux * 3, hy - uy * 3)
    d.line([pa, pb], fill=col("K"), width=3)
    d.line([pa, pb], fill=col(GRIP), width=1)
    d.point((round(hx - ux * 3.5), round(hy - uy * 3.5)), fill=col("Y"))
    if glow and not sheathed:  # 刃のきらめき: 刃の上を白い光が走る
        f = 0.25 + 0.6 * ((phase % 4) / 3)
        gx, gy = guard[0] + (tip[0] - guard[0]) * f, guard[1] + (tip[1] - guard[1]) * f
        d.point([(round(gx), round(gy)), (round(gx + ux), round(gy + uy))], fill=col(WHITE))


def shield_image(sh):
    img = ps.pixels_to_image(SHIELD, {**COLORS, "F": SHIELD_FIELD})
    w = max(2, round(img.width * sh.get("w", 1.0)))
    if w != img.width:
        img = img.resize((w, img.height), Image.NEAREST)
    if sh.get("ang"):
        img = img.rotate(sh["ang"], resample=Image.NEAREST, expand=True)
    return img


def draw_shield(gimg, p, g):
    sh = p["shield"]
    img = shield_image(sh)
    cx, cy = (sh["gx"], sh["gy"]) if sh.get("free") else (g["hands"]["l"][0] - 1, g["hands"]["l"][1] + 1)
    gimg.alpha_composite(img, (round(cx - img.width / 2), round(cy - img.height / 2)))


def draw_slash(d, e):
    """太い三日月形の斬撃 (白 → 薄い鋼色 → 鋼色の 3 層)。"""
    cx, cy, r, a0, a1 = e["cx"], e["cy"], e["r"], e["a0"], e["a1"]
    for rr, c, w in ((r, WHITE, 2), (r - 1.5, STEEL_LIGHT, 2), (r - 3, STEEL, 1)):
        d.line(wz.arc_pts(cx, cy, rr, a0, a1, 12), fill=col(c), width=w)


def draw_trail(d, tips):
    """剣を振ったときの刃先の跡 (古いほど暗い鋼色、最新は太い白)。"""
    colors = [STEEL, STEEL_LIGHT, WHITE]
    for i in range(len(tips) - 1):
        c = colors[max(0, len(colors) - (len(tips) - 1) + i)]
        d.line([tips[i], tips[i + 1]], fill=col(c), width=4 if i == len(tips) - 2 else 2)


def draw_sword_fx(d, fx):
    """剣士用のエフェクト: 斬り跡の線・金属の火花・刃のきらめき・打撃の星。"""
    for e in fx:
        kind = e.get("type")
        if kind == "cut":  # まっすぐな斬り跡
            a, b = (e["x0"], e["y0"]), (e["x1"], e["y1"])
            d.line([a, b], fill=col(STEEL), width=4)
            d.line([a, b], fill=col(WHITE), width=2)
        elif kind == "sparks":  # 金属がぶつかった火花 (オレンジと黄色の短い線)
            x, y, r = e["x"], e["y"], e["r"]
            for i in range(8):
                a = 2 * math.pi * i / 8 + (0.3 if i % 2 else 0)
                r0, r1 = r * 0.35, r * (1.0 if i % 2 == 0 else 0.7)
                d.line([(x + r0 * math.cos(a), y + r0 * math.sin(a)), (x + r1 * math.cos(a), y + r1 * math.sin(a))],
                       fill=col(SPARK_ORANGE if i % 2 else SPARK_YELLOW))
        elif kind == "glint":  # 刃のきらめき (白い 4 本の光)
            x, y, s = round(e["x"]), round(e["y"]), e.get("s", 3)
            d.line([(x - s, y), (x + s, y)], fill=col(WHITE))
            d.line([(x, y - s - 1), (x, y + s + 1)], fill=col(WHITE))
            d.point([(x - 1, y - 1), (x + 1, y + 1), (x + 1, y - 1), (x - 1, y + 1)], fill=col(STEEL_LIGHT))
        elif kind == "hit":  # 打撃の星 (白い星にオレンジの縁)
            x, y, r = e["x"], e["y"], e.get("r", 4)
            pts = [(x + (r if i % 2 == 0 else r / 2.2) * math.cos(math.pi * i / 4),
                    y + (r if i % 2 == 0 else r / 2.2) * math.sin(math.pi * i / 4)) for i in range(8)]
            d.polygon(pts, fill=col(WHITE), outline=col(SPARK_ORANGE))


def render_grid(p, phase=0, trail=()):
    jumped = p["y"] <= -2
    p = clamp(p)
    gimg = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    d = ImageDraw.Draw(gimg)
    g = geometry(p)
    ax, ay = g["anchor"]
    wz.draw_fx(gimg, d, [e for e in p["fx"] if e.get("type") not in OWN_FX], g, phase, back=True)
    if not p["shield"].get("front") and not p["shield"].get("free"):
        draw_shield(gimg, p, g)
    if p["shield"].get("free"):
        draw_shield(gimg, p, g)

    body = body_image(p)
    tmp = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    tmp.alpha_composite(body, (24 - body.width // 2, 44 - body.height))
    if p["tilt"]:
        tmp = tmp.rotate(p["tilt"], resample=Image.NEAREST, center=(24, 44))
    for i, gdx in enumerate(p.get("ghost", ())):  # 残像: 体の形を薄い鋼色で後ろに残す
        sil = Image.new("RGBA", tmp.size, col(STEEL_LIGHT)[:3] + (0,))
        sil.putalpha(tmp.getchannel("A").point(lambda v, k=i: (70 if k == 0 else 40) if v else 0))
        gimg.alpha_composite(sil, (round(ax + gdx) - 24, round(ay) - 44))
    gimg.alpha_composite(tmp, (round(ax) - 24, round(ay) - 44))

    if len(trail) >= 2:
        draw_trail(d, list(trail) + [g["tip"]])
    for e in p["fx"]:
        if e.get("type") == "slash":
            draw_slash(d, e)
    # 剣は別の層に描き、地面より下は消す (地面に突き立てた剣が文字のウィンドウに刺さらないように)
    layer = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    draw_sword(ImageDraw.Draw(layer), g, p["sword"].get("glow"), phase, p["sword"].get("sheathed", False))
    layer.paste((0, 0, 0, 0), (0, GROUND, GW, GH))
    gimg.alpha_composite(layer)
    for sh, hk in zip(g["shoulders"], ("l", "r")):
        d.line([sh, g["hands"][hk]], fill=col("K"), width=4)
        d.line([sh, g["hands"][hk]], fill=col("G"), width=2)
    for h in g["hands"].values():
        hx, hy = round(h[0]), round(h[1])
        d.rectangle([hx - 1, hy - 1, hx + 2, hy + 2], fill=col("K"))
    for h in g["hands"].values():
        hx, hy = round(h[0]), round(h[1])
        d.rectangle([hx, hy, hx + 1, hy + 1], fill=col("g"))
    if p["shield"].get("front") and not p["shield"].get("free"):
        draw_shield(gimg, p, g)
    if jumped:
        for dx in (-4, 0, 4):
            x = round(ax + dx)
            d.line([(x, round(ay) + 2), (x, min(GROUND - 1, round(ay) + 5))], fill=col(WHITE))
    wz.draw_fx(gimg, d, [e for e in p["fx"] if e.get("type") not in OWN_FX], g, phase, back=False)
    draw_sword_fx(d, p["fx"])
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


def render_sequence(poses, text, style, item):
    """コマを順に描く。剣が大きく動いたコマには、直前の刃先の位置から斬撃の軌跡を付ける。"""
    imgs, tips = [], []
    sfx = wz.frame_sfx(item, len(poses))
    for i, p in enumerate(poses):
        tip = geometry(clamp(p))["tip"]
        trail = ()
        if i >= 2 and not p["sword"].get("free"):
            prev = [t for t in tips[-2:] if t is not None]
            if prev and math.hypot(tip[0] - prev[-1][0], tip[1] - prev[-1][1]) > 4:
                trail = prev
        imgs.append(render(p, text, style, phase=i, trail=trail, sfx=sfx[i]))
        tips.append(tip if i >= 1 else None)
    return imgs


# --- エフェクトの部品 --------------------------------------------------------
spr, speed, puff, confetti = wz.spr, wz.speed, wz.puff, wz.confetti


def slash(cx, cy, r, a0, a1):
    return {"type": "slash", "cx": cx, "cy": cy, "r": r, "a0": a0, "a1": a1}


def cut(x0, y0, x1, y1):
    return {"type": "cut", "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def sparks(x, y, r=5):
    return {"type": "sparks", "x": x, "y": y, "r": r}


def glint(x, y, s=3):
    return {"type": "glint", "x": x, "y": y, "s": s}


def hit(x, y, r=4):
    return {"type": "hit", "x": x, "y": y, "r": r}


def dust(x, r):
    """着地や踏み込みで地面に広がる土ぼこりの輪。"""
    return {"type": "ring", "x": x, "y": GROUND, "r": r, "color": "#D8CFB8", "back": True}


def tip_of(p):
    return geometry(clamp(p))["tip"]


def with_glint(p, s=3):
    """刃先にきらめきを足した姿勢を返す。"""
    x, y = tip_of(p)
    q = copy.deepcopy(p)
    q["fx"] = q["fx"] + [glint(x, y, s)]
    return q


# --- 構え (剣士の基本姿勢) ---------------------------------------------------
def ready(**kw):      # 中段の構え: 剣先を斜め前に向け、盾を構える
    return pose(**{**dict(rh=(8, -13), sword=dict(ang=50), lh=(-7, -12), expr="angry"), **kw})


def overhead(**kw):   # 上段: 剣を頭の後ろに振りかぶる
    return pose(**{**dict(y=-1, squash=1.06, tilt=10, rh=(2, -25), sword=dict(ang=-40), lh=(-8, -13), expr="angry"), **kw})


def downcut(**kw):    # 振り下ろした後: 体を前に倒し、剣先は右下
    return pose(**{**dict(x=25, squash=0.88, tilt=-14, rh=(11, -9), sword=dict(ang=135, glow=True), lh=(-8, -12),
                          expr="angry"), **kw})


def thrust(**kw):     # 突き: 大きく踏み込んで、剣をまっすぐ前へ
    return pose(**{**dict(x=27, tilt=-16, squash=0.94, rh=(13, -15), sword=dict(ang=90, glow=True), lh=(-10, -13),
                          expr="angry"), **kw})


def pullback(**kw):   # 突きの前の引き: 体を後ろに引き、剣を水平に引きしぼる
    return pose(**{**dict(x=21, tilt=12, rh=(-3, -15), sword=dict(ang=90), lh=(-9, -12), expr="angry"), **kw})


def salute(**kw):     # 騎士の敬礼: 剣を顔の前にまっすぐ立てる
    return pose(**{**dict(rh=(1, -14), sword=dict(ang=0, glow=True), lh=(-7, -12), expr="smile"), **kw})


def shoulder(**kw):   # 剣を肩にかつぐ
    return pose(**{**dict(rh=(5, -20), sword=dict(ang=-60), lh=(-7, -12)), **kw})


def planted(**kw):    # 剣を地面に突き立て、柄に手を置く
    return pose(**{**dict(rh=(9, -12), sword=dict(ang=180), lh=(-7, -12)), **kw})


def sheathed(**kw):   # 納刀: 剣を腰の鞘に収めて、柄に手を添える
    x = kw.get("x", 24)
    return pose(**{**dict(rh=(-4, -12), lh=(-8, -12),
                          sword=dict(free=True, gx=x - 4, gy=GROUND - 12, ang=205, sheathed=True)), **kw})


def run(x, i, **kw):
    """走りのコマ: 前のめりで弾み、盾を前に構え、剣を後ろに引く。"""
    ph = i % 2
    return pose(x=x, y=-2 * ph, tilt=-16 + 4 * ph, squash=1.05 if ph else 0.92,
                lh=(7, -14 + ph), rh=(-9, -12 - ph), sword=dict(ang=-110 + 20 * ph),
                shield=dict(ang=-10, w=0.8), ghost=(-6, -12),
                fx=[speed(x - 14, GROUND - 16, n=3, length=6)] + ([puff(x)] if ph == 0 else []), **kw)


def spin(base, sxs=(0.5, -0.5, -1.0, -0.5, 0.5)):
    out = []
    for sx in sxs:
        q = copy.deepcopy(base)
        q["sx"] = sx
        out.append(q)
    return out


# --- 動き (24 種) ------------------------------------------------------------
def m_thanks():   # ありがとう!: 剣を顔の前に立てて騎士の敬礼 → 剣を地に突き立てて深くおじぎ
    final = planted(bow=5, squash=0.84, expr="calm", rh=(8, -10), fx=[dust(31, 6)])
    sal = salute()
    seq = [final] + tween(ready(expr="normal"), 1, sal, 1, with_glint(sal, 4), 2,
                          planted(squash=0.92, expr="calm"), 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_morning():  # おはよう!: 朝の素振りを 2 回 → 剣を肩にかついで大きく伸び
    final = shoulder(y=-1, squash=1.1, expr="happy", lh=(-9, -25), fx=[spr("sparkle", 46, 8)])
    cut1 = downcut(fx=[slash(26, 18, 14, -40, 140), dust(30, 8)])
    seq = [final, overhead(), cut1, downcut(), overhead(), with_fx(cut1, slash(26, 18, 14, -40, 140), dust(30, 10)),
           downcut(), lerp(downcut(), final, 0.5), final, final]
    return seq, an.split(3000, len(seq)), 1


def m_ok():       # OK!: 手首で剣をくるくる回す剣さばき → 中段に構えてビシッ
    final = with_glint(ready(expr="wink", sword=dict(ang=45, glow=True)), 4)
    seq = [final, ready(expr="smile")]
    for i, a in enumerate(range(90, 450, 45)):
        seq.append(pose(rh=(8, -16), lh=(-7, -12), expr="smile", tilt=(-4 if i % 2 else 4),
                        sword=dict(ang=a, glow=True), fx=[slash(32, 22, 10, a - 100, a - 20)]))
    seq += [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_roger():    # 了解!: 盾で体当たり → 剣を顔の前に立てて敬礼
    final = with_glint(salute(expr="kira", fx=[spr("exclaim", 46, 6)]), 4)
    crouch = pose(squash=0.76, expr="angry", rh=(9, -8), lh=(-4, -9), sword=dict(ang=120), shield=dict(ang=10, w=0.7))
    bash = pose(x=27, tilt=-16, expr="angry", lh=(-12, -14), rh=(6, -12), sword=dict(ang=-120),
                shield=dict(ang=-15, w=1.0), ghost=(-5,), fx=[speed(54, 12, left=False), hit(10, 20, 5), dust(27, 9)])
    seq = [final] + tween(ready(), 1, crouch, 1, bash, 1, with_fx(bash, hit(10, 20, 7), sparks(10, 20, 7)), 2,
                          final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_sorry():    # ごめん!: 剣と盾を地面に置き、汗を飛ばして何度も深く頭を下げる
    sword = dict(free=True, gx=44, gy=GROUND - 14, ang=180)
    shield = dict(free=True, gx=7, gy=GROUND - 6, ang=8)
    final = pose(bow=6, squash=0.76, expr="sad", lh=(-1, -10), rh=(1, -10), sword=sword, shield=shield,
                 fx=[spr("sweats", 34, 4), spr("sweat", 12, 6)])
    up = pose(y=-2, squash=1.06, expr="sad", lh=(-1, -10), rh=(1, -10), sword=sword, shield=shield,
              fx=[spr("sweat", 34, 6)])
    seq = [final] + tween(final, 2, up, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_otsukare():  # おつかれさま!: 大きく袈裟斬り → 血振り → 腰の鞘にチャキンと納刀
    final = sheathed(expr="calm", fx=[glint(19, 25, 3)])
    cut1 = downcut(fx=[slash(25, 18, 15, -50, 150)])
    flick = pose(x=25, tilt=-6, rh=(12, -12), sword=dict(ang=100, glow=True), lh=(-8, -12), expr="normal",
                 fx=[speed(54, 20, n=2, length=5, left=False)])
    to_hip = pose(rh=(-2, -13), sword=dict(ang=200), lh=(-8, -12), expr="calm")
    seq = [final, overhead(), cut1, downcut(), flick, to_hip, with_fx(final, glint(19, 25, 5)), final, final, final]
    return seq, an.split(3000, len(seq)), 1


def m_congrats():  # おめでとう!: 回転ジャンプで剣を高く掲げて、紙吹雪
    up = dict(rh=(4, -24), sword=dict(ang=0, glow=True), lh=(-10, -20))
    final = with_glint(pose(y=-6, squash=1.12, expr="happy", **up, fx=[confetti(0)]), 4)
    seq = [final, pose(squash=0.75, expr="smile", rh=(8, -10), sword=dict(ang=60))]
    seq += spin(pose(y=-6, squash=1.1, expr="happy", **up, fx=[confetti(1)]), (0.5, -0.5, -1.0, -0.5, 0.5))
    seq += [with_fx(final, confetti(2)), pose(squash=0.8, expr="happy", **up, fx=[confetti(3), dust(24, 12)]),
            final, final]
    return seq, an.split(3000, len(seq)), 1


def m_goodnight():  # おやすみ: 盾を抱えて剣にもたれ、こっくり → ハッ!
    final = pose(tilt=-16, bow=3, expr="sleep", rh=(9, -14), sword=dict(ang=180), lh=(-1, -12),
                 shield=dict(ang=20, w=0.9), fx=[spr("zzz", 40, 2)])
    awake = pose(y=-2, squash=1.08, expr="surprised", rh=(9, -14), sword=dict(ang=180), lh=(-6, -12),
                 fx=[spr("exclaim", 42, 6)])
    seq = [final] + tween(final, 3, awake, 1, awake, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_ittekimasu():  # いってきます!: 剣を肩にかついで出発 → 盾を構えて全速力で走っていく
    final = shoulder(expr="happy", lh=(-11, -22), fx=[spr("note", 4, 4)])
    seq = [final, shoulder(expr="happy", lh=(-12, -16)), final]
    seq += [run(26 + 8 * i, i, expr="angry") for i in range(1, 6)]
    seq += [run(-6 + 8 * i, i, expr="angry") for i in range(1, 4)] + [shoulder(squash=0.85, expr="happy"), final]
    return seq, an.split(4000, len(seq)), 1


def m_tadaima():  # ただいま!: 走って帰ってきてジャンプ、剣を地面に突き立ててザクッ!
    final = planted(squash=0.86, expr="happy", rh=(10, -10), lh=(-10, -22), shield=dict(ang=-20, w=1.0),
                    fx=[dust(34, 12), puff(34), spr("note", 46, 4)])
    seq = [final] + [run(-6 + 8 * i, i, expr="smile") for i in range(1, 5)]
    seq += [pose(y=-6, squash=1.12, expr="happy", rh=(8, -24), sword=dict(ang=170, glow=True), lh=(-10, -22)),
            final, with_fx(final, dust(34, 18), dust(34, 10), puff(34)), final, final]
    return seq, an.split(3000, len(seq)), 1


def m_yoroshiku():  # よろしく!: 剣と盾を胸の前でガキンと交差 → 勢いよくおじぎ
    cross = pose(expr="angry", rh=(4, -14), sword=dict(ang=-40, glow=True), lh=(-3, -14), shield=dict(ang=0, w=1.0),
                 fx=[sparks(21, 13, 6)])
    final = planted(bow=5, squash=0.84, expr="calm", rh=(8, -10), sword=dict(ang=170), fx=[dust(32, 6)])
    seq = [final] + tween(ready(), 2, cross, 1, with_fx(cross, sparks(21, 13, 9), hit(21, 13, 3)), 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_omakase():  # おまかせを!: 盾で胸をドンと叩き、剣先をビシッと前に向ける
    final = with_glint(thrust(x=25, tilt=-8, expr="kira", fx=[spr("exclaim", 46, 2)]), 4)
    thump = pose(squash=0.9, tilt=6, expr="angry", rh=(9, -12), sword=dict(ang=40), lh=(-1, -15), fx=[hit(22, 16, 4)])
    seq = [final] + tween(ready(), 1, with_fx(thump, hit(22, 16, 6)), 1, ready(), 1, thump, 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_gyoi():     # 御意!: 片ひざをついて剣を地に立て、盾を横に置いて深く頭を垂れる
    final = planted(squash=0.72, bow=5, expr="calm", rh=(8, -9), lh=(-7, -9), shield=dict(ang=-10, w=0.8),
                    fx=[dust(32, 9)])
    seq = [final] + tween(ready(expr="normal"), 1, planted(y=-2, squash=1.05, expr="normal", rh=(6, -18)), 2,
                          planted(squash=0.72, expr="normal", rh=(8, -9), lh=(-7, -9), fx=[dust(32, 12), puff(32)]), 2,
                          final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_fight():    # ファイト!: 剣を左右に大きく連続で振る (斬撃が交差する)
    l = pose(y=-4, tilt=20, squash=1.08, expr="angry", rh=(-2, -24), sword=dict(ang=-70, glow=True), lh=(-9, -12),
             fx=[slash(24, 14, 14, 70, -70), speed(52, 10, left=False)])
    r = pose(y=-4, tilt=-20, squash=1.08, expr="angry", rh=(10, -22), sword=dict(ang=70, glow=True), lh=(-9, -12),
             fx=[slash(24, 14, 14, -70, 70), speed(10, 10)])
    mid = pose(squash=0.82, expr="kira", rh=(5, -20), sword=dict(ang=0, glow=True), lh=(-9, -12), fx=[dust(24, 9)])
    seq = [r, lerp(r, mid, 0.5), mid, lerp(mid, l, 0.5), l, lerp(l, mid, 0.5), mid, lerp(mid, r, 0.5)]
    return seq, an.split(1000, len(seq)), 3


def m_sasuga():   # さすが!: 剣で盾をカンカン叩いて火花を散らし、たたえる
    hit_p = pose(tilt=-6, expr="happy", lh=(-4, -14), rh=(4, -14), sword=dict(ang=-60, glow=True),
                 fx=[sparks(15, 18, 6), hit(15, 18, 3)])
    lift = pose(tilt=8, y=-2, expr="happy", lh=(-6, -14), rh=(8, -22), sword=dict(ang=20, glow=True))
    seq = [hit_p, lift, lerp(lift, hit_p, 0.5), hit_p, with_fx(hit_p, sparks(15, 18, 9), hit(15, 18, 4))]
    return seq, an.split(1000, len(seq)), 3


def m_iine():     # いいね!: 引きしぼってから、残像とともに鋭い突き! → 刃先がキラッ
    final = with_glint(thrust(expr="wink", fx=[speed(6, 16, n=3, length=6)]), 4)
    strike = thrust(ghost=(-5, -10), fx=[speed(6, 16, n=3, length=8), hit(tip_of(thrust())[0], tip_of(thrust())[1], 5)])
    seq = [final] + tween(ready(), 2, pullback(), 1, strike, 1, with_fx(strike, hit(*tip_of(thrust()), 7)), 2,
                          final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_nice():     # ナイス!: 体ごと 1 回転しながら剣を水平に振り回す回転斬り → 決め
    final = with_glint(pose(tilt=-10, expr="kira", rh=(11, -15), sword=dict(ang=80, glow=True), lh=(-9, -13),
                            fx=[slash(24, 22, 15, -100, 100)]), 4)
    seq = [final, pose(squash=0.85, expr="angry", rh=(-8, -14), sword=dict(ang=-90), lh=(-9, -12))]
    for i, sx in enumerate((0.5, -0.5, -1.0, -0.5, 0.5, 1.0)):
        seq.append(pose(sx=sx, y=-2, expr="angry", rh=(9, -15), sword=dict(ang=80 + i * 60, glow=True), lh=(-9, -13),
                        fx=[slash(24, 22, 15, -100 + i * 40, 20 + i * 40), dust(24, 10)]))
    seq += [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_muri():     # 無理しないでね: 盾をそっと差し出してかばい、心配そうに見つめる
    final = pose(x=22, tilt=-10, expr="worry", lh=(-11, -16), rh=(8, -11), sword=dict(ang=160),
                 shield=dict(ang=-12, w=1.0), fx=[spr("heart", 46, 6), spr("sweat", 14, 2)])
    seq = [final] + tween(pose(expr="worry"), 3, final, 3, with_fx(final, spr("heart", 46, 2), spr("sweat", 14, 2))) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_yukkuri():  # ゆっくり休んで: 剣を肩にかついで、ゆったり手を振る
    final = shoulder(expr="calm", lh=(-11, -22), fx=[spr("heart", 4, 2), spr("zzz", 44, 4)])
    a = shoulder(tilt=6, expr="calm", lh=(-12, -16), fx=[spr("heart", 4, 4), spr("zzz", 44, 6)])
    seq = [final] + tween(a, 3, final, 3, a)[1:-1]
    return seq, an.split(2000, len(seq)), 2


def m_mukatteru():  # いま向かってる: 盾を構え、残像を残して全速力で画面を駆け抜ける
    final = run(30, 0, expr="angry")
    final["fx"].append(spr("sweat", 6, 4))
    seq = [final] + [run(-10 + 8 * i, i, expr="angry") for i in range(1, 10)] + [final]
    return seq, an.split(2000, len(seq)), 2


def m_tsuita():   # 着いたよ!: 跳んできてズザッと着地、剣を地面に突き立てる
    final = planted(expr="happy", lh=(-10, -22), fx=[dust(32, 8), spr("note", 46, 6)])
    seq = [final, pose(x=4, y=-8, tilt=-20, squash=1.1, expr="surprised", rh=(8, -14), sword=dict(ang=60), ghost=(-5,)),
           pose(x=12, y=-8, tilt=-15, squash=1.1, expr="surprised", rh=(8, -14), sword=dict(ang=60), ghost=(-6, -12)),
           pose(x=20, y=-4, tilt=-10, expr="surprised", rh=(8, -14), sword=dict(ang=90), ghost=(-6, -12)),
           planted(x=24, squash=0.75, tilt=-6, expr="angry", rh=(9, -10), fx=[puff(24), dust(24, 14), speed(8, 30, n=2, length=8)]),
           planted(x=24, squash=0.85, expr="smile", fx=[puff(24)])]
    seq += tween(seq[-1], 2, final)[1:] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_gohan():    # ごはんどうする?: 盾をお盆のように持ち、首をかしげて剣を揺らす
    tray = dict(ang=90, w=0.5)
    final = pose(tilt=12, expr="normal", lh=(-9, -16), shield=tray, rh=(8, -18), sword=dict(ang=-15),
                 fx=[spr("question", 48, 2), spr("note", 2, 4)])
    other = pose(tilt=-12, expr="normal", lh=(-9, -16), shield=tray, rh=(8, -18), sword=dict(ang=15),
                 fx=[spr("question", 48, 4), spr("note", 2, 2)])
    seq = [final] + tween(final, 3, other, 3, final)[1:-1]
    return seq, an.split(2000, len(seq)), 2


def m_majika():   # まじか!?: のけぞって跳び上がり、剣が手から吹っ飛ぶ
    final = pose(y=-6, tilt=14, squash=1.12, expr="surprised", lh=(-3, -16), rh=(10, -24),
                 sword=dict(free=True, gx=48, gy=10, ang=140), shield=dict(ang=0, w=1.0),
                 fx=[spr("exclaim_q", 3, 22), spr("sweats", 34, 14)])
    seq = [final, ready(expr="normal")]
    for i, (gx, gy, a) in enumerate([(36, 22, 30), (42, 14, 90), (48, 10, 150), (52, 8, 220), (50, 12, 290), (44, 20, 350)]):
        seq.append(pose(y=-6 + max(0, i - 2) * 2, tilt=14, squash=1.12, expr="surprised", lh=(-3, -16), rh=(10, -24),
                        sword=dict(free=True, gx=gx, gy=gy, ang=a), shield=dict(ang=0, w=1.0), fx=[spr("exclaim_q", 3, 22)]))
    seq += [pose(squash=0.75, expr="surprised", fx=[spr("sweats", 36, 8), puff(24)]), pose(expr="surprised"), final]
    return seq, an.split(2000, len(seq)), 2


def m_yossha():   # よっしゃー!: 十字斬り (✕) を決めてから、剣を天に突き上げて跳ぶ
    up = dict(rh=(4, -24), sword=dict(ang=0, glow=True), lh=(-10, -20))
    xcut = [cut(34, 6, 54, 26), cut(54, 6, 34, 26)]
    final = with_glint(pose(y=-6, squash=1.14, expr="kira", **up, shield=dict(ang=-20, w=1.0),
                            fx=xcut + [confetti(3)]), 5)
    cut_a = pose(x=26, tilt=-12, expr="angry", rh=(12, -10), sword=dict(ang=140, glow=True), lh=(-9, -12),
                 fx=[cut(34, 6, 54, 26)])
    cut_b = pose(x=26, tilt=12, expr="angry", rh=(-2, -10), sword=dict(ang=-140, glow=True), lh=(-9, -12),
                 fx=xcut + [sparks(44, 16, 6)])
    crouch = pose(squash=0.72, expr="angry", rh=(8, -9), sword=dict(ang=60), lh=(-6, -9), fx=xcut)
    seq = [final, ready(), overhead(), cut_a, overhead(tilt=-10, rh=(10, -25), sword=dict(ang=40)), cut_b,
           crouch, final, with_fx(final, *xcut, confetti(5)),
           pose(squash=0.82, expr="happy", **up, fx=xcut + [dust(24, 14), puff(24)]), final, final]
    return seq, an.split(3000, len(seq)), 1


MOTIONS = {
    "thanks": m_thanks, "morning": m_morning, "ok": m_ok, "roger": m_roger, "sorry": m_sorry,
    "otsukare": m_otsukare, "congrats": m_congrats, "goodnight": m_goodnight, "ittekimasu": m_ittekimasu,
    "tadaima": m_tadaima, "yoroshiku": m_yoroshiku, "omakase": m_omakase, "gyoi": m_gyoi, "fight": m_fight,
    "sasuga": m_sasuga, "iine": m_iine, "nice": m_nice, "muri": m_muri, "yukkuri": m_yukkuri,
    "mukatteru": m_mukatteru, "tsuita": m_tsuita, "gohan": m_gohan, "majika": m_majika, "yossha": m_yossha,
}


# --- 書き出し ----------------------------------------------------------------
def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = cfg_path.parent / cfg.get("output", "output_warrior")
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

    # メイン画像 (240x240): 剣を立てて構え、刃がきらめく
    grids = [render_grid(pose(expr=e, rh=(9, -13), sword=dict(ang=0, glow=True)), phase=j)
             for j, e in enumerate(["normal"] * 5 + ["calm"] + ["normal"] * 4)]
    box = (6, 4, 44, GROUND + 2)
    k = min((MAIN_SIZE[0] - 20) // (box[2] - box[0]), (MAIN_SIZE[1] - 20) // (box[3] - box[1]))
    mains = []
    for g in grids:
        big = ps.scaled(g.crop(box), k)
        canvas = Image.new("RGBA", MAIN_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(big, ((MAIN_SIZE[0] - big.width) // 2, (MAIN_SIZE[1] - big.height) // 2))
        mains.append(canvas)
    an.save_apng(mains, an.split(2000, len(mains)), 2, out / "main.png")
    problems += [f"main.png: {e}" for e in an.check_anim(out / "main.png", "main")[1]]
    ps.fit_square(render_grid(pose(expr="smile", rh=(9, -13), sword=dict(ang=0))), TAB_SIZE, 2).save(out / "tab.png")

    an.make_preview_gif(all_frames, cfg_path.parent / cfg.get("preview", "preview_warrior.gif"))
    zip_path = cfg_path.parent / f"{cfg.get('name', 'warrior_anim_stamp')}.zip"
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
    ap = argparse.ArgumentParser(description="剣と盾の戦士の動くスタンプ")
    ap.add_argument("-c", "--config", default="warrior_stamps.json")
    build(ap.parse_args().config)


if __name__ == "__main__":
    main()
