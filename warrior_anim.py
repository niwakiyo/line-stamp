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
IDLE = dict(x=24, y=0, tilt=0, squash=1.0, sx=1.0, bow=0, expr="normal",
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
_EL, _ER = 6, 9
FACES = {
    "normal":    [(_EL, 11, "E"), (_EL, 12, "E"), (_ER, 11, "E"), (_ER, 12, "E")],
    "smile":     [(_EL, 11, "E"), (_EL, 12, "E"), (_ER, 11, "E"), (_ER, 12, "E"), (7, 13, "R"), (8, 13, "R")],
    "calm":      [(5, 12, "E"), (6, 12, "E"), (9, 12, "E"), (10, 12, "E")],
    "sleep":     [(5, 12, "E"), (6, 12, "E"), (9, 12, "E"), (10, 12, "E"), (7, 13, "K")],
    "happy":     [(5, 12, "E"), (6, 11, "E"), (7, 12, "E"), (8, 12, "E"), (9, 11, "E"), (10, 12, "E"),
                  (7, 13, "R"), (8, 13, "R")],
    "wink":      [(_EL, 11, "E"), (_EL, 12, "E"), (9, 12, "E"), (10, 12, "E"), (7, 13, "R"), (8, 13, "R")],
    "surprised": [(_EL, 11, "E"), (_EL, 12, "E"), (_ER, 11, "E"), (_ER, 12, "E"), (7, 13, "K"), (8, 13, "K"),
                  (5, 10, "E"), (10, 10, "E")],
    "kira":      [(_EL, 11, "Y"), (_EL, 12, "Y"), (_ER, 11, "Y"), (_ER, 12, "Y"), (7, 13, "R"), (8, 13, "R")],
    "sad":       [(_EL, 12, "E"), (_ER, 12, "E"), (_EL, 13, "L"), (_ER, 13, "L"), (5, 10, "E"), (10, 10, "E")],
    "angry":     [(_EL, 11, "E"), (_EL, 12, "E"), (_ER, 11, "E"), (_ER, 12, "E"), (6, 10, "E"), (9, 10, "E"),
                  (7, 13, "K"), (8, 13, "K")],
    "worry":     [(_EL, 12, "E"), (_ER, 12, "E"), (4, 10, "E"), (11, 10, "E")],
    "love":      [(_EL, 11, "R"), (_EL, 12, "R"), (_ER, 11, "R"), (_ER, 12, "R"), (7, 13, "R"), (8, 13, "R")],
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
def draw_sword(d, g, glow, phase):
    (hx, hy), (ux, uy) = g["grip"], g["u"]
    nx, ny = -uy, ux
    guard = (hx + ux * 1.5, hy + uy * 1.5)
    tip = g["tip"]
    # 刃: 輪郭 → 白い刃 → 刃の影の筋
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
    if glow:  # 刃のきらめき: 刃の上を光が走り、刃先が光る
        f = 0.25 + 0.6 * ((phase % 4) / 3)
        gx, gy = guard[0] + (tip[0] - guard[0]) * f, guard[1] + (tip[1] - guard[1]) * f
        d.point((round(gx), round(gy)), fill=col(WHITE))
        tx, ty = round(tip[0]), round(tip[1])
        r = 2 + phase % 2
        d.point([(tx, ty - r), (tx, ty + r), (tx - r, ty), (tx + r, ty)], fill=col(WHITE))


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
    """三日月形の斬撃 (外側が白、内側が水色)。"""
    cx, cy, r, a0, a1 = e["cx"], e["cy"], e["r"], e["a0"], e["a1"]
    for rr, c, w in ((r, WHITE, 2), (r - 2, CYAN, 1)):
        pts = wz.arc_pts(cx, cy, rr, a0, a1, 10)
        d.line(pts, fill=col(c), width=w)


def draw_trail(d, tips):
    colors = [VIOLET, CYAN, WHITE]
    for i in range(len(tips) - 1):
        c = colors[max(0, len(colors) - (len(tips) - 1) + i)]
        d.line([tips[i], tips[i + 1]], fill=col(c), width=3 if i == len(tips) - 2 else 2)


def render_grid(p, phase=0, trail=()):
    jumped = p["y"] <= -2
    p = clamp(p)
    gimg = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    d = ImageDraw.Draw(gimg)
    g = geometry(p)
    ax, ay = g["anchor"]
    wz.draw_fx(gimg, d, [e for e in p["fx"] if e.get("type") != "slash"], g, phase, back=True)
    if not p["shield"].get("front") and not p["shield"].get("free"):
        draw_shield(gimg, p, g)
    if p["shield"].get("free"):
        draw_shield(gimg, p, g)

    body = body_image(p)
    tmp = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    tmp.alpha_composite(body, (24 - body.width // 2, 44 - body.height))
    if p["tilt"]:
        tmp = tmp.rotate(p["tilt"], resample=Image.NEAREST, center=(24, 44))
    gimg.alpha_composite(tmp, (round(ax) - 24, round(ay) - 44))

    if len(trail) >= 2:
        draw_trail(d, list(trail) + [g["tip"]])
    for e in p["fx"]:
        if e.get("type") == "slash":
            draw_slash(d, e)
    # 剣は別の層に描き、地面より下は消す (地面に突き立てた剣が文字のウィンドウに刺さらないように)
    layer = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    draw_sword(ImageDraw.Draw(layer), g, p["sword"].get("glow"), phase)
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
    wz.draw_fx(gimg, d, [e for e in p["fx"] if e.get("type") != "slash"], g, phase, back=False)
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


# --- エフェクトの部品 (wizard_anim のものを使う) -----------------------------
spr, burst, speed, ring, puff, confetti = wz.spr, wz.burst, wz.speed, wz.ring, wz.puff, wz.confetti
circle = wz.circle
GOLD_AURA = {"type": "aura", "n": 9, "color": GOLD}
RAINBOW_AURA = wz.AURA


def slash(cx, cy, r, a0, a1):
    return {"type": "slash", "cx": cx, "cy": cy, "r": r, "a0": a0, "a1": a1}


def bolt_to_tip(x1, y1):
    return {"type": "bolt", "from": "orb", "x1": x1, "y1": y1}


# --- 動き (24 種) ------------------------------------------------------------
UP = dict(rh=(4, -24), sword=dict(ang=0, glow=True))                 # 剣を真上に掲げる
GUARD = dict(lh=(-2, -14), shield=dict(ang=0, w=1.0, front=True))     # 盾を体の前に構える


def run(x, i, **kw):
    """走りのコマ: 前のめりで弾み、盾を前に構え、剣を後ろに引く。"""
    ph = i % 2
    return pose(x=x, y=-2 * ph, tilt=-16 + 4 * ph, squash=1.05 if ph else 0.92,
                lh=(7, -14 + ph), rh=(-9, -12 - ph), sword=dict(ang=-110 + 20 * ph),
                shield=dict(ang=-10, w=0.8), fx=[speed(x - 12, GROUND - 16, n=3, length=6)] +
                ([puff(x)] if ph == 0 else []), **kw)


def spin(base, sxs=(0.5, -0.5, -1.0, -0.5, 0.5)):
    out = []
    for sx in sxs:
        q = copy.deepcopy(base)
        q["sx"] = sx
        out.append(q)
    return out


def m_thanks():   # ありがとう!: 剣を顔の前に立てて騎士の敬礼 → 剣を地に突き立てて深くおじぎ
    final = pose(bow=5, squash=0.84, expr="calm", rh=(6, -9), sword=dict(ang=180, glow=True),
                 lh=(-7, -10), shield=dict(ang=0, w=1.0),
                 fx=[burst(24, 4, 7, "rainbow"), spr("sparkle", 44, 2), ring(30, 8)])
    salute = pose(expr="smile", rh=(1, -14), sword=dict(ang=0, glow=True), fx=[spr("sparkle", 30, 0)])
    seq = [final] + tween(pose(), 2, salute, 2, with_fx(salute, burst(25, 2, 5)), 2,
                          pose(squash=0.9, expr="calm", rh=(6, -12), sword=dict(ang=180), lh=(-7, -10)), 2, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_morning():  # おはよう!: 剣を真上に突き上げて大きく伸び、朝日のように光る
    final = pose(y=-2, squash=1.16, expr="happy", **UP, lh=(-9, -16), fx=[{"type": "rays", "n": 10, "r0": 4, "r1": 9},
                                                                           spr("sparkle", 46, 10)])
    yawn = pose(squash=0.82, bow=2, expr="sleep", rh=(8, -10), sword=dict(ang=150), fx=[spr("zzz", 38, 8)])
    left = pose(y=-2, squash=1.12, tilt=20, expr="calm", rh=(2, -24), sword=dict(ang=-25, glow=True), lh=(-9, -18))
    right = pose(y=-2, squash=1.12, tilt=-20, expr="calm", rh=(6, -24), sword=dict(ang=25, glow=True), lh=(-9, -18))
    seq = [final] + tween(yawn, 2, final, 2, left, 2, right, 2, final) + [final]
    return seq, an.split(3000, len(seq)), 1


def m_ok():       # OK!: 剣を頭上で大きく 1 回転させて光の輪を描き、ビシッと止める
    seq, pts = [], []
    for a in range(-30, 331, 30):
        g = geometry(pose(rh=(4, -22), sword=dict(ang=a)))
        pts.append(g["tip"])
        seq.append(pose(rh=(4, -22), lh=(-8, -12), tilt=-math.sin(math.radians(a)) * 12, expr="smile",
                        sword=dict(ang=a, glow=True), fx=[{"type": "plus", "pts": list(pts), "color": "rainbow"}]))
    final = pose(rh=(4, -22), lh=(-8, -12), tilt=-4, expr="wink", sword=dict(ang=330, glow=True),
                 fx=[{"type": "plus", "pts": pts, "color": "rainbow"}, spr("sparkles", 46, 22)])
    seq = [final] + seq + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_roger():    # 了解!: 盾をドンと前に突き出し、剣を真上に掲げて稲妻を受ける
    final = pose(y=-3, squash=1.08, expr="kira", rh=(5, -24), lh=(-9, -14), sword=dict(ang=0, glow=True),
                 shield=dict(ang=-10, w=1.0), fx=[bolt_to_tip(40, 0), bolt_to_tip(14, 0), spr("exclaim", 48, 10), GOLD_AURA])
    crouch = pose(squash=0.76, expr="angry", rh=(9, -8), lh=(-4, -9), sword=dict(ang=120), **{"shield": dict(ang=10, w=0.7)})
    bash = pose(x=26, tilt=-14, expr="angry", lh=(-11, -14), rh=(6, -12), sword=dict(ang=-120),
                shield=dict(ang=-15, w=1.0), fx=[speed(6, 14, left=True), burst(12, 22, 6)])
    seq = [final] + tween(pose(), 1, crouch, 2, bash, 2, final, 1, with_fx(final, ring(26, 14), puff(24))) + [final] * 3
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


def m_otsukare():  # おつかれさま!: 大きく剣を振り抜いてから、地面に突き立てて寄りかかり、ねぎらう
    final = pose(tilt=-6, expr="smile", rh=(8, -13), sword=dict(ang=180, glow=True), lh=(-9, -12),
                 fx=[spr("sparkle", 44, 4), {"type": "plus", "pts": [(42, 14), (50, 20), (6, 8), (10, 18)], "color": "rainbow"}])
    back = pose(tilt=18, expr="angry", rh=(-4, -24), sword=dict(ang=-70, glow=True), lh=(-9, -12))
    swing = pose(tilt=-20, x=26, expr="angry", rh=(12, -14), sword=dict(ang=110, glow=True), lh=(-9, -14),
                 fx=[slash(26, 16, 14, -60, 120)])
    seq = [final] + tween(pose(), 1, back, 2, swing, 1, with_fx(swing, slash(26, 16, 14, -60, 120), burst(44, 20, 5)), 2,
                          final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_congrats():  # おめでとう!: 回転ジャンプして剣を掲げ、刃先から花火
    def fw(r, seed):
        return [burst(46, 8, r, PINK), burst(46, 8, r * 0.55, GOLD, 6), burst(12, 8, r * 0.8, CYAN),
                burst(30, 3, r * 0.5, VIOLET, 6), confetti(seed)]
    final = pose(y=-6, squash=1.12, expr="happy", **UP, lh=(-10, -20), fx=fw(7, 0))
    seq = [final, pose(squash=0.75, expr="smile", rh=(8, -10), sword=dict(ang=60))]
    seq += spin(pose(y=-6, squash=1.1, expr="happy", **UP, lh=(-10, -20), fx=fw(3, 1)), (0.5, -0.5, -1.0, -0.5, 0.5))
    seq += [with_fx(final, *fw(5, 2)), with_fx(final, *fw(9, 3)),
            pose(squash=0.8, expr="happy", **UP, lh=(-10, -20), fx=fw(8, 4) + [puff(24)]), final, final]
    return seq, an.split(3000, len(seq)), 1


def m_goodnight():  # おやすみ: 盾を枕のように抱えて剣にもたれ、こっくり → ハッ!
    final = pose(tilt=-16, bow=3, expr="sleep", rh=(9, -14), sword=dict(ang=180), lh=(-1, -12),
                 shield=dict(ang=20, w=0.9), fx=[spr("zzz", 40, 2)])
    awake = pose(y=-2, squash=1.08, expr="surprised", rh=(9, -14), sword=dict(ang=180), lh=(-6, -12),
                 fx=[spr("exclaim", 42, 6)])
    seq = [final] + tween(final, 3, awake, 1, awake, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_ittekimasu():  # いってきます!: 剣を高く掲げて出発の合図 → 盾を構えて全速力で走っていく
    final = pose(y=-3, squash=1.1, expr="happy", **UP, lh=(-9, -14), fx=[spr("sparkle", 30, 0), spr("note", 4, 4)])
    seq = [final, pose(squash=0.82, expr="smile", rh=(8, -12), sword=dict(ang=40)), final]
    seq += [run(26 + 8 * i, i, expr="angry") for i in range(1, 6)]
    seq += [run(-6 + 8 * i, i, expr="angry") for i in range(1, 4)] + [pose(squash=0.85, expr="happy"), final]
    return seq, an.split(4000, len(seq)), 1


def m_tadaima():  # ただいま!: 走って帰ってきてジャンプ、剣を地面に突き立ててドン!
    final = pose(squash=0.86, expr="happy", rh=(10, -10), sword=dict(ang=180, glow=True), lh=(-10, -22),
                 shield=dict(ang=-20, w=1.0), fx=[ring(34, 12), puff(34), spr("note", 46, 4)])
    seq = [final] + [run(-6 + 8 * i, i, expr="smile") for i in range(1, 5)]
    seq += [pose(y=-6, squash=1.12, expr="happy", rh=(8, -24), sword=dict(ang=170, glow=True), lh=(-10, -22)),
            final, with_fx(final, ring(34, 18, VIOLET), ring(34, 10), puff(34)), final, final]
    return seq, an.split(3000, len(seq)), 1


def m_yoroshiku():  # よろしく!: 剣と盾を胸の前で交差させてから、勢いよくおじぎ
    cross = pose(expr="smile", rh=(4, -14), sword=dict(ang=-40, glow=True), lh=(-3, -14), shield=dict(ang=0, w=1.0),
                 fx=[burst(24, 10, 8, GOLD)])
    final = pose(bow=5, squash=0.84, expr="calm", rh=(8, -10), sword=dict(ang=160), lh=(-7, -10),
                 fx=[spr("sparkle", 44, 4), burst(24, 4, 6, "rainbow")])
    seq = [final] + tween(pose(), 2, cross, 1, with_fx(cross, burst(24, 10, 11, "rainbow")), 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_omakase():  # おまかせを!: 盾で胸をドンと叩き、剣を掲げて金色のオーラ
    final = pose(y=-2, squash=1.1, expr="kira", **UP, lh=(-3, -15), shield=dict(ang=0, w=1.0),
                 fx=[GOLD_AURA, burst(27, 3, 6, GOLD), spr("sparkle", 46, 10)])
    thump = pose(squash=0.9, tilt=6, expr="angry", rh=(9, -12), sword=dict(ang=40), lh=(-1, -15),
                 fx=[burst(22, 16, 6), GOLD_AURA])
    seq = [final] + tween(pose(), 1, with_fx(thump, burst(22, 16, 4)), 1, pose(expr="angry", lh=(-8, -14)), 1, thump, 2,
                          final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_gyoi():     # 御意!: 片ひざをついて剣を地に立て、盾を横に置いて深く頭を垂れる
    final = pose(squash=0.72, bow=5, expr="calm", rh=(8, -9), sword=dict(ang=180), lh=(-7, -9),
                 shield=dict(ang=-10, w=0.8), fx=[burst(24, 3, 5, GOLD), ring(32, 9)])
    seq = [final] + tween(pose(expr="normal"), 1, pose(y=-2, squash=1.05, expr="normal", rh=(6, -18), sword=dict(ang=180)), 2,
                          pose(squash=0.72, expr="normal", rh=(8, -9), sword=dict(ang=180), lh=(-7, -9),
                               fx=[ring(32, 12), puff(32)]), 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_fight():    # ファイト!: 剣を左右に大きく連続で振り、跳ねながら応援
    l = pose(y=-4, tilt=20, squash=1.08, expr="angry", rh=(-2, -24), sword=dict(ang=-70, glow=True), lh=(-9, -12),
             fx=[slash(24, 14, 13, 70, -70), speed(52, 10, left=False)])
    r = pose(y=-4, tilt=-20, squash=1.08, expr="angry", rh=(10, -22), sword=dict(ang=70, glow=True), lh=(-9, -12),
             fx=[slash(24, 14, 13, -70, 70), speed(10, 10)])
    mid = pose(squash=0.82, expr="kira", rh=(5, -20), sword=dict(ang=0, glow=True), lh=(-9, -12), fx=[])
    seq = [r, lerp(r, mid, 0.5), mid, lerp(mid, l, 0.5), l, lerp(l, mid, 0.5), mid, lerp(mid, r, 0.5)]
    return seq, an.split(1000, len(seq)), 3


def m_sasuga():   # さすが!: 剣で盾をカンカン叩いて火花を散らし、たたえる
    hit = pose(tilt=-6, expr="happy", lh=(-4, -14), rh=(4, -14), sword=dict(ang=-60, glow=True),
               fx=[burst(15, 18, 5, GOLD), spr("sparkle", 44, 4)])
    lift = pose(tilt=8, y=-2, expr="happy", lh=(-6, -14), rh=(8, -22), sword=dict(ang=20, glow=True), fx=[spr("sparkle", 44, 6)])
    seq = [hit, lift, lerp(lift, hit, 0.5), hit, with_fx(hit, burst(15, 18, 8, "rainbow"))]
    return seq, an.split(1000, len(seq)), 3


def m_iine():     # いいね!: 斜め上に剣をビシッと突き出してウインク、刃先がキラーン
    final = pose(tilt=-14, x=22, expr="wink", rh=(10, -20), sword=dict(ang=45, glow=True), lh=(-9, -14),
                 fx=[spr("sparkles", 46, 0), burst(42, 6, 5, "rainbow")])
    pull = pose(tilt=10, squash=0.9, expr="smile", rh=(-4, -14), sword=dict(ang=-100), lh=(-9, -12))
    seq = [final] + tween(pose(), 2, pull, 2, final, 1, with_fx(final, burst(42, 6, 8, "rainbow"), spr("sparkles", 46, 0))) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_nice():     # ナイス!: 体ごと 1 回転しながら剣を水平に振り回す回転斬り → 決め
    final = pose(tilt=-10, expr="kira", rh=(11, -15), sword=dict(ang=80, glow=True), lh=(-9, -13),
                 fx=[slash(24, 22, 15, -100, 100), spr("sparkle", 48, 4)])
    seq = [final, pose(squash=0.85, expr="angry", rh=(-8, -14), sword=dict(ang=-90), lh=(-9, -12))]
    for i, (sx, a) in enumerate(zip((0.5, -0.5, -1.0, -0.5, 0.5, 1.0), (-60, 0, 60, 120, 180, 240))):
        seq.append(pose(sx=sx, y=-2, expr="angry", rh=(9, -15), sword=dict(ang=80 + i * 60, glow=True), lh=(-9, -13),
                        fx=[slash(24, 22, 15, -100 + i * 40, 20 + i * 40)]))
    seq += [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_muri():     # 無理しないでね: 盾をそっと差し出してかばい、心配そうに見つめる
    final = pose(x=22, tilt=-10, expr="worry", lh=(-11, -16), rh=(8, -11), sword=dict(ang=160),
                 shield=dict(ang=-12, w=1.0), fx=[spr("heart", 46, 6), spr("sweat", 14, 2), {"type": "rays", "n": 6, "r0": 6, "r1": 8}])
    seq = [final] + tween(pose(expr="worry"), 3, final, 3, with_fx(final, spr("heart", 46, 2), spr("sweat", 14, 2))) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_yukkuri():  # ゆっくり休んで: 剣を肩にかついで、ゆったり手を振る
    st = dict(ang=-60)
    final = pose(expr="calm", rh=(5, -20), sword=st, lh=(-11, -22), fx=[spr("heart", 4, 2), spr("zzz", 44, 4)])
    a = pose(tilt=6, expr="calm", rh=(5, -20), sword=st, lh=(-12, -16), fx=[spr("heart", 4, 4), spr("zzz", 44, 6)])
    seq = [final] + tween(a, 3, final, 3, a)[1:-1]
    return seq, an.split(2000, len(seq)), 2


def m_mukatteru():  # いま向かってる: 盾を構えて全速力で画面を駆け抜ける
    final = run(30, 0, expr="angry")
    final["fx"].append(spr("sweat", 6, 4))
    seq = [final] + [run(-10 + 8 * i, i, expr="angry") for i in range(1, 10)] + [final]
    return seq, an.split(2000, len(seq)), 2


def m_tsuita():   # 着いたよ!: 跳んできてズザッと着地、剣を掲げて到着の合図
    final = pose(expr="happy", **UP, lh=(-10, -20), fx=[spr("sparkle", 30, 0), puff(24), spr("note", 46, 6)])
    seq = [final, pose(x=4, y=-8, tilt=-20, squash=1.1, expr="surprised", rh=(8, -14), sword=dict(ang=60)),
           pose(x=12, y=-8, tilt=-15, squash=1.1, expr="surprised", rh=(8, -14), sword=dict(ang=60)),
           pose(x=20, y=-4, tilt=-10, expr="surprised", rh=(8, -14), sword=dict(ang=60)),
           pose(x=24, squash=0.75, tilt=-6, expr="angry", rh=(9, -10), sword=dict(ang=120), fx=[puff(24), speed(8, 30, n=2, length=8)]),
           pose(x=24, squash=0.85, expr="smile", rh=(9, -12), sword=dict(ang=60), fx=[puff(24)])]
    seq += tween(seq[-1], 2, final)[1:] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_gohan():    # ごはんどうする?: 盾をお盆のように持ち、首をかしげて剣をフォークのように揺らす
    tray = dict(ang=90, w=0.5)
    final = pose(tilt=12, expr="normal", lh=(-9, -16), shield=tray, rh=(8, -18), sword=dict(ang=-15),
                 fx=[spr("question", 48, 2), spr("note", 2, 4)])
    other = pose(tilt=-12, expr="normal", lh=(-9, -16), shield=tray, rh=(8, -18), sword=dict(ang=15),
                 fx=[spr("question", 48, 4), spr("note", 2, 2)])
    seq = [final] + tween(final, 3, other, 3, final)[1:-1]
    return seq, an.split(2000, len(seq)), 2


def m_majika():   # まじか!?: のけぞって跳び上がり、剣が手から吹っ飛び、盾で顔を隠す
    final = pose(y=-6, tilt=14, squash=1.12, expr="surprised", lh=(-3, -16), rh=(10, -24),
                 sword=dict(free=True, gx=48, gy=10, ang=140), shield=dict(ang=0, w=1.0),
                 fx=[spr("exclaim_q", 3, 22), spr("sweats", 34, 14)])
    seq = [final, pose(expr="normal")]
    for i, (gx, gy, a) in enumerate([(36, 22, 30), (42, 14, 90), (48, 10, 150), (52, 8, 220), (50, 12, 290), (44, 20, 350)]):
        seq.append(pose(y=-6 + max(0, i - 2) * 2, tilt=14, squash=1.12, expr="surprised", lh=(-3, -16), rh=(10, -24),
                        sword=dict(free=True, gx=gx, gy=gy, ang=a), shield=dict(ang=0, w=1.0), fx=[spr("exclaim_q", 3, 22)]))
    seq += [pose(squash=0.75, expr="surprised", fx=[spr("sweats", 36, 8), puff(24)]), pose(expr="surprised"), final]
    return seq, an.split(2000, len(seq)), 2


def m_yossha():   # よっしゃー!: 剣を天に突き上げて跳び、稲妻が落ちて光り輝く
    final = pose(y=-6, squash=1.14, expr="kira", **UP, lh=(-10, -20), shield=dict(ang=-20, w=1.0),
                 fx=[bolt_to_tip(30, 0), bolt_to_tip(46, 0), burst(28, 4, 7, "rainbow"), GOLD_AURA, confetti(3)])
    crouch = pose(squash=0.72, expr="angry", rh=(8, -9), sword=dict(ang=60), lh=(-6, -9), fx=[GOLD_AURA])
    seq = [final] + tween(pose(), 1, crouch, 2, final, 1, with_fx(final, bolt_to_tip(20, 0), burst(28, 4, 10, "rainbow"),
                                                                  GOLD_AURA, confetti(5)), 1,
                          final) + [pose(squash=0.82, expr="happy", **UP, lh=(-10, -20), fx=[ring(24, 14), puff(24)]), final, final]
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
    grids = [render_grid(pose(expr=e, rh=(9, -13), sword=dict(ang=0, glow=True), fx=[GOLD_AURA]), phase=j)
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
