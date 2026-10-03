#!/usr/bin/env python3
"""杖をついた魔法使いの「動くスタンプ」ジェネレーター.

キャラを 体 / 腕 / 杖 の部品に分けたドット絵の人形として描き、
コマごとに姿勢 (ジャンプ・おじぎ・体の傾き・空中回転・手と杖の角度) を変えて大きな動きを作る。
杖は木目と節のある木の杖で、振ると宝玉が光の軌跡を残す。魔法陣・稲妻・光の粒などの魔法表現付き。
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

# 木の杖と魔法の色
WOOD_DARK, WOOD, WOOD_LIGHT, WOOD_KNOT = "#4A2A12", "#7A4A22", "#B07A45", "#3A200C"
LEAF = "#6CBF4A"
ORB, ORB_LIGHT = "#6FE3FF", "#E8FFFF"
CYAN, VIOLET, PINK, GOLD, WHITE = "#6FE3FF", "#B07CFF", "#FF8FD8", "#FFE680", "#FFFFFF"
RAINBOW = [GOLD, PINK, CYAN, VIOLET, "#9CFF8F"]

ps.set_layout((GW * S, GH * S), window=WINDOW, sprite_scale=S, sprite_x=20, panel_min_w=150,
              effect_scale=S, panel_pad=14)


def col(c):
    return ps.rgba(COLORS.get(c, c))


# --- 姿勢 --------------------------------------------------------------------
# x, y   : 足元の位置 (y はマイナスで上に浮く)
# tilt   : 体の傾き (度、プラスで左に傾く)
# squash : 縦の伸び縮み (1.0 が普通)
# sx     : 横の幅 (1.0 が普通、マイナスで左右反転)。1 → 0.3 → -0.3 → -1 と変えると空中で回転して見える
# bow    : 帽子を下げる量 (ドット)。おじぎ・うなずき
# hat    : 帽子が頭から飛んでいるとき (dx, dy, 角度)
# lh, rh : 左手・右手の位置 (足元からの相対ドット)
# staff  : 杖。hand で持つ手、ang は角度 (0 が真上、プラスで右に倒れる)、grip は握る位置 (下から何割)、
#          glow で宝玉が光る。free=True のときは手を離れて (gx, gy) の位置に浮く
IDLE = dict(x=24, y=0, tilt=0, squash=1.0, sx=1.0, bow=0, hat=None, expr="normal",
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
        if isinstance(u, bool) or isinstance(v, bool):
            return v if t >= 0.5 else u
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


def with_fx(p, *fx):
    q = copy.deepcopy(p)
    q["fx"] = list(fx)
    return q


# --- 体 ----------------------------------------------------------------------
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
HAT_ROWS = 10  # 帽子は 0〜9 行目


def wizard_sprite(expr, hatless=False):
    grid = [list(r) for r in CH["pixels"]]
    for x, y, c in FACES[expr]:
        grid[y][x] = c
    if hatless:  # 帽子がないときは白い髪の頭を見せる
        for y in range(HAT_ROWS):
            grid[y] = list("." * 16)
        grid[8] = list("....KKKKKKKK....")
        grid[9] = list("...KWWWWWWWWK...")
    return ps.pixels_to_image(["".join(r) for r in grid], COLORS)


def hat_image():
    return wizard_sprite("normal").crop((0, 0, 16, HAT_ROWS))


def body_image(p):
    img = wizard_sprite(p["expr"], hatless=p["hat"] is not None)
    bow = round(p["bow"])
    if bow and p["hat"] is None:  # 帽子を前に深く下げて目元を隠し、おじぎや うなずき に見せる
        hat = img.crop((0, 0, img.width, HAT_ROWS))
        body = img.crop((0, HAT_ROWS, img.width, img.height))
        img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        img.alpha_composite(body, (0, HAT_ROWS))
        img.alpha_composite(hat, (0, bow))
    w = max(2, round(img.width * abs(p["sx"])))
    h = max(4, round(img.height * p["squash"]))
    if (w, h) != img.size:
        img = img.resize((w, h), Image.NEAREST)
    if p["sx"] < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def geometry(p):
    """姿勢から、肩・手・杖の両端の位置 (ドット) を計算する。"""
    ax, ay = p["x"], GROUND + p["y"]

    def world(rel):
        dx, dy = rot(rel[0] * (1 if p["sx"] >= 0 else -1), rel[1], p["tilt"])
        return ax + dx, ay + dy

    shoulders = [world(((sx - 8) * abs(p["sx"]), (sy - 28) * p["squash"])) for sx, sy in CH["shoulders"]]
    hands = {"l": world(p["lh"]), "r": world(p["rh"])}
    st = p["staff"]
    grip = (st["gx"], st["gy"]) if st.get("free") else hands[st["hand"]]
    ang, frac = st["ang"], st.get("grip", 0.5)
    ux, uy = math.sin(math.radians(ang)), -math.cos(math.radians(ang))
    up = STAFF_LEN * (1 - frac)
    # 杖の先 (宝玉) が画面の外に出るときは、手の中で杖をずらして画面内に収める
    limits = []
    if uy < -0.05:
        limits.append((grip[1] - 5) / -uy)
    if ux > 0.05:
        limits.append((GW - 5 - grip[0]) / ux)
    if ux < -0.05:
        limits.append((grip[0] - 4) / -ux)
    up = max(5, min([up] + limits))
    top = (grip[0] + ux * up, grip[1] + uy * up)
    bot = (grip[0] - ux * (STAFF_LEN - up), grip[1] - uy * (STAFF_LEN - up))
    orb = (top[0] + ux * 2, top[1] + uy * 2)
    return dict(anchor=(ax, ay), shoulders=shoulders, hands=hands, top=top, bot=bot, orb=orb, u=(ux, uy))


# --- 木の杖 ------------------------------------------------------------------
def draw_staff(d, g, glow, phase):
    (bx, by), (tx, ty), (ux, uy) = g["bot"], g["top"], g["u"]
    nx, ny = -uy, ux  # 杖に垂直な向き
    # 太い木の柄: 輪郭 → 濃い木 → 明るい木目
    d.line([(bx, by), (tx, ty)], fill=col("K"), width=4)
    d.line([(bx, by), (tx, ty)], fill=col(WOOD), width=2)
    d.line([(bx + nx * 0.6, by + ny * 0.6), (tx + nx * 0.6, ty + ny * 0.6)], fill=col(WOOD_LIGHT), width=1)
    # 節 (こぶ) と木目の筋
    for f in (0.22, 0.55, 0.8):
        kx, ky = bx + (tx - bx) * f, by + (ty - by) * f
        d.point((round(kx - nx), round(ky - ny)), fill=col(WOOD_KNOT))
        d.point((round(kx + nx * 2), round(ky + ny * 2)), fill=col("K"))
        d.point((round(kx + nx * 1.2), round(ky + ny * 1.2)), fill=col(WOOD_DARK))
    # 先端: 2 本の枝が宝玉を包む。小さな葉っぱ付き
    for side in (-1, 1):
        a = math.atan2(uy, ux) + side * math.radians(40)
        ex, ey = tx + math.cos(a) * 3.5, ty + math.sin(a) * 3.5
        cx, cy = ex + ux * 1.8, ey + uy * 1.8
        d.line([(tx, ty), (ex, ey), (cx, cy)], fill=col("K"), width=3)
        d.line([(tx, ty), (ex, ey), (cx, cy)], fill=col(WOOD), width=1)
    lx, ly = tx + nx * 2.5 - ux * 2, ty + ny * 2.5 - uy * 2
    d.point([(round(lx), round(ly)), (round(lx + nx), round(ly + ny))], fill=col(LEAF))
    # 宝玉
    ox, oy = round(g["orb"][0]), round(g["orb"][1])
    d.ellipse([ox - 2, oy - 2, ox + 2, oy + 2], fill=col("K"))
    d.rectangle([ox - 1, oy - 1, ox + 1, oy + 1], fill=col(ORB))
    d.point((ox - 1, oy - 1), fill=col(ORB_LIGHT))
    if glow:  # 光の輪と、宝玉のまわりを回る光の粒
        r = 4 + (phase % 2)
        for i in range(8):
            a = 2 * math.pi * i / 8 + phase * 0.4
            if i % 2 == phase % 2:
                d.point((round(ox + r * math.cos(a)), round(oy + r * math.sin(a))), fill=col(WHITE))
        for i in range(3):
            a = phase * 0.9 + i * 2.1
            d.point((round(ox + 6 * math.cos(a)), round(oy + 6 * math.sin(a))), fill=col(RAINBOW[(i + phase) % 5]))


# --- 魔法のエフェクト --------------------------------------------------------
def magic_circle(d, x, y, r, phase):
    """足元の魔法陣 (2 重の楕円と、回るルーン文字の点)。"""
    y -= 2  # 文字のウィンドウにかからないよう、足元より少し上に平たく描く
    for rr, c in ((r, VIOLET), (r * 0.72, CYAN)):
        d.ellipse([x - rr, y - rr / 4, x + rr, y + rr / 4], outline=col(c))
    for i in range(10):
        a = 2 * math.pi * i / 10 + phase * 0.35
        px, py = x + r * 0.86 * math.cos(a), y + r * 0.86 / 4 * math.sin(a)
        d.point((round(px), round(py)), fill=col(GOLD if i % 2 else WHITE))
    for i in range(3):  # 中の三角形
        a1 = 2 * math.pi * i / 3 - phase * 0.3
        a2 = 2 * math.pi * (i + 1) / 3 - phase * 0.3
        d.line([(x + r * 0.7 * math.cos(a1), y + r * 0.7 / 4 * math.sin(a1)),
                (x + r * 0.7 * math.cos(a2), y + r * 0.7 / 4 * math.sin(a2))], fill=col(VIOLET))


def bolt(d, x0, y0, x1, y1, seed=0):
    """ギザギザの稲妻。"""
    pts = [(x0, y0)]
    n = 5
    for i in range(1, n):
        t = i / n
        off = (2.5 if (i + seed) % 2 else -2.5)
        nx, ny = -(y1 - y0), (x1 - x0)
        ln = math.hypot(nx, ny) or 1
        pts.append((x0 + (x1 - x0) * t + nx / ln * off, y0 + (y1 - y0) * t + ny / ln * off))
    pts.append((x1, y1))
    d.line(pts, fill=col(GOLD), width=3)
    d.line(pts, fill=col(WHITE), width=1)


def draw_fx(img, d, fx, g, phase, back):
    for e in fx:
        if bool(e.get("back")) != back:
            continue
        kind = e.get("type", "sprite")
        if kind == "sprite":
            img.alpha_composite(ps.pixels_to_image(EFFECTS[e["name"]]), (round(e["x"]), round(e["y"])))
        elif kind == "plus":  # 十字のきらめき (色は 1 色か虹色)
            for i, (x, y) in enumerate(e["pts"]):
                x, y = round(x), round(y)
                c = col(RAINBOW[(i + phase) % 5] if e.get("color") == "rainbow" else e.get("color", GOLD))
                d.point([(x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=c)
        elif kind == "dots":
            for i, (x, y) in enumerate(e["pts"]):
                c = RAINBOW[(i + phase) % 5] if e.get("color") == "rainbow" else e.get("color", GOLD)
                d.point((round(x), round(y)), fill=col(c))
        elif kind == "ring":  # 地面の衝撃波
            x, y, r = e["x"], e["y"] - 2, e["r"]
            d.ellipse([x - r, y - r / 4, x + r, y + r / 4], outline=col(e.get("color", CYAN)))
            if r > 6:
                d.ellipse([x - r + 3, y - r / 4 + 1, x + r - 3, y + r / 4 - 1], outline=col(WHITE))
        elif kind == "circle":
            magic_circle(d, e["x"], e["y"], e["r"], phase)
        elif kind == "bolt":
            x0, y0 = g["orb"] if e.get("from") == "orb" else (e["x0"], e["y0"])
            bolt(d, x0, y0, e["x1"], e["y1"], seed=phase)
        elif kind == "rays":  # 宝玉から放射状に伸びる光
            ox, oy = g["orb"]
            for i in range(e.get("n", 8)):
                a = 2 * math.pi * i / e.get("n", 8) + phase * 0.2
                r0, r1 = e.get("r0", 5), e.get("r1", 9)
                d.line([(ox + r0 * math.cos(a), oy + r0 * math.sin(a)), (ox + r1 * math.cos(a), oy + r1 * math.sin(a))],
                       fill=col(e.get("color", GOLD)))
        elif kind == "puff":  # 砂ぼこり
            for x, y, r in e["pts"]:
                d.ellipse([x - r, y - r, x + r, y + r], fill=col("#E8E2D0"), outline=col("#9A927E"))
        elif kind == "lines":  # 動きの線
            for x0, y0, x1, y1 in e["segs"]:
                d.line([(x0, y0), (x1, y1)], fill=col(e.get("color", WHITE)))
        elif kind == "aura":  # 体のまわりを立ちのぼる光の粒
            ax, ay = g["anchor"]
            for i in range(e.get("n", 8)):
                x = ax - 10 + (i * 7) % 21
                y = ay - ((phase * 3 + i * 5) % 26)
                d.point((round(x), round(y)), fill=col(RAINBOW[i % 5] if e.get("color") == "rainbow"
                                                          else e.get("color", CYAN)))


def draw_trail(d, tips):
    """杖の宝玉が通った跡 (古いほど暗い色の帯)。"""
    colors = [VIOLET, CYAN, WHITE]
    for i in range(len(tips) - 1):
        c = colors[max(0, len(colors) - (len(tips) - 1) + i)]
        d.line([tips[i], tips[i + 1]], fill=col(c), width=3 if i == len(tips) - 2 else 2)


def clamp(p):
    """高く跳びすぎて帽子が画面の上で切れないように、跳ぶ高さをおさえる。"""
    q = copy.deepcopy(p)
    head = 28 * q["squash"]
    q["y"] = max(q["y"], -(GROUND - 2 - head))
    if q["hat"] is not None:
        hdx, hdy, hang = q["hat"]
        q["hat"] = (hdx, max(hdy, -(GROUND + q["y"] - 28 * q["squash"]) + 1), hang)
    return q


def render_grid(p, phase=0, trail=()):
    """姿勢 p を 64x54 ドットの画像に描く。"""
    jumped = p["y"] <= -2
    p = clamp(p)
    gimg = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    d = ImageDraw.Draw(gimg)
    g = geometry(p)
    ax, ay = g["anchor"]
    draw_fx(gimg, d, p["fx"], g, phase, back=True)

    body = body_image(p)
    tmp = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    tmp.alpha_composite(body, (24 - body.width // 2, 44 - body.height))
    if p["tilt"]:
        tmp = tmp.rotate(p["tilt"], resample=Image.NEAREST, center=(24, 44))
    gimg.alpha_composite(tmp, (round(ax) - 24, round(ay) - 44))
    if p["hat"] is not None:  # 飛んでいる帽子
        hdx, hdy, hang = p["hat"]
        hat = hat_image().rotate(hang, resample=Image.NEAREST, expand=True)
        gimg.alpha_composite(hat, (round(ax - 8 + hdx), round(ay - 28 * p["squash"] + hdy)))

    if len(trail) >= 2:
        draw_trail(d, list(trail) + [g["orb"]])
    draw_staff(d, g, p["staff"].get("glow"), phase)
    for sh, hk in zip(g["shoulders"], ("l", "r")):
        d.line([sh, g["hands"][hk]], fill=col("K"), width=4)
        d.line([sh, g["hands"][hk]], fill=col("U"), width=2)
    # 縁取りを先に全部描いてから肌色を塗る (両手を合わせたときに 1 つの塊に見えるように)
    for h in g["hands"].values():
        hx, hy = round(h[0]), round(h[1])
        d.rectangle([hx - 1, hy - 1, hx + 2, hy + 2], fill=col("K"))
    for h in g["hands"].values():
        hx, hy = round(h[0]), round(h[1])
        d.rectangle([hx, hy, hx + 1, hy + 1], fill=col("S"))

    if jumped:  # 跳んでいるときは足の下に跳躍線
        for dx in (-4, 0, 4):
            x = round(ax + dx)
            d.line([(x, round(ay) + 2), (x, min(GROUND - 1, round(ay) + 5))], fill=col(WHITE))
    draw_fx(gimg, d, p["fx"], g, phase, back=False)
    return gimg


def render(p, text, style, phase=0, trail=()):
    img = Image.new("RGBA", (GW * S, GH * S), (0, 0, 0, 0))
    ps.draw_window(img, style)
    x0, y0, x1, y1 = WINDOW
    t = ps.pixel_text(text, style.get("text", "#FFFFFF"), style.get("shadow", "#0A0D3A"))
    k = max(1, min((x1 - x0 - 28) // t.width, (y1 - y0 - 24) // t.height, 3))
    t = ps.scaled(t, k)
    img.alpha_composite(t, ((x0 + x1 - t.width) // 2, (y0 + y1 - t.height) // 2 + 2))
    img.alpha_composite(ps.scaled(render_grid(p, phase, trail), S))
    return img


# --- エフェクトの部品 --------------------------------------------------------
def spr(name, x, y):
    return {"name": name, "x": x, "y": y}


def burst(x, y, r, color=GOLD, n=8):
    return {"type": "plus", "color": color,
            "pts": [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]}


def arc_pts(cx, cy, r, a0, a1, n):
    return [(cx + r * math.sin(math.radians(a0 + (a1 - a0) * i / max(1, n - 1))),
             cy - r * math.cos(math.radians(a0 + (a1 - a0) * i / max(1, n - 1)))) for i in range(n)]


def speed(x, y, n=3, length=6, gap=3, left=True, color=WHITE):
    s = -1 if left else 1
    return {"type": "lines", "color": color, "segs": [(x, y + i * gap, x + s * length, y + i * gap) for i in range(n)]}


def circle(x=24, r=14):
    return {"type": "circle", "x": x, "y": GROUND, "r": r, "back": True}


def ring(x, r, color=CYAN):
    return {"type": "ring", "x": x, "y": GROUND, "r": r, "color": color, "back": True}


def puff(x, side=1):
    return {"type": "puff", "pts": [(x - 6 * side, GROUND - 1, 2), (x - 9 * side, GROUND - 2, 1.5), (x + 6 * side, GROUND - 1, 1.5)]}


def confetti(seed, n=14):
    return {"type": "dots", "color": "rainbow",
            "pts": [((seed * 7 + i * 13) % 60 + 2, (seed * 5 + i * 9) % 26 + 1) for i in range(n)]}


AURA = {"type": "aura", "n": 9, "color": "rainbow"}
RAYS = {"type": "rays", "n": 8, "r0": 5, "r1": 9}


# --- 動き (24 種) ------------------------------------------------------------
# どれも (姿勢のリスト, 各コマの ms, ループ回数) を返す。1 コマ目は完成形。
HOLD_UP = dict(lh=(-4, -24), rh=(3, -25))          # 両手を頭の上に
CHEST = dict(lh=(-1, -10), rh=(1, -10))            # 胸の前で手を合わせる
GLOW_UP = dict(ang=0, grip=0.45, glow=True)


def spin_frames(base, n=4):
    """その場で 1 回転するコマ (横幅を縮めて裏返す)。"""
    out = []
    for i, sx in enumerate([0.5, -0.4, -1.0, -0.5, 0.4, 1.0][:n] if n < 6 else [0.5, -0.4, -1.0, -0.5, 0.4, 1.0]):
        q = copy.deepcopy(base)
        q["sx"] = sx
        out.append(q)
    return out


def m_thanks():   # ありがとう: しゃがむ → 回転ジャンプで杖を回す → 魔法陣の上で深くおじぎ
    final = pose(bow=5, squash=0.82, expr="calm", lh=(-4, -10), rh=(5, -10),
                 staff=dict(hand="r", ang=90, grip=0.6, glow=True),
                 fx=[circle(), burst(24, 4, 7, "rainbow"), spr("sparkle", 44, 2), AURA])
    crouch = pose(squash=0.78, expr="happy", **HOLD_UP, staff=dict(ang=0, grip=0.5))
    air = pose(y=-9, squash=1.15, expr="happy", **HOLD_UP, staff=dict(ang=0, grip=0.45, glow=True), fx=[AURA])
    seq = [final, crouch]
    for i, a in enumerate((60, 150, 240, 330)):
        q = copy.deepcopy(air)
        q["staff"]["ang"] = a
        q["sx"] = [0.4, -1.0, -0.4, 1.0][i]
        q["fx"] = [AURA, circle(r=8 + 2 * i)]
        seq.append(q)
    land = pose(squash=0.75, expr="happy", **HOLD_UP, staff=dict(ang=0, grip=0.5, glow=True),
                fx=[circle(), puff(24)])
    seq += [land] + tween(land, 2, final)[1:] + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_morning():  # おはよう: 全身で大きく伸び、左右に大きくそらして、杖から朝日の光
    final = pose(y=-2, squash=1.18, expr="happy", **HOLD_UP, staff=GLOW_UP,
                 fx=[RAYS, burst(30, 3, 7, "rainbow"), spr("sparkle", 46, 8)])
    yawn = pose(squash=0.8, bow=2, expr="sleep", lh=(-5, -6), rh=(8, -10), fx=[spr("zzz", 36, 6)])
    left = pose(y=-2, squash=1.15, tilt=22, expr="calm", **HOLD_UP, staff=dict(ang=-30, grip=0.45, glow=True), fx=[RAYS])
    right = pose(y=-2, squash=1.15, tilt=-22, expr="calm", **HOLD_UP, staff=dict(ang=30, grip=0.45, glow=True), fx=[RAYS])
    seq = [final] + tween(yawn, 2, final, 2, left, 2, right, 2, final) + [final]
    return seq, an.split(3000, len(seq)), 1


def m_ok():       # OK!: 体ごと振り回して、杖の先で空中に大きな光の丸を描く
    hand = (4, -20)
    pts, seq = [], []
    for a in range(-30, 331, 30):
        tip = (24 + hand[0] + math.sin(math.radians(a)) * 13, GROUND + hand[1] - math.cos(math.radians(a)) * 13)
        pts.append(tip)
        seq.append(pose(rh=hand, lh=(-7, -14), tilt=-math.sin(math.radians(a)) * 14, expr="smile",
                        staff=dict(ang=a, grip=0.45, glow=True),
                        fx=[{"type": "plus", "pts": list(pts), "color": "rainbow"}, circle(r=10)]))
    final = pose(rh=hand, lh=(-7, -14), tilt=-6, expr="wink", staff=dict(ang=330, grip=0.45, glow=True),
                 fx=[{"type": "plus", "pts": pts, "color": "rainbow"}, spr("sparkles", 46, 22), circle(r=10)])
    seq = [final] + seq + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_roger():    # 了解!: 深くしゃがんで力をため、高く飛んで杖を突き上げる → 稲妻!
    final = pose(y=-9, squash=1.15, expr="kira", lh=(-8, -16), rh=(3, -24), staff=dict(ang=0, grip=0.4, glow=True),
                 fx=[{"type": "bolt", "from": "orb", "x1": 40, "y1": 0}, {"type": "bolt", "from": "orb", "x1": 14, "y1": 0},
                     spr("exclaim", 46, 8), AURA])
    crouch = pose(squash=0.72, expr="angry", rh=(7, -8), lh=(-6, -6), staff=dict(ang=10, grip=0.6),
                  fx=[circle(r=10), AURA])
    land = pose(squash=0.78, expr="smile", lh=(-8, -14), rh=(3, -22), staff=dict(ang=0, grip=0.45, glow=True),
                fx=[ring(24, 14), puff(24)])
    seq = [final] + tween(pose(), 1, crouch, 2, final, 3, land, 2, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_sorry():    # ごめんね: 汗を飛ばしながら、何度も勢いよく深くおじぎ
    staff = dict(free=True, gx=40, gy=GROUND - 12, ang=-8, grip=0.5)
    final = pose(bow=6, squash=0.76, tilt=-6, expr="sad", **CHEST, staff=staff,
                 fx=[spr("sweats", 34, 4), spr("sweat", 10, 8)])
    up = pose(y=-2, squash=1.08, tilt=4, expr="sad", **CHEST, staff=staff, fx=[spr("sweat", 34, 6)])
    seq = [final] + tween(final, 2, up, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def m_otsukare():  # おつかれさま: 後ろから前へ杖を大きく振り抜き、癒やしの光とハートを降らせる
    pts = [(38 + (7 * i) % 22, 4 + (11 * i) % 24) for i in range(12)]
    final = pose(tilt=-18, x=26, expr="smile", lh=(-8, -12), rh=(11, -18), staff=dict(ang=75, grip=0.4, glow=True),
                 fx=[{"type": "plus", "pts": pts, "color": "rainbow"}, spr("heart", 50, 2), spr("heart", 40, 14), circle()])
    back = pose(tilt=20, x=22, squash=0.92, expr="calm", lh=(-6, -12), rh=(-6, -22), staff=dict(ang=-80, grip=0.4, glow=True),
                fx=[circle()])
    seq = [final] + tween(pose(), 2, back, 3, final) + [final] * 4
    return seq, an.split(3000, len(seq)), 1


def m_congrats():  # おめでとう: 回転ジャンプで花火を連発、紙吹雪
    def fw(r, seed):
        return [burst(48, 9, r, PINK), burst(48, 9, r * 0.55, GOLD, 6), burst(12, 6, r * 0.8, CYAN),
                burst(30, 2, r * 0.5, VIOLET, 6), confetti(seed)]
    up = dict(lh=(-9, -20), rh=(6, -24))
    final = pose(y=-8, squash=1.12, expr="happy", **up, staff=dict(ang=15, grip=0.4, glow=True), fx=fw(7, 0))
    seq = [final, pose(squash=0.75, expr="smile", fx=[AURA])]
    for i, sx in enumerate([0.5, -1.0, -0.5, 1.0]):
        q = pose(y=-8 - (i % 2) * 2, squash=1.12, sx=sx, expr="happy", **up, staff=dict(ang=15, grip=0.4, glow=True),
                 fx=fw(2 + i * 2, i))
        seq.append(q)
    seq += [pose(squash=0.8, expr="happy", **up, staff=dict(ang=15, grip=0.45), fx=fw(9, 5) + [puff(24)])]
    seq += tween(seq[-1], 2, final)[1:] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_goodnight():  # おやすみ: 杖に大きくもたれてこっくり → ハッと起きてまたこっくり
    final = pose(tilt=-20, x=22, bow=3, expr="sleep", lh=(6, -12), rh=(9, -13), staff=dict(ang=0, grip=0.55),
                 fx=[spr("zzz", 40, 2), {"type": "dots", "pts": [(36, 10), (38, 7)], "color": VIOLET}])
    awake = pose(y=-2, squash=1.08, tilt=-2, x=22, expr="surprised", lh=(4, -14), rh=(9, -14),
                 staff=dict(ang=0, grip=0.55), fx=[spr("exclaim", 40, 6)])
    seq = [final] + tween(final, 3, awake, 1, awake, 2, final)[1:]
    return seq, an.split(1000, len(seq)), 3


def run(x, i, **kw):
    """走りのコマ: 体を大きく前に倒し、上下に弾み、杖を振る。"""
    ph = i % 2
    return pose(x=x, y=-2 * ph, tilt=-16 + 4 * ph, squash=1.05 if ph else 0.92,
                staff=dict(ang=(40 if ph else 70), grip=0.5), rh=(10, -14 + ph), lh=(-8, -10 - 2 * ph),
                fx=[speed(x - 12, GROUND - 16, n=3, length=6), puff(x, side=1)] if ph == 0 else
                [speed(x - 12, GROUND - 18, n=3, length=6)], **kw)


def m_ittekimasu():  # いってきます: 大きく手を振ってから、全速力で走って出ていく
    wave_up = pose(tilt=8, expr="happy", lh=(-11, -24), fx=[spr("note", 4, 4)])
    wave_dn = pose(tilt=-6, expr="happy", lh=(-12, -16), fx=[spr("note", 4, 6)])
    final = wave_up
    seq = [final, wave_dn, wave_up, wave_dn] + [run(26 + 8 * i, i, expr="smile") for i in range(1, 6)] + \
        [run(-6 + 8 * i, i, expr="smile") for i in range(1, 4)] + [pose(squash=0.85, expr="happy", lh=(-11, -24)), final]
    return seq, an.split(4000, len(seq)), 1


def m_tadaima():  # ただいま: 走って帰ってきて、回転ジャンプで杖を掲げる
    final = pose(y=-6, squash=1.12, expr="happy", lh=(-10, -24), rh=(5, -24), staff=dict(ang=10, grip=0.4, glow=True),
                 fx=[burst(30, 3, 6, "rainbow"), spr("note", 46, 8), AURA])
    seq = [final] + [run(-6 + 8 * i, i, expr="smile") for i in range(1, 5)]
    seq += [pose(squash=0.75, expr="smile", fx=[puff(24)])] + spin_frames(final, 4) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_ganbare():  # がんばれ!: 杖を頭上で左右にぶん回し、跳ねながら応援
    l = pose(y=-5, tilt=22, squash=1.1, expr="happy", lh=(-9, -22), rh=(1, -25), staff=dict(ang=-60, grip=0.4, glow=True),
             fx=[spr("sparkle", 4, 2), speed(52, 8, left=False), circle(r=12)])
    r = pose(y=-5, tilt=-22, squash=1.1, expr="happy", lh=(-9, -22), rh=(7, -25), staff=dict(ang=60, grip=0.4, glow=True),
             fx=[spr("sparkle", 44, 2), speed(10, 8), circle(r=12)])
    mid = pose(squash=0.82, expr="kira", lh=(-9, -18), rh=(4, -20), staff=dict(ang=0, grip=0.45, glow=True), fx=[circle(r=12)])
    seq = [r, lerp(r, mid, 0.5), mid, lerp(mid, l, 0.5), l, lerp(l, mid, 0.5), mid, lerp(mid, r, 0.5)]
    return seq, an.split(1000, len(seq)), 3


def m_sugoi():    # すごい!: 高く跳んで杖を地面にドーン! 衝撃波・砂ぼこり・地面から稲妻
    lift = pose(y=-10, squash=1.15, expr="surprised", lh=(-7, -20), rh=(6, -24), staff=dict(ang=-20, grip=0.3, glow=True),
                fx=[AURA])
    slam = pose(x=24, squash=0.7, expr="kira", lh=(-7, -10), rh=(9, -10), staff=dict(ang=0, grip=0.6, glow=True),
                fx=[ring(33, 10), puff(30), {"type": "bolt", "x0": 33, "y0": GROUND, "x1": 46, "y1": 4},
                    {"type": "bolt", "x0": 33, "y0": GROUND, "x1": 20, "y1": 2}, spr("exclaim", 48, 6)])
    wave = with_fx(slam, ring(33, 18, VIOLET), ring(33, 12), puff(30), spr("exclaim", 48, 6), burst(33, 20, 12, "rainbow"))
    shake1, shake2 = copy.deepcopy(wave), copy.deepcopy(wave)
    shake1["x"], shake2["x"] = 26, 22
    seq = [wave] + tween(pose(), 1, pose(squash=0.75, expr="angry"), 1, lift, 2, slam) + [shake1, shake2, wave] + \
        tween(wave, 1, lift, 1, slam)[1:] + [shake1, wave]
    return seq, an.split(3000, len(seq)), 1


def m_iine():     # いいね!: 体ごと回りながら杖をバトンのように振り回し、決めポーズ
    final = pose(tilt=-14, x=22, expr="wink", lh=(-10, -22), rh=(10, -16), staff=dict(ang=50, grip=0.45, glow=True),
                 fx=[spr("sparkles", 46, 2), burst(44, 8, 5, "rainbow")])
    seq = [final]
    for i, a in enumerate(range(0, 720, 60)):
        seq.append(pose(y=-(i % 3), sx=[1, 0.5, -0.5, -1, -0.5, 0.5][i % 6], expr="happy", rh=(6, -16),
                        staff=dict(ang=a, grip=0.5, glow=True), fx=[circle(r=11)]))
    seq += [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_yoroshiku():  # よろしく: 杖を大きく振ってあいさつ → 勢いよくおじぎ
    st_free = dict(free=True, gx=40, gy=GROUND - 12, ang=-6)
    final = pose(bow=5, squash=0.82, expr="calm", **CHEST, staff=st_free, fx=[spr("sparkle", 46, 2), burst(24, 6, 6, "rainbow")])
    w1 = pose(tilt=-12, expr="smile", rh=(8, -24), staff=dict(ang=50, grip=0.4, glow=True))
    w2 = pose(tilt=12, expr="smile", rh=(0, -24), staff=dict(ang=-50, grip=0.4, glow=True))
    seq = [final] + tween(pose(), 1, w1, 2, w2, 2, w1, 2, pose(expr="calm", **CHEST, staff=st_free), 1, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_onegai():   # おねがい: 杖を抱えて手を合わせ、体を揺らしてぴょんぴょん
    st = dict(hand="r", ang=-10, grip=0.5, glow=True)
    final = pose(tilt=-8, expr="kira", **CHEST, staff=st, fx=[spr("hearts", 40, 2), AURA])
    hop = pose(y=-6, squash=1.12, tilt=8, expr="kira", **CHEST, staff=st, fx=[spr("hearts", 40, 0), spr("heart", 6, 6), AURA])
    seq = [final] + tween(pose(squash=0.78, tilt=-8, expr="kira", **CHEST, staff=st, fx=[spr("hearts", 40, 2)]), 1, hop, 2, final)
    return seq, an.split(1000, len(seq)), 3


def m_matte():    # ちょっと待って: 大きく踏み込んで杖を突き出し、魔法のバリアを張る
    barrier = {"type": "lines", "color": CYAN, "segs": [(58, 4, 58, 26), (60, 2, 60, 28), (56, 8, 56, 22)]}
    final = pose(x=24, tilt=-24, squash=0.92, expr="surprised", lh=(-11, -20), rh=(13, -15),
                 staff=dict(ang=82, grip=0.3, glow=True), fx=[barrier, spr("exclaim", 46, 0), RAYS])
    back = pose(x=20, tilt=18, expr="surprised", lh=(-8, -14), rh=(-4, -18), staff=dict(ang=-50, grip=0.4))
    seq = [final] + tween(pose(), 1, back, 2, final) + [with_fx(final, barrier, spr("exclaim", 46, 0))]
    shake = copy.deepcopy(final)
    shake["x"] = 26
    seq += [shake, final, shake, final]
    return seq, an.split(2000, len(seq)), 2


def m_shouchi():  # 承知しました: 杖を突き立てて魔法陣を起こし、うやうやしく深くおじぎ
    st = dict(hand="r", ang=0, grip=0.55, glow=True)
    final = pose(bow=5, squash=0.84, expr="calm", lh=(1, -12), rh=(4, -12), staff=st,
                 fx=[circle(r=16), AURA, burst(28, 6, 4)])
    lift = pose(y=-3, squash=1.06, expr="normal", rh=(6, -20), staff=dict(ang=0, grip=0.4, glow=True))
    tap = pose(squash=0.9, expr="normal", rh=(6, -14), staff=st, fx=[ring(30, 8), circle(r=8)])
    seq = [final] + tween(pose(), 1, lift, 1, tap, 1, with_fx(tap, circle(r=13), AURA), 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_wahaha():   # わはは!: 大きくのけぞって、前に折れて、足をばたばたさせて大笑い
    back = pose(tilt=28, y=-3, squash=1.05, expr="happy", lh=(-3, -10), rh=(9, -14), staff=dict(ang=-30, grip=0.55),
                fx=[spr("note", 2, 2), speed(46, 4, left=False), speed(10, 4)])
    fwd = pose(tilt=-18, bow=3, squash=0.85, expr="happy", lh=(-3, -10), rh=(9, -12), staff=dict(ang=15, grip=0.55),
               fx=[spr("note", 46, 4), spr("note", 6, 10)])
    seq = tween(back, 3, fwd, 3, back)[:-1]
    return seq, an.split(1000, len(seq)), 3


def m_eh():       # えっ!?: 跳び上がって帽子も杖も吹っ飛ぶ → 落ちてきて元どおり
    final = pose(y=-10, squash=1.15, expr="surprised", lh=(-10, -24), rh=(10, -24), hat=(-15, 3, 35),
                 staff=dict(free=True, gx=46, gy=8, ang=135), fx=[spr("exclaim_q", 52, 18), spr("sweats", 34, 14)])
    seq = [final, pose(expr="normal")]
    path = [(34, 22, 30, -4), (40, 13, 80, -9), (46, 8, 135, -14), (50, 5, 200, -16), (48, 9, 270, -12), (42, 16, 330, -6)]
    for i, (gx, gy, a, hx) in enumerate(path):
        seq.append(pose(y=-10 + max(0, i - 2) * 2, squash=1.15, expr="surprised", lh=(-10, -24), rh=(10, -24),
                        hat=(hx, 2 + abs(hx) // 4, 20 + 25 * i),
                        staff=dict(free=True, gx=gx, gy=gy, ang=a), fx=[spr("exclaim_q", 52, 18)]))
    seq += [pose(squash=0.75, expr="surprised", staff=dict(ang=0, grip=0.5), fx=[spr("sweats", 36, 8), puff(24)]),
            pose(expr="surprised", fx=[spr("sweats", 36, 8)]), final]
    return seq, an.split(2000, len(seq)), 2


def m_daijoubu():  # 大丈夫?: 走って駆け寄り、大きく身を乗り出して癒やしの杖を差し出す
    final = pose(x=24, tilt=-22, bow=2, expr="sad", lh=(-6, -12), rh=(13, -12), staff=dict(ang=105, grip=0.3, glow=True),
                 fx=[spr("sweat", 12, 2), spr("question", 48, 0), spr("heart", 52, 16), RAYS])
    seq = [final] + [run(-2 + 6 * i, i, expr="sad") for i in range(1, 5)] + \
        tween(pose(x=24, squash=0.85, expr="sad"), 2, final) + [final] * 3
    return seq, an.split(3000, len(seq)), 1


def m_odaiji():   # お大事に: 魔法陣の上で杖を大きく振り、ハートの回復魔法を降らせる
    def hearts(o):
        return [spr("heart", 44, 16 - o), spr("heart", 4, 20 - o), spr("heart", 52, 4 + o // 2),
                burst(30, 4, 4 + o / 2, PINK), circle(r=14), AURA]
    final = pose(tilt=-14, expr="calm", lh=(-8, -18), rh=(6, -24), staff=dict(ang=25, grip=0.4, glow=True), fx=hearts(6))
    a = pose(tilt=14, expr="calm", lh=(-8, -18), rh=(2, -24), staff=dict(ang=-25, grip=0.4, glow=True), fx=hearts(0))
    seq = [final] + tween(a, 3, final, 3, a)[1:-1]
    return seq, an.split(2000, len(seq)), 2


def m_tanoshimi():  # 楽しみ!: 杖を掲げて、回転しながら高く連続ジャンプ
    up = pose(y=-11, squash=1.15, expr="kira", lh=(-10, -24), rh=(5, -25), staff=dict(ang=15, grip=0.4, glow=True),
              fx=[spr("note", 46, 4), spr("note", 4, 10), AURA])
    dn = pose(squash=0.72, expr="happy", lh=(-10, -18), rh=(6, -18), staff=dict(ang=15, grip=0.45, glow=True),
              fx=[spr("note", 46, 8), spr("note", 4, 6), puff(24)])
    mid = lerp(up, dn, 0.5)
    seq = [up, lerp(up, dn, 0.3)] + [copy.deepcopy(mid)] + [dn, mid]
    seq[2]["sx"] = -0.5
    return seq, an.split(1000, len(seq)), 3


def m_kaeru():    # 今から帰る: 杖にまたがって、宙返りしながらびゅーんと飛んで帰る
    def fly(x, y, tilt=-10, sx=1.0):
        return pose(x=x, y=y, tilt=tilt, sx=sx, squash=0.85, expr="happy", lh=(5, -8), rh=(9, -9),
                    staff=dict(free=True, gx=x + 2, gy=GROUND + y - 5, ang=96 - tilt * 0, grip=0.45, glow=True),
                    fx=[speed(x - 12, GROUND + y - 14, n=3, length=8),
                        {"type": "dots", "color": "rainbow", "pts": [(x - 12 - k * 3, GROUND + y - 6 + (k % 2)) for k in range(5)]}])
    final = fly(26, -8)
    final["fx"].append(spr("sparkle", 48, 0))
    seq = [final] + [fly(-12 + 6 * i, -3 - 3 * math.sin(i / 2), tilt=-10 - 8 * math.sin(i)) for i in range(1, 12)] + [final] * 2
    return seq, an.split(3000, len(seq)), 1


def m_naruhodo():  # なるほど: 杖をドンと突いて、ひらめきの光とともに深くうなずく
    idea = [burst(24, 2, 4, GOLD), spr("exclaim", 42, 2), {"type": "rays", "n": 8, "r0": 5, "r1": 8}]
    final = pose(bow=4, squash=0.88, expr="calm", rh=(9, -13), staff=dict(ang=0, grip=0.5, glow=True), fx=idea)
    up = pose(y=-3, squash=1.08, expr="surprised", rh=(9, -18), staff=dict(ang=0, grip=0.35, glow=True))
    nod = pose(bow=5, squash=0.82, expr="calm", rh=(9, -12), staff=dict(ang=0, grip=0.5, glow=True),
               fx=[ring(33, 8), puff(33)])
    seq = [final] + tween(pose(), 1, up, 2, nod, 2, up, 2, final) + [final] * 2
    return seq, an.split(3000, len(seq)), 1


MOTIONS = {
    "thanks": m_thanks, "morning": m_morning, "ok": m_ok, "roger": m_roger, "sorry": m_sorry,
    "otsukare": m_otsukare, "congrats": m_congrats, "goodnight": m_goodnight, "ittekimasu": m_ittekimasu,
    "tadaima": m_tadaima, "ganbare": m_ganbare, "sugoi": m_sugoi, "iine": m_iine, "yoroshiku": m_yoroshiku,
    "onegai": m_onegai, "matte": m_matte, "shouchi": m_shouchi, "wahaha": m_wahaha, "eh": m_eh,
    "daijoubu": m_daijoubu, "odaiji": m_odaiji, "tanoshimi": m_tanoshimi, "kaeru": m_kaeru,
    "naruhodo": m_naruhodo,
}


def render_sequence(poses, text, style):
    """コマを順に描く。杖が大きく動いたコマには、直前の宝玉の位置から光の軌跡を付ける。"""
    imgs, tips = [], []
    for i, p in enumerate(poses):
        orb = geometry(p)["orb"]
        trail = ()
        if i >= 2 and p["staff"].get("glow") and tips:  # 1 コマ目 (完成形) からの軌跡は付けない
            prev = [t for t in tips[-2:] if t is not None]
            if prev and math.hypot(orb[0] - prev[-1][0], orb[1] - prev[-1][1]) > 3:
                trail = prev
        imgs.append(render(p, text, style, phase=i, trail=trail))
        tips.append(orb if i >= 1 else None)
    return imgs


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
        imgs = render_sequence(poses, item["text"], style)
        path = out / f"{i:02d}.png"
        an.save_apng(imgs, ms, loops, path)
        all_frames.append((imgs, ms, loops))
        info, errs = an.check_anim(path, "stamp")
        problems += [f"{path.name}: {e}" for e in errs]
        print(f"  {path.name}  {item['motion']:<10} {info['frames']:>2}f {info['ms'] * info['loops']:>4}ms "
              f"{info['bytes'] // 1024:>3}KB  {item['text']!r}")

    # メイン画像 (240x240): 杖をついてまばたき、杖の宝玉が光り、魔法の粒が立ちのぼる
    grids = [render_grid(pose(x=24, expr=expr, staff=dict(ang=0, grip=0.5, glow=True), fx=[AURA]), phase=j)
             for j, expr in enumerate(["smile"] * 5 + ["calm"] + ["smile"] * 4)]
    box = (4, 2, 46, GROUND + 2)
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
