#!/usr/bin/env python3
"""杖をついた魔法使いの「動くスタンプ」ジェネレーター.

キャラを 体 / 腕 / 杖 の部品に分けたドット絵の人形として描き、
コマごとに姿勢 (ジャンプ・おじぎ・体の傾き・手と杖の角度) を変えて大きな動きを作る。
1 ドット = 5px の 64x54 ドットの画面に描いてから 5 倍に拡大するので、ドット感は崩れない。

使い方:
    python3 wizard_anim.py                     # wizard_stamps.json から生成
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
from make_stamps import MAIN_SIZE, TAB_SIZE
from sprites import CHARACTERS, EFFECTS, PALETTE

S = 5                    # 1 ドットの大きさ (px)
GW, GH = 64, 54          # 画面のドット数 (64x5=320, 54x5=270)
GROUND = 37              # 足元の高さ (ドット)
WINDOW = (10, 184, 310, 262)
STAFF_LEN = 24
CH = CHARACTERS["wizard"]
COLORS = {**PALETTE, **CH["colors"]}

ps.set_layout((GW * S, GH * S), window=WINDOW, sprite_scale=S, sprite_x=20, panel_min_w=150,
              effect_scale=S, panel_pad=14)


def col(c):
    return ps.rgba(COLORS.get(c, c))


# --- 姿勢 --------------------------------------------------------------------
# x, y   : 足元の位置 (y はマイナスで上に浮く)
# tilt   : 体の傾き (度、プラスで左に傾く)
# squash : 縦の伸び縮み (1.0 が普通)
# bow    : 頭を下げる量 (ドット)
# lh, rh : 左手・右手の位置 (足元からの相対ドット)
# staff  : 杖。hand で持つ手、ang は角度 (0 が真上、プラスで右に倒れる)、grip は握る位置 (下から何割)
#          free=True のときは手を離れて (gx, gy) の位置に浮く
IDLE = dict(x=24, y=0, tilt=0, squash=1.0, bow=0, expr="normal",
            lh=(-5, -8), rh=(9, -12), staff=dict(hand="r", ang=0, grip=0.5), fx=[])


def pose(**kw):
    p = copy.deepcopy(IDLE)
    staff = kw.pop("staff", None)
    p.update(kw)
    if staff is not None:
        p["staff"] = {**IDLE["staff"], **staff} if not staff.get("free") else staff
    return p


def lerp(a, b, t):
    """2 つの姿勢の間を t (0〜1) で補間する。表情とエフェクトは後半で切り替える。"""
    def mix(u, v):
        if isinstance(u, (int, float)) and isinstance(v, (int, float)):
            return u + (v - u) * t
        if isinstance(u, tuple) and isinstance(v, tuple):
            return tuple(mix(x, y) for x, y in zip(u, v))
        return v if t >= 0.5 else u
    p = {k: mix(a[k], b[k]) for k in a if k not in ("staff", "fx")}
    sa, sb = a["staff"], b["staff"]
    if sa.get("free") == sb.get("free") and sa.get("hand") == sb.get("hand"):
        p["staff"] = {k: mix(sa.get(k, sb[k]), sb[k]) for k in sb}
    else:
        p["staff"] = sb if t >= 0.5 else sa
    p["fx"] = b["fx"] if t >= 0.5 else a["fx"]
    return p


def tween(*keys):
    """tween(姿勢, コマ数, 姿勢, コマ数, ..., 姿勢) → 間を補間した姿勢のリスト (最後の姿勢を含む)。"""
    out = []
    for i in range(0, len(keys) - 1, 2):
        a, n, b = keys[i], keys[i + 1], keys[i + 2]
        for j in range(n):
            out.append(lerp(a, b, j / n))
    out.append(keys[-1])
    return out


# --- 描画 --------------------------------------------------------------------
def rot(dx, dy, deg):
    a = math.radians(deg)
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


# 魔法使いは顔が小さいので専用の表情 (目は 1〜2 ドット)。(x, y, 色) のリスト
_EL, _ER = 6, 10
FACES = {
    "normal":    [(_EL, 11, "E"), (_ER, 11, "E")],
    "smile":     [(_EL, 11, "E"), (_ER, 11, "E")],
    "calm":      [(5, 12, "E"), (6, 12, "E"), (10, 12, "E"), (11, 12, "E")],
    "sleep":     [(5, 12, "E"), (6, 12, "E"), (10, 12, "E"), (11, 12, "E"), (8, 14, "K")],
    "happy":     [(5, 12, "E"), (6, 12, "E"), (10, 12, "E"), (11, 12, "E"), (7, 14, "R"), (8, 14, "R")],
    "wink":      [(_EL, 11, "E"), (10, 12, "E"), (11, 12, "E"), (7, 14, "R"), (8, 14, "R")],
    "surprised": [(_EL, 11, "E"), (_EL, 12, "E"), (_ER, 11, "E"), (_ER, 12, "E"), (7, 14, "K"), (8, 14, "K")],
    "kira":      [(_EL, 11, "Y"), (_EL, 12, "Y"), (_ER, 11, "Y"), (_ER, 12, "Y"), (7, 14, "R"), (8, 14, "R")],
    "sad":       [(_EL, 12, "E"), (_ER, 12, "E"), (_EL, 13, "L"), (_ER, 13, "L")],
    "angry":     [(_EL, 11, "E"), (_ER, 11, "E"), (7, 10, "K"), (8, 10, "K"), (7, 14, "K"), (8, 14, "K")],
    "love":      [(_EL, 11, "R"), (_EL, 12, "R"), (_ER, 11, "R"), (_ER, 12, "R"), (7, 14, "R"), (8, 14, "R")],
}


def wizard_sprite(expr):
    grid = [list(r) for r in CH["pixels"]]
    for x, y, c in FACES[expr]:
        grid[y][x] = c
    return ps.pixels_to_image(["".join(r) for r in grid], COLORS)


def body_image(p):
    img = wizard_sprite(p["expr"])
    bow = round(p["bow"])
    if bow:  # 帽子を前に深く下げて目元を隠し、おじぎや うなずき に見せる
        hat = img.crop((0, 0, img.width, 10))
        body = img.crop((0, 10, img.width, img.height))
        img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        img.alpha_composite(body, (0, 10))
        img.alpha_composite(hat, (0, bow))
    if p["squash"] != 1.0:
        img = img.resize((img.width, max(4, round(img.height * p["squash"]))), Image.NEAREST)
    return img


def draw_line(d, a, b, outline, inner, w=1):
    d.line([a, b], fill=col(outline), width=w + 2)
    d.line([a, b], fill=col(inner), width=w)


def draw_staff(d, grip, ang, frac, glow=False):
    ux, uy = math.sin(math.radians(ang)), -math.cos(math.radians(ang))
    up = STAFF_LEN * (1 - frac)
    # 杖の先 (宝玉) が画面の外に出るときは、手の中で杖をずらして画面内に収める
    limits = []
    if uy < -0.05:
        limits.append((grip[1] - 3) / -uy)
    if ux > 0.05:
        limits.append((GW - 4 - grip[0]) / ux)
    if ux < -0.05:
        limits.append((grip[0] - 3) / -ux)
    up = max(4, min([up] + limits))
    top = (grip[0] + ux * up, grip[1] + uy * up)
    bot = (grip[0] - ux * (STAFF_LEN - up), grip[1] - uy * (STAFF_LEN - up))
    draw_line(d, bot, top, "K", "#8A5A32")
    tx, ty = round(top[0]), round(top[1])
    d.ellipse([tx - 2, ty - 2, tx + 2, ty + 2], fill=col("K"))
    d.rectangle([tx - 1, ty - 1, tx + 1, ty + 1], fill=col("#6FE3FF"))
    d.point((tx - 1, ty - 1), fill=col("W"))
    if glow:
        for dx, dy in ((0, -4), (0, 4), (-4, 0), (4, 0)):
            d.point((tx + dx, ty + dy), fill=col("#FFF7B0"))
    return top


def draw_fx(img, d, fx):
    for e in fx:
        kind = e.get("type", "sprite")
        if kind == "sprite":
            pat = ps.pixels_to_image(EFFECTS[e["name"]])
            img.alpha_composite(pat, (round(e["x"]), round(e["y"])))
        elif kind == "dots":  # キラキラの粒・軌跡
            for x, y in e["pts"]:
                d.point((round(x), round(y)), fill=col(e.get("color", "#FFE680")))
        elif kind == "plus":  # 小さな十字のきらめき
            for x, y in e["pts"]:
                x, y = round(x), round(y)
                c = col(e.get("color", "#FFE680"))
                d.point([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=c)
        elif kind == "ring":  # 地面の衝撃波
            x, y, r = e["x"], e["y"], e["r"]
            d.ellipse([x - r, y - r / 3, x + r, y + r / 3], outline=col(e.get("color", "#6FE3FF")))
        elif kind == "lines":  # 動きの線
            for x0, y0, x1, y1 in e["segs"]:
                d.line([(x0, y0), (x1, y1)], fill=col(e.get("color", "W")))


def render_grid(p):
    """姿勢 p を 64x54 ドットの画像に描く。"""
    g = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    ax, ay = p["x"], GROUND + p["y"]

    body = body_image(p)
    tmp = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    tmp.alpha_composite(body, (24 - body.width // 2, 44 - body.height))
    if p["tilt"]:
        tmp = tmp.rotate(p["tilt"], resample=Image.NEAREST, center=(24, 44))
    g.alpha_composite(tmp, (round(ax) - 24, round(ay) - 44))

    def world(rel):
        dx, dy = rot(rel[0], rel[1], p["tilt"])
        return ax + dx, ay + dy

    shoulders = [world((sx - 8, (sy - 28) * p["squash"])) for sx, sy in CH["shoulders"]]
    hands = {"l": world(p["lh"]), "r": world(p["rh"])}

    st = p["staff"]
    if st.get("free"):
        draw_staff(d, (st["gx"], st["gy"]), st["ang"], st.get("grip", 0.5), st.get("glow"))
    else:
        draw_staff(d, hands[st["hand"]], st["ang"] + p["tilt"] * 0, st["grip"], st.get("glow"))

    for sh, hk in zip(shoulders, ("l", "r")):
        draw_line(d, sh, hands[hk], "K", "U", w=2)
    # 縁取りを先に全部描いてから肌色を塗る (両手を合わせたときに 1 つの塊に見えるように)
    for h in hands.values():
        hx, hy = round(h[0]), round(h[1])
        d.rectangle([hx - 1, hy - 1, hx + 2, hy + 2], fill=col("K"))
    for h in hands.values():
        hx, hy = round(h[0]), round(h[1])
        d.rectangle([hx, hy, hx + 1, hy + 1], fill=col("S"))

    draw_fx(g, d, p["fx"])
    return g


def render(p, text, style):
    img = Image.new("RGBA", (GW * S, GH * S), (0, 0, 0, 0))
    ps.draw_window(img, style)
    x0, y0, x1, y1 = WINDOW
    t = ps.pixel_text(text, style.get("text", "#FFFFFF"), style.get("shadow", "#0A0D3A"))
    k = max(1, min((x1 - x0 - 28) // t.width, (y1 - y0 - 24) // t.height, 3))
    t = ps.scaled(t, k)
    img.alpha_composite(t, ((x0 + x1 - t.width) // 2, (y0 + y1 - t.height) // 2 + 2))
    img.alpha_composite(ps.scaled(render_grid(p), S))
    return img


# --- エフェクトの部品 --------------------------------------------------------
def spr(name, x, y):
    return {"name": name, "x": x, "y": y}


def burst(x, y, r, color="#FFE680", n=8):
    return {"type": "plus", "color": color,
            "pts": [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]}


def arc_pts(cx, cy, r, a0, a1, n):
    return [(cx + r * math.sin(math.radians(a0 + (a1 - a0) * i / max(1, n - 1))),
             cy - r * math.cos(math.radians(a0 + (a1 - a0) * i / max(1, n - 1)))) for i in range(n)]


def speed(x, y, n=3, length=6, gap=3, left=True):
    s = -1 if left else 1
    return {"type": "lines", "segs": [(x, y + i * gap, x + s * length, y + i * gap) for i in range(n)]}


# --- 動き (24 種) ------------------------------------------------------------
# どれも (姿勢のリスト, 各コマの ms, ループ回数) を返す。1 コマ目は完成形。
HOLD_UP = dict(lh=(-3, -26), rh=(3, -27))          # 両手を頭の上に
CHEST = dict(lh=(-1, -10), rh=(1, -10))            # 胸の前で手を合わせる


def m_thanks():   # ありがとう: 杖を頭上でくるっと回してから深くおじぎ
    final = pose(bow=4, squash=0.92, expr="calm", lh=(-4, -11), rh=(5, -11),
                 staff=dict(hand="r", ang=90, grip=0.6), fx=[burst(24, 6, 6), spr("sparkle", 38, 2)])
    up = pose(y=-2, squash=1.05, expr="happy", **HOLD_UP, staff=dict(ang=0, grip=0.3, glow=True))
    seq = [final] + tween(pose(), 2, up, 1, pose(**HOLD_UP, y=-2, expr="happy", staff=dict(ang=90, grip=0.5, glow=True)), 1,
                          pose(**HOLD_UP, y=-2, expr="happy", staff=dict(ang=180, grip=0.5, glow=True)), 1,
                          pose(**HOLD_UP, y=-2, expr="happy", staff=dict(ang=270, grip=0.5, glow=True)), 1,
                          up, 3, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_morning():  # おはよう: 杖を持って大きく伸び、左右に体をそらす
    final = pose(y=-1, squash=1.08, expr="happy", **HOLD_UP, staff=dict(ang=0, grip=0.3, glow=True),
                 fx=[burst(30, 2, 5), spr("sparkle", 44, 6)])
    left = pose(y=-1, squash=1.08, tilt=12, expr="calm", **HOLD_UP, staff=dict(ang=-20, grip=0.3))
    right = pose(y=-1, squash=1.08, tilt=-12, expr="calm", **HOLD_UP, staff=dict(ang=20, grip=0.3))
    seq = [final] + tween(pose(squash=0.9, expr="sleep"), 2, final, 2, left, 2, right, 2, final) + [final]
    return seq, an.split(3000, len(seq)), 1


def m_ok():       # OK!: 杖の先で空中に大きな丸を描く
    hand = (4, -22)
    final_pts = []
    seq = []
    angs = list(range(-30, 331, 30))
    for a in angs:
        tip = (24 + hand[0] + math.sin(math.radians(a)) * 13, GROUND + hand[1] - math.cos(math.radians(a)) * 13)
        final_pts.append(tip)
        seq.append(pose(rh=hand, lh=(-6, -14), expr="smile", staff=dict(ang=a, grip=0.45, glow=True),
                        fx=[{"type": "plus", "pts": list(final_pts)}]))
    ring = [{"type": "plus", "pts": final_pts}, spr("sparkles", 46, 20)]
    final = pose(rh=hand, lh=(-6, -14), expr="wink", staff=dict(ang=330, grip=0.45, glow=True), fx=ring)
    seq = [final] + seq + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_roger():    # 了解!: しゃがんで力をためてから、杖を突き上げてジャンプ
    final = pose(y=-4, squash=1.08, expr="kira", lh=(-7, -14), rh=(3, -28), staff=dict(ang=0, grip=0.25, glow=True),
                 fx=[burst(27, 4, 6), spr("exclaim", 42, 6)])
    crouch = pose(squash=0.82, expr="angry", rh=(7, -9), lh=(-5, -7), staff=dict(ang=0, grip=0.6))
    land = pose(squash=0.94, expr="smile", lh=(-7, -14), rh=(3, -26), staff=dict(ang=0, grip=0.3, glow=True),
                fx=[{"type": "ring", "x": 24, "y": GROUND, "r": 12}])
    seq = [final] + tween(pose(), 2, crouch, 2, final, 2, land, 2, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_sorry():    # ごめんね: 杖を横に立てたまま、何度も深くおじぎ
    staff = dict(free=True, gx=37, gy=GROUND - 12, ang=0, grip=0.5)
    final = pose(bow=5, squash=0.88, tilt=0, expr="sad", **CHEST, staff=staff, fx=[spr("sweats", 34, 6)])
    up = pose(expr="sad", **CHEST, staff=staff, fx=[spr("sweat", 34, 8)])
    seq = [final] + tween(final, 2, up, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_otsukare():  # おつかれさま: 杖を大きく振って、癒やしのキラキラを降らせる
    pts = [(40 + 3 * i % 17, 8 + (7 * i) % 22) for i in range(10)]
    final = pose(tilt=-6, expr="smile", lh=(-6, -12), rh=(10, -20), staff=dict(ang=60, grip=0.4, glow=True),
                 fx=[{"type": "plus", "pts": pts}, spr("heart", 50, 4)])
    back = pose(tilt=8, expr="calm", lh=(-6, -12), rh=(-4, -24), staff=dict(ang=-60, grip=0.4, glow=True))
    mid = pose(tilt=0, expr="happy", lh=(-6, -12), rh=(3, -26), staff=dict(ang=0, grip=0.4, glow=True),
               fx=[{"type": "dots", "pts": arc_pts(27, 12, 16, -60, 0, 6)}])
    seq = [final] + tween(pose(), 2, back, 2, mid, 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_congrats():  # おめでとう: 杖を掲げて花火を打ち上げ、ぴょんと跳ねる
    def fw(r):
        return [burst(46, 10, r, "#FF8FA3"), burst(46, 10, r * 0.6, "#FFE680", 6), burst(14, 6, r * 0.8, "#6FE3FF")]
    final = pose(y=-3, squash=1.05, expr="happy", lh=(-8, -20), rh=(6, -26), staff=dict(ang=20, grip=0.3, glow=True),
                 fx=fw(7))
    seq = [final] + tween(pose(squash=0.88, expr="smile"), 2,
                          pose(y=-3, squash=1.05, expr="happy", lh=(-8, -20), rh=(6, -26),
                               staff=dict(ang=20, grip=0.3, glow=True), fx=fw(2)), 2,
                          pose(y=-3, squash=1.05, expr="happy", lh=(-8, -20), rh=(6, -26),
                               staff=dict(ang=20, grip=0.3, glow=True), fx=fw(5)), 2, final, 2,
                          pose(squash=0.94, expr="happy", lh=(-8, -20), rh=(6, -24), staff=dict(ang=20, grip=0.35), fx=fw(8)), 2,
                          final)
    return seq, an.split(3000, len(seq)), 1


def m_goodnight():  # おやすみ: 杖にもたれて、こっくりこっくり
    final = pose(tilt=-10, bow=2, expr="sleep", lh=(4, -12), rh=(8, -13), staff=dict(ang=0, grip=0.55),
                 fx=[spr("zzz", 38, 2)])
    awake = pose(tilt=-4, expr="calm", lh=(4, -12), rh=(8, -13), staff=dict(ang=0, grip=0.55), fx=[spr("zzz", 38, 5)])
    seq = [final] + tween(final, 3, awake, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def walk(x, i, **kw):
    """歩きのコマ: 体を上下させ、杖を前後に振る。"""
    ph = i % 2
    return pose(x=x, y=-ph, tilt=(4 if ph else -4), staff=dict(ang=(-15 if ph else 15), grip=0.5),
                rh=(8, -13 + ph), **kw)


def m_ittekimasu():  # いってきます: 手を振ってから、杖をついて歩いて出ていく
    wave_up = pose(expr="happy", lh=(-9, -24))
    wave_dn = pose(expr="happy", lh=(-11, -18))
    final = pose(expr="happy", lh=(-9, -24), fx=[spr("note", 6, 6)])
    walk_out = [walk(24 + 6 * i, i, expr="smile", lh=(-6, -10)) for i in range(1, 8)]
    walk_in = [walk(-6 + 6 * i, i, expr="smile", lh=(-6, -10)) for i in range(1, 5)]
    seq = [final, wave_dn, wave_up, wave_dn] + walk_out + walk_in + [final]
    return seq, an.split(4000, len(seq)), 1


def m_tadaima():  # ただいま: 歩いて帰ってきて、杖と手を挙げる
    final = pose(y=-2, squash=1.05, expr="happy", lh=(-9, -24), rh=(5, -24), staff=dict(ang=10, grip=0.35, glow=True),
                 fx=[burst(30, 4, 5), spr("note", 44, 8)])
    seq = [final] + [walk(-4 + 5 * i, i, expr="smile", lh=(-6, -10)) for i in range(1, 7)] + \
        tween(pose(squash=0.88, expr="smile"), 2, final)[0:] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_ganbare():  # がんばれ!: 杖を頭の上で左右に大きく振って応援
    l = pose(y=-1, tilt=10, expr="happy", lh=(-8, -22), rh=(2, -27), staff=dict(ang=-45, grip=0.35, glow=True),
             fx=[spr("sparkle", 6, 2), speed(50, 8, left=False)])
    r = pose(y=-1, tilt=-10, expr="happy", lh=(-8, -22), rh=(6, -27), staff=dict(ang=45, grip=0.35, glow=True),
             fx=[spr("sparkle", 44, 2), speed(12, 8)])
    seq = tween(r, 3, l, 3, r)[:-1]
    return seq, an.split(1000, len(seq)), 3


def m_sugoi():    # すごい!: 杖を振り上げて地面をドン! 衝撃波が広がる
    lift = pose(y=-3, squash=1.06, expr="surprised", lh=(-6, -20), rh=(7, -24),
                staff=dict(ang=0, grip=0.2, glow=True))
    slam = pose(squash=0.86, expr="kira", lh=(-6, -12), rh=(8, -12), staff=dict(ang=0, grip=0.55, glow=True),
                fx=[{"type": "ring", "x": 33, "y": GROUND, "r": 10}, spr("exclaim", 44, 6), burst(33, 30, 7)])
    wave = copy.deepcopy(slam)
    wave["fx"] = [{"type": "ring", "x": 33, "y": GROUND, "r": 16}, spr("exclaim", 44, 6), burst(33, 30, 11)]
    seq = [slam] + tween(pose(), 2, lift, 1, slam, 1, wave, 2, lift, 1, slam, 1, wave)
    return seq, an.split(3000, len(seq)), 1


def m_iine():     # いいね!: 杖をバトンのようにくるくる回して、決めポーズ
    final = pose(tilt=-5, expr="wink", lh=(-8, -20), rh=(9, -18), staff=dict(ang=45, grip=0.5, glow=True),
                 fx=[spr("sparkles", 44, 2)])
    spin = [pose(expr="happy", rh=(6, -16), staff=dict(ang=a, grip=0.5, glow=True),
                 fx=[{"type": "dots", "pts": arc_pts(30, GROUND - 16, 12, a - 90, a, 5)}]) for a in range(0, 720, 60)]
    seq = [final] + spin + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_yoroshiku():  # よろしく: 杖を振ってあいさつしてから、ていねいにおじぎ
    final = pose(bow=3, squash=0.94, expr="calm", **CHEST, staff=dict(free=True, gx=36, gy=GROUND - 12, ang=0),
                 fx=[spr("sparkle", 44, 4)])
    w1 = pose(expr="smile", rh=(6, -24), staff=dict(ang=30, grip=0.35, glow=True))
    w2 = pose(expr="smile", rh=(2, -24), staff=dict(ang=-30, grip=0.35, glow=True))
    seq = [final] + tween(pose(), 1, w1, 1, w2, 1, w1, 1, w2, 2,
                          pose(expr="calm", **CHEST, staff=dict(free=True, gx=36, gy=GROUND - 12, ang=0)), 2,
                          final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_onegai():   # おねがい: 杖を抱えて手を合わせ、ぴょこぴょこ跳ねる
    st = dict(hand="r", ang=-10, grip=0.5)
    final = pose(expr="kira", **CHEST, staff=st, fx=[spr("hearts", 38, 4)])
    hop = pose(y=-3, squash=1.05, expr="kira", **CHEST, staff=st, fx=[spr("hearts", 38, 1)])
    seq = [final] + tween(pose(squash=0.9, expr="kira", **CHEST, staff=st, fx=[spr("hearts", 38, 4)]), 1, hop, 2, final)
    return seq, an.split(1000, len(seq)), 3


def m_matte():    # ちょっと待って: 体を乗り出して、杖をビシッと前に突き出す
    final = pose(x=22, tilt=-12, expr="surprised", lh=(-10, -20), rh=(12, -16), staff=dict(ang=80, grip=0.25, glow=True),
                 fx=[spr("exclaim", 50, 4), speed(58, 20, left=False)])
    back = pose(x=20, tilt=10, expr="surprised", lh=(-8, -14), rh=(-2, -16), staff=dict(ang=-40, grip=0.4))
    seq = [final] + tween(pose(), 2, back, 2, final) + [lerp(final, back, 0.2), final] + [final] * 2
    return seq, an.split(2000, len(seq)), 2


def m_shouchi():  # 承知しました: 杖を胸に立てて、うやうやしくおじぎ
    st = dict(hand="r", ang=0, grip=0.55)
    final = pose(bow=4, squash=0.92, expr="calm", lh=(1, -13), rh=(4, -13), staff=st, fx=[burst(28, 8, 4)])
    seq = [final] + tween(pose(staff=st, rh=(9, -12)), 2, pose(expr="calm", lh=(1, -13), rh=(4, -13), staff=st), 2,
                          final, 3, final)[:-1] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_wahaha():   # わはは!: おなかを抱えて、のけぞって大笑い
    back = pose(tilt=14, y=-1, expr="happy", lh=(-3, -10), rh=(8, -13), staff=dict(ang=-10, grip=0.55),
                fx=[spr("note", 2, 4), speed(44, 6, left=False)])
    fwd = pose(tilt=-8, bow=2, expr="happy", lh=(-3, -10), rh=(8, -12), staff=dict(ang=5, grip=0.55),
               fx=[spr("note", 46, 6)])
    seq = tween(back, 3, fwd, 3, back)[:-1]
    return seq, an.split(1000, len(seq)), 3


def m_eh():       # えっ!?: 驚いて飛び上がり、杖が手から飛んでいく
    final = pose(y=-6, squash=1.1, expr="surprised", lh=(-9, -24), rh=(9, -24),
                 staff=dict(free=True, gx=44, gy=6, ang=135), fx=[spr("exclaim_q", 4, 2)])
    seq = [final, pose(expr="normal")]
    for i, (gx, gy, a) in enumerate([(33, 20, 30), (38, 12, 80), (44, 6, 135), (47, 4, 200), (46, 8, 270),
                                      (40, 16, 330)]):
        seq.append(pose(y=-6 + i, squash=1.1, expr="surprised", lh=(-9, -24), rh=(9, -24),
                        staff=dict(free=True, gx=gx, gy=gy, ang=a), fx=[spr("exclaim_q", 4, 2)]))
    seq += [pose(squash=0.9, expr="surprised", staff=dict(ang=0, grip=0.5), fx=[spr("sweats", 36, 8)]),
            pose(expr="surprised", fx=[spr("sweats", 36, 8)]), final]
    return seq, an.split(2000, len(seq)), 2


def m_daijoubu():  # 大丈夫?: 前に乗り出して、杖をそっと差し出す
    final = pose(x=26, tilt=-10, bow=2, expr="sad", lh=(-4, -12), rh=(12, -12), staff=dict(ang=110, grip=0.3),
                 fx=[spr("sweat", 16, 4), spr("question", 48, 2)])
    seq = [final] + [walk(14 + 3 * i, i, expr="sad", lh=(-6, -10)) for i in range(1, 5)] + \
        tween(pose(x=26, expr="sad"), 3, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_odaiji():   # お大事に: 杖を掲げてゆらゆら、ハートの回復魔法
    def hearts(o):
        return [spr("heart", 44, 14 - o), spr("heart", 6, 18 - o), burst(30, 4, 4 + o / 2, "#FF8FA3")]
    final = pose(tilt=-6, expr="calm", lh=(-7, -18), rh=(5, -25), staff=dict(ang=10, grip=0.3, glow=True), fx=hearts(4))
    a = pose(tilt=6, expr="calm", lh=(-7, -18), rh=(3, -25), staff=dict(ang=-10, grip=0.3, glow=True), fx=hearts(0))
    seq = [final] + tween(a, 3, final, 3, a)[1:-1]
    return seq, an.split(2000, len(seq)), 2


def m_tanoshimi():  # 楽しみ!: 杖を掲げてぴょんぴょん連続ジャンプ
    up = pose(y=-6, squash=1.08, expr="kira", lh=(-9, -24), rh=(5, -26), staff=dict(ang=15, grip=0.3, glow=True),
              fx=[spr("note", 44, 4), spr("note", 4, 10)])
    dn = pose(squash=0.86, expr="happy", lh=(-9, -18), rh=(6, -20), staff=dict(ang=15, grip=0.4),
              fx=[spr("note", 44, 8), spr("note", 4, 6)])
    seq = tween(up, 3, dn, 2, up)[:-1]
    return seq, an.split(1000, len(seq)), 3


def m_kaeru():    # 今から帰る: 杖にまたがって空を飛んで帰る
    def fly(x, y, i):  # 杖を腰の下に通してまたがり、前の方を両手でつかむ
        return pose(x=x, y=y, tilt=-8, squash=0.85, expr="happy", lh=(5, -8), rh=(9, -9),
                    staff=dict(free=True, gx=x + 2, gy=GROUND + y - 5, ang=96, grip=0.45),
                    fx=[speed(x - 12, GROUND + y - 14, n=3, length=8)])
    final = fly(26, -6, 0)
    final["fx"].append(spr("sparkle", 46, 2))
    seq = [final] + [fly(-10 + 6 * i, -2 - (i % 2) - i // 2, i) for i in range(1, 12)] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_naruhodo():  # なるほど: 杖をトンと突きながら、深くうなずく
    final = pose(bow=2, expr="calm", rh=(9, -13), staff=dict(ang=0, grip=0.5),
                 fx=[burst(24, 3, 4), spr("exclaim", 40, 4)])
    up = pose(expr="normal", rh=(9, -15), staff=dict(ang=0, grip=0.5), fx=[])
    nod = pose(bow=3, squash=0.95, expr="calm", rh=(9, -12), staff=dict(ang=0, grip=0.5),
               fx=[{"type": "ring", "x": 33, "y": GROUND, "r": 5}])
    seq = [final] + tween(up, 2, nod, 2, up, 2, nod, 2, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


MOTIONS = {
    "thanks": m_thanks, "morning": m_morning, "ok": m_ok, "roger": m_roger, "sorry": m_sorry,
    "otsukare": m_otsukare, "congrats": m_congrats, "goodnight": m_goodnight, "ittekimasu": m_ittekimasu,
    "tadaima": m_tadaima, "ganbare": m_ganbare, "sugoi": m_sugoi, "iine": m_iine, "yoroshiku": m_yoroshiku,
    "onegai": m_onegai, "matte": m_matte, "shouchi": m_shouchi, "wahaha": m_wahaha, "eh": m_eh,
    "daijoubu": m_daijoubu, "odaiji": m_odaiji, "tanoshimi": m_tanoshimi, "kaeru": m_kaeru,
    "naruhodo": m_naruhodo,
}


# --- 書き出し ----------------------------------------------------------------
def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = cfg_path.parent / cfg.get("output", "output_wizard")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    style = cfg.get("window", {})

    problems, all_frames = [], []
    for i, item in enumerate(cfg["stamps"], 1):
        poses, ms, loops = MOTIONS[item["motion"]]()
        if len(poses) > 20:  # LINE の上限 20 フレームに収める
            raise SystemExit(f"{item['motion']}: フレーム数 {len(poses)} が 20 を超えています")
        imgs = [render(p, item["text"], style) for p in poses]
        path = out / f"{i:02d}.png"
        an.save_apng(imgs, ms, loops, path)
        all_frames.append((imgs, ms, loops))
        info, errs = an.check_anim(path, "stamp")
        problems += [f"{path.name}: {e}" for e in errs]
        print(f"  {path.name}  {item['motion']:<10} {info['frames']:>2}f {info['ms'] * info['loops']:>4}ms "
              f"{info['bytes'] // 1024:>3}KB  {item['text']!r}")

    # メイン画像 (240x240、48x48 ドット): 杖をついてまばたき、杖の先が光る
    grids = [render_grid(pose(x=24, expr=expr, staff=dict(ang=0, grip=0.5, glow=j % 4 < 2)))
             for j, expr in enumerate(["smile"] * 5 + ["calm"] + ["smile"] * 4)]
    box = grids[0].getbbox()  # 光っているコマの範囲でそろえて、コマごとに位置がずれないようにする
    k = min((MAIN_SIZE[0] - 20) // (box[2] - box[0]), (MAIN_SIZE[1] - 20) // (box[3] - box[1]))
    mains = []
    for g in grids:
        big = ps.scaled(g.crop(box), k)
        canvas = Image.new("RGBA", MAIN_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(big, ((MAIN_SIZE[0] - big.width) // 2, (MAIN_SIZE[1] - big.height) // 2))
        mains.append(canvas)
    an.save_apng(mains, an.split(2000, len(mains)), 2, out / "main.png")
    problems += [f"main.png: {e}" for e in an.check_anim(out / "main.png", "main")[1]]
    ps.fit_square(render_grid(pose(x=22, expr="smile")), TAB_SIZE, 2).save(out / "tab.png")

    an.make_preview_gif(all_frames, cfg_path.parent / cfg.get("preview", "preview_wizard.gif"))
    zip_path = cfg_path.parent / f"{cfg.get('name', 'wizard_anim_stamp')}.zip"
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
    ap = argparse.ArgumentParser(description="杖をついた魔法使いの動くスタンプ")
    ap.add_argument("-c", "--config", default="wizard_stamps.json")
    build(ap.parse_args().config)


if __name__ == "__main__":
    main()
