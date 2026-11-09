#!/usr/bin/env python3
"""set05: set04 の絵(下絵 work/set05/base/NN.png)の上に、新しいセリフを重ねる。

  python3 tools/set05_base.py            # 下絵を作る(set04 の絵から文字だけ抜いたもの。一度でよい)
  python3 tools/set05.py 01 --png work/set05/design/01_sheet.png

セリフごとに、書体・枠(吹き出し・札・画面など)・出し方の動きを変える。絵は下絵のまま何も変えない。
1コマ目はできあがりの形。2コマ目から出し方の動きが始まり、出たあとも何かがゆっくり動き続ける。
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import textfx as X
from textfx import (T, prog, eo, back, bounce, draw, line, width, glyph, put, vec, rrect, poly, ell, seg, spiky,
                    cloud, star, sparkle, impact, clip, new, INK, RED, RED_D, GREEN, GREEN_D, GOLD, NAVY, WHITE)

ROOT = Path(__file__).resolve().parent.parent
CW, CH = 320, 270
CARDS = "11 12 16 19 20 21 22 23 24".split()
YEL = "#FFD43B"


def seal(L, cx, cy, r, lines, s=1.0, rot=0.0, col=RED, square=False):
    """赤いはんこ(丸か四角、二重のふち)。lines: (文字, 大きさ, dy)。"""
    sub = new()

    def fn(d):
        if square:
            rrect(d, (cx - r, cy - r, cx + r, cy + r), 5, WHITE, col, 3)
            rrect(d, (cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), 3, None, col, 1.5)
        else:
            ell(d, (cx - r, cy - r, cx + r, cy + r), WHITE, col, 3)
            ell(d, (cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), None, col, 1.5)
    vec(sub, fn)
    for text, size, dy in lines:
        draw(sub, line(text, "zenkaku", size, cx, cy + dy, "c"), "zenkaku", dict(fill=col))
    # はんこは押す動き(大きく→ぴたっ)と傾き。中心 (cx, cy) のまわりで拡大・回転する
    box = sub.crop((int(cx - r - 4), int(cy - r - 4), int(cx + r + 5), int(cy + r + 5)))
    put(L, box, cx, cy, s, rot)


# ==== 01 サンタは70歳から永久に歳を取らない: テレビの「豆知識」テロップ ====
def s01(L, i, F):
    u_tab = prog(i, 1, 2)
    bob = 2 * math.sin(i * 1.05)
    ty = 12 - (1 - eo(u_tab)) * 34 + bob
    w = eo(prog(i, 2, 4))
    l1 = line("サンタは70歳から", "zenkaku", 21, 26, 56, sizes=[21, 21, 21, 21, 26, 26, 21, 21, 21])
    l2 = line("永久に歳を取らない", "zenkaku", 21, 26, 87)
    bx1 = 26 + max(width(l1), width(l2)) + 12

    def bar(d):
        if w > 0:
            rrect(d, (12, 36, 12 + (bx1 - 12) * w, 104), 6, WHITE, INK, 2.5)
            d.rectangle(X.P(14, 39, 20, 101), fill=RED)
        if u_tab > 0:
            rrect(d, (14, ty - 2, 100, ty + 24), 6, YEL, INK, 2.2)
    vec(L, bar)
    if u_tab > 0:
        draw(L, line("豆知識", "dela", 17, 57, ty + 11, "c"), "dela", dict(fill=RED))
    sub = new()
    m = eo(prog(i, 7, 9))  # 「永久に」に黄色いマーカー
    if m > 0:
        x0, x1 = l2[0]["x"] - 10, l2[2]["x"] + 10
        vec(sub, lambda d: rrect(d, (x0, 76, x0 + (x1 - x0) * m, 99), 3, "#FFE97A", None))
    d1 = (1 - eo(prog(i, 3, 5))) * 170
    d2 = -(1 - eo(prog(i, 4, 6))) * 170
    draw(sub, l1, "zenkaku", lambda c: dict(fill=RED if c["ch"] in "70" else NAVY), lambda c: (d1, 0, 1, 0))
    draw(sub, l2, "zenkaku", lambda c: dict(fill=RED if c["j"] < 3 else NAVY),
         lambda c: (d2, 0, 1.0 + (0.08 * math.sin(i * 1.3) if c["j"] < 3 and T(i) > 9 else 0), 0))
    clip(sub, (14, 38, 12 + (bx1 - 12) * w - 2, 102))
    L.alpha_composite(sub)


# ==== 02 とりあえずこれ受け取れや / タダではない: ギザギザの叫び吹き出し+赤いはんこ ====
def s02(L, i, F):
    s = back(prog(i, 1, 2.5))
    if s > 0.15:
        ph = 0.12 * math.sin(i * 1.4)
        vec(L, lambda d: poly(d, spiky(132, 54, 120 * s, 46 * s, 17, 9, ph), "#FFF3B0", INK, 2.6))
    st1 = dict(fill=GREEN, ow=3, rw=2)
    draw(L, line("とりあえず", "reggae", 18, 132, 31, "c"), "reggae", st1,
         lambda c: None if T(i) < 2.5 else (0, 0, back(prog(i, 2.5 + c["j"] * 0.12, 3.5 + c["j"] * 0.12)), 0))
    l2 = line("これ受け取れや", "reggae", 28, 132, 66, "c")

    def fx2(c):
        u = prog(i, 3.5 + c["j"] * 0.3, 4.5 + c["j"] * 0.3)
        if u <= 0:
            return None
        return (0, 0, 1 + (1 - eo(u)) * 1.3, (1 - eo(u)) * -25 + 3 * math.sin(i * 1.2 + c["j"]))
    draw(L, l2, "reggae", lambda c: dict(fill=RED if c["j"] >= 2 else INK, ow=3, rw=2), fx2)
    u = prog(i, 7, 8)
    if u > 0:
        seal(L, 268, 114, 36, [("タダ", 21, -10), ("ではない", 14, 12)], s=1 + (1 - eo(u)) * 1.4, rot=-12)
        if 8 <= T(i) <= 9:
            vec(L, lambda d: impact(d, 268, 114, 42, 52, 10, RED, 2.5))


# ==== 03 4時間運んで30分休憩します: つり下げの「お知らせ」看板(落ちてきてゆれる) ====
def s03(L, i, F):
    sub = new()
    px, py = 82, 12

    def fn(d):
        seg(d, [(px, py), (26, 36)], INK, 2)
        seg(d, [(px, py), (138, 36)], INK, 2)
        ell(d, (px - 4, py - 4, px + 4, py + 4), GOLD, INK, 1.6)
        rrect(d, (14, 34, 150, 148), 10, "#FFFDF4", INK, 2.8)
        rrect(d, (14, 34, 150, 58), 10, GREEN, INK, 2.8)
        d.rectangle(X.P(16, 48, 148, 57), fill=GREEN)
    vec(sub, fn)
    draw(sub, line("お知らせ", "dela", 14, 82, 46, "c"), "dela", dict(fill=WHITE))
    draw(sub, line("4時間運んで", "kaisei", 19, 82, 78, "c", sizes=[25, 19, 19, 19, 19, 19]), "kaisei",
         lambda c: dict(fill=RED if c["ch"] == "4" else INK))
    l2 = line("30分休憩", "kaisei", 20, 82, 106, "c", sizes=[25, 25, 20, 20, 20])
    draw(sub, l2, "kaisei", lambda c: dict(fill=RED if c["ch"] in "30" else INK))
    draw(sub, line("します", "kaisei", 17, 82, 132, "c"), "kaisei", dict(fill=INK))
    m = prog(i, 6, 9)  # 「休憩」に赤い丸
    if m > 0:
        cx = (l2[3]["x"] + l2[4]["x"]) / 2
        vec(sub, lambda d: d.arc(X.P(cx - 30, 92, cx + 30, 121), -200, -200 + 360 * m, fill=RED, width=3 * X.K))
    drop = (1 - bounce(prog(i, 1, 3))) * -150
    t = T(i)
    if t < 3:
        ang = 0
    elif t < 10:
        ang = 16 * math.exp(-(t - 3) * 0.45) * math.cos((t - 3) * 1.6)
    else:
        ang = 2.5 * math.sin(i * 0.9)
    sub = sub.rotate(ang, resample=Image.BICUBIC, center=(px, py))
    X.comp(L, sub, 0, drop)


# ==== 04 面倒くさいから何も入れないで帰る: だるそうな字が上からぽとぽと落ちる+ためいき雲 ====
def s04(L, i, F):
    puff = eo(prog(i, 6, 9))
    if puff > 0:
        fl = 3 * math.sin(i * 0.9)
        vec(L, lambda d: cloud(d, 134, 150 - puff * 6 + fl, 18 * puff, 11 * puff, "#EEF1F6", "#8C96A8", 2, 8))
    rows = [(line("面倒くさいから", "yomogi", 21, 14, 176), 1.0), (line("何も入れないで", "yomogi", 21, 14, 205), 3.4)]
    st = dict(fill="#56627E", ow=4, rw=1.6, rfill="#8C96A8", thick=1)
    for chars, t0 in rows:
        def fx(c, t0=t0):
            u = prog(i, t0 + c["j"] * 0.32, t0 + c["j"] * 0.32 + 1.6)
            if u <= 0:
                return None
            return (0, c["j"] * 1.3 - (1 - bounce(u)) * 70, 1, -4 + (1 - u) * 25 * (1 if c["j"] % 2 else -1))
        draw(L, chars, "yomogi", st, fx)
    kv = line("帰る", "yomogi", 38, 30, 240)
    u = prog(i, 7.5, 9)
    if u > 0:
        walk = 4 * math.sin(i * 1.6)
        draw(L, kv, "yomogi", dict(fill=RED, ow=4, rw=2, thick=1),
             lambda c: (-(1 - eo(u)) * 40 + walk, -abs(3 * math.sin(i * 1.6 + c["j"])), 1, -6 + 4 * math.sin(i * 1.6)))
        # 歩いたあとの小さな足あと(だるそうに)
        vec(L, lambda d: [ell(d, (104 + k * 12, 246 - (k % 2) * 5, 110 + k * 12, 251 - (k % 2) * 5), "#A9B1C2", None)
                          for k in range(3)])


# ==== 05 自動運転: カーナビの画面(電源が入る→ドットの字が打たれる→ONのランプ) ====
def s05(L, i, F):
    on = eo(prog(i, 1, 2))
    if on <= 0:
        return
    cy, hh = 50, 38 * on

    def fn(d):
        rrect(d, (164, cy - hh, 306, cy + hh), 10, "#16233A", INK, 2.8)
        if on >= 1:
            rrect(d, (170, cy - hh + 5, 300, cy + hh - 5), 7, None, "#3C5A85", 1.6)
            sl = 18 + (i * 7) % 56  # ゆっくり下りる走査線
            d.rectangle(X.P(172, cy - 38 + sl, 298, cy - 37 + sl), fill="#22385A")
            lamp = "#45E07A" if T(i) >= 8 else "#5A2A2A"
            ell(d, (284, 18, 294, 28), lamp, INK, 1.4)
            if 2 <= T(i) < 3:  # 電源が入るときのノイズ
                for k in range(5):
                    y = 24 + k * 11
                    d.rectangle(X.P(176 + (k * 37) % 40, y, 290 - (k * 23) % 50, y + 2), fill="#5CF2C8")
    vec(L, fn)
    if on < 1:
        return
    draw(L, line("AUTO", "dot", 12, 176, 23), "dot", dict(fill="#FFB547"))
    chars = line("自動運転", "dot", 30, 235, 58, "c")
    nshow = 4 if T(i) >= 8 else max(0, min(4, int(T(i) - 3)))
    draw(L, chars, "dot", dict(fill="#5CF2C8", rw=2, rfill="#1F6F67"),
         lambda c: (0, 0, 1, 0) if c["j"] < nshow else None)
    if T(i) < 8 and nshow < 4:  # 打っている途中のカーソル
        c = chars[nshow]
        vec(L, lambda d: d.rectangle(X.P(c["x"] - 12, c["y"] - 14, c["x"] + 12, c["y"] + 14), fill="#5CF2C8"))
    if 8 <= T(i) <= 9:
        vec(L, lambda d: impact(d, 289, 23, 9, 14, 8, "#45E07A", 1.6))


# ==== 06 今日は直帰: ホワイトボードがすべりこみ、マーカーで書いて「直帰」を赤丸 ====
def s06(L, i, F):
    dx = -(1 - back(prog(i, 1, 2.5), 1.4)) * 260
    sub = new()

    def board(d):
        rrect(d, (18, 12, 232, 106), 6, "#C9D3DC", INK, 2.5)
        rrect(d, (24, 18, 226, 100), 3, WHITE, "#9AA7B3", 1.5)
        rrect(d, (70, 100, 180, 108), 2, "#B3BFCA", INK, 1.6)
        for x, col in ((36, RED), (212, "#3A7BD5")):
            ell(d, (x - 7, 15, x + 7, 29), col, INK, 1.6)
            ell(d, (x - 3, 17, x, 20), WHITE, None)
    vec(sub, board)
    txt = new()
    l1 = line("今日は", "hachi", 30, 36, 62)
    l2 = line("直帰", "hachi", 42, 36 + width(l1) + 4, 60)
    draw(txt, l1, "hachi", dict(fill="#2F6FD0", thick=1))
    draw(txt, l2, "hachi", dict(fill=RED, thick=1))
    w = prog(i, 3, 6.5)
    x_end = 32 + (l2[-1]["x"] + 26 - 32) * w
    clip(txt, (0, 0, x_end, CH))
    sub.alpha_composite(txt)
    m = prog(i, 7, 9.5)
    if m > 0:
        cx, r = (l2[0]["x"] + l2[1]["x"]) / 2, 50
        vec(sub, lambda d: d.arc(X.P(cx - 60, 30, cx + 60, 92), -160, -160 + 370 * m, fill=RED, width=3 * X.K))
    if 3 <= T(i) < 7:  # 書いているマーカー
        vec(sub, lambda d: (poly(d, [(x_end, 74), (x_end + 8, 68), (x_end + 34, 46), (x_end + 26, 40), (x_end, 62)],
                                 "#2F6FD0", INK, 1.8)))
    X.comp(L, sub, dx, 0)


# ==== 07 飲み過ぎた〜: ふらふらの字(回りながら出る・二重に見える)+しゃっくりの泡 ====
def s07(L, i, F):
    chars = line("飲み過ぎた〜", "mochiy", 38, 158, 206, "c")
    cols = ["#FF6F9C", "#9B6BD6", "#FF9F43"]
    hic = -10 if T(i) in (9,) else 0

    def fx(c, ghost=False):
        u = prog(i, 1 + c["j"] * 0.55, 2.2 + c["j"] * 0.55)
        if u <= 0:
            return None
        sway = 6 * math.sin(i * 0.9 + c["j"] * 0.8)
        rot = 10 * math.sin(i * 0.7 + c["j"] * 1.1) + (1 - eo(u)) * 360
        g = (5 * math.sin(i * 0.8) + 4, -3) if ghost else (0, 0)
        return (g[0], sway + hic + g[1], 0.3 + 0.7 * eo(u), rot)
    if T(i) >= 6:
        draw(L, chars, "mochiy", dict(fill="#E2D2F7"), lambda c: fx(c, True))
    draw(L, chars, "mochiy", lambda c: dict(fill=cols[c["j"] % 3], ow=4, rw=2), fx)
    vec(L, lambda d: [ell(d, (x - r, y - r, x + r, y + r), "#E8F6FF", "#7FB3D9", 1.6)
                      for k in range(3)
                      for x, y, r in [(272 + 6 * math.sin(i + k), 182 - ((i * 9 + k * 22) % 60), 4 + k * 1.5)]
                      if T(i) >= 7])


# ==== 08 去年と同じじゃだめだろ!: 怒りの爆発吹き出し(ドーン)+怒りマーク ====
def s08(L, i, F):
    s = back(prog(i, 1, 2.2), 2.2)
    jit = 3 if T(i) in (5, 6) else 0
    jx = jit * (1 if i % 2 else -1)
    if s > 0.15:
        vec(L, lambda d: poly(d, spiky(108 + jx, 62, 96 * s, 56 * s, 14, 12, 0.2, 0.08), WHITE, INK, 2.8))
    draw(L, line("去年と同じじゃ", "dela", 22, 108, 42, "c"), "dela", dict(fill=INK, ow=2),
         lambda c: None if prog(i, 2 + c["j"] * 0.25, 2.5 + c["j"] * 0.25) <= 0 else
         (jx - (1 - eo(prog(i, 2 + c["j"] * 0.25, 3 + c["j"] * 0.25))) * 30, 0, 1, 0))
    u = prog(i, 5, 6)
    if u > 0:
        draw(L, line("だめだろ!", "dela", 34, 108, 80, "c"), "dela", dict(fill=RED, ow=3, rw=2),
             lambda c: (jx, 0, 1 + (1 - eo(u)) * 0.9, -3 + (1 - eo(u)) * 10))
    if 5 <= T(i) <= 6:
        vec(L, lambda d: impact(d, 108, 62, 108, 122, 12, INK, 2.5, 0.3))
    if T(i) >= 6:  # 怒りマーク(ぴくぴく)
        k = 1 + 0.15 * math.sin(i * 2.1)

        def vein(d):
            cx, cy = 206, 22
            for ax, ay in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                a, b = (cx + ax * 4 * k, cy + ay * 11 * k), (cx + ax * 11 * k, cy + ay * 4 * k)
                seg(d, [a, (cx + ax * 9 * k, cy + ay * 9 * k), b], RED, 3.2)
        vec(L, vein)


# ==== 09 ハロウィンっぽい: 紫のおばけ板(下がどろっと垂れる)+オレンジと黄緑の字+コウモリとかぼちゃ ====
def s09(L, i, F):
    g = eo(prog(i, 1, 2.5))
    drip = eo(prog(i, 6, 10))
    if g > 0.1:
        def plate(d):
            x0, x1, y0, y1 = 196 - 110 * g, 196 + 110 * g, 12, 12 + 70 * g
            pts = [(x0 + 4, y0), (x1 - 4, y0), (x1, y0 + 6), (x1, y1)]
            n = 9
            for k in range(n, -1, -1):  # 下のふちは波打って、ところどころ垂れる
                x = x0 + (x1 - x0) * k / n
                ln = (drip * (8 + (k * 7) % 11) + 1.5 * math.sin(i * 0.8 + k)) if k % 3 == 1 and k < 6 else 0
                pts += [(x + 6, y1 + 3 * math.sin(k * 2.1)), (x, y1 + ln + 3)]
            pts += [(x0, y0 + 6)]
            poly(d, pts, "#3B2557", "#1E1030", 2.6)
            for k in range(1, 6, 3):  # 垂れの先の丸
                x = x0 + (x1 - x0) * k / n
                ln = drip * (8 + (k * 7) % 11) + 1.5 * math.sin(i * 0.8 + k)
                if ln > 4:
                    ell(d, (x - 5, y1 + ln - 2, x + 5, y1 + ln + 8), "#3B2557", "#1E1030", 2)
        vec(L, plate)
    for txt, size, y, t0, cx in (("ハロウィン", 34, 36, 2, 196), ("っぽい", 27, 66, 5, 222)):
        chars = line(txt, "dela", size, cx, y, "c")

        def fx(c, t0=t0):
            u = prog(i, t0 + c["j"] * 0.45, t0 + 1.4 + c["j"] * 0.45)
            if u <= 0:
                return None
            return (0, (1 - eo(u)) * 30 + 2 * math.sin(i * 0.8 + c["j"]), 0.4 + 0.6 * eo(u),
                    (1 - u) * 25 * math.sin(c["j"] * 2) + 3 * math.sin(i * 0.6 + c["j"]))
        draw(L, chars, "dela", lambda c: dict(fill="#FF8A1E" if c["j"] % 2 == 0 else "#B6F25A", ow=2, ofill="#1E1030"), fx)
    pu = back(prog(i, 7, 8.5))
    if pu > 0:  # かぼちゃのおばけ(ゆれる)
        def pk(d):
            cx, cy, r = 150 + 2 * math.sin(i), 64, 13 * pu
            ell(d, (cx - r, cy - r * 0.85, cx + r, cy + r * 0.85), "#FF8A1E", "#1E1030", 2.2)
            seg(d, [(cx - r * 0.4, cy - r * 0.8), (cx - r * 0.4, cy + r * 0.8)], "#E06A00", 1.4)
            seg(d, [(cx + r * 0.4, cy - r * 0.8), (cx + r * 0.4, cy + r * 0.8)], "#E06A00", 1.4)
            seg(d, [(cx, cy - r * 0.85), (cx + 2, cy - r * 1.25)], GREEN_D, 3)
            if pu > 0.8:
                poly(d, [(cx - 8, cy - 2), (cx - 4, cy - 8), (cx - 1, cy - 2)], "#1E1030", None)
                poly(d, [(cx + 8, cy - 2), (cx + 4, cy - 8), (cx + 1, cy - 2)], "#1E1030", None)
                poly(d, [(cx - 8, cy + 3), (cx + 8, cy + 3), (cx + 5, cy + 8), (cx, cy + 6), (cx - 5, cy + 8)], "#1E1030", None)
        vec(L, pk)

    def bats(d):  # コウモリ2匹が、大きく羽ばたきながら飛ぶ
        for k in range(2):
            t = (i + k * 6) % 12 / 12
            x = 40 + 230 * t if k == 0 else 280 - 220 * t
            y = 128 + 12 * math.sin(t * 6.3 + k) + k * 20
            f = 1 if (i + k) % 2 else -1
            sc = 1.5
            pts = [(-13, -5 * f), (-7, 3), (-3, 0), (0, 4), (3, 0), (7, 3), (13, -5 * f), (6, -2), (2, -5), (0, -3), (-2, -5), (-6, -2)]
            poly(d, [(x + px * sc, y + py * sc) for px, py in pts], "#3B2557", "#1E1030", 1.6)
            ell(d, (x - 2, y - 4, x - 0.5, y - 2.5), "#FFD84D", None)
            ell(d, (x + 0.5, y - 4, x + 2, y - 2.5), "#FFD84D", None)
    vec(L, bats)


# ==== 10 ブーツの中はムレるわ〜: もわもわの湯気雲+ゆらゆらの字+におい線 ====
def s10(L, i, F):
    g = eo(prog(i, 1, 3))
    if g > 0:
        vec(L, lambda d: cloud(d, 110, 64 + (1 - g) * 40, 98 * g + 1, 54 * g + 1, "#F2F2EE", "#9A9A8C", 2.2, 12, 0.3))
    for (txt, size, y, t0, col) in (("ブーツの中は", 22, 46, 3, "#7A8B2E"), ("ムレるわ〜", 31, 86, 5, "#B07A2A")):
        chars = line(txt, "kiwi", size, 110, y, "c")

        def fx(c, t0=t0):
            u = prog(i, t0 + c["j"] * 0.15, t0 + 1.6 + c["j"] * 0.15)
            if u <= 0:
                return None
            return (0, (1 - eo(u)) * 26 + 3 * math.sin(i * 1.2 + c["j"] * 0.9), 1, 0, 1 + 0.05 * math.sin(i * 1.1 + c["j"]), 1)
        draw(L, chars, "kiwi", dict(fill=col, ow=3, rw=2, thick=1), fx)
    if T(i) >= 6:  # におい線(くねくね、上へ)
        def stink(d):
            for k, x in enumerate((40, 176)):
                pts = [(x + 5 * math.sin(i * 1.3 + y * 0.25 + k), y) for y in range(138, 112, -2)]
                seg(d, pts, "#9DB04A", 2.6)
        vec(L, stink)


# ==== 13 なにっサーンス!!: 集中線+金の字がズームで飛びこむ+「ー」がのびる ====
def s13(L, i, F):
    r = eo(prog(i, 2, 4))
    if r > 0:
        def rays(d):
            cx, cy = 200, 70
            for k in range(14):
                a = k / 14 * 2 * math.pi + i * 0.08
                pts = [(cx + 40 * math.cos(a - 0.05), cy + 26 * math.sin(a - 0.05)),
                       (cx + 125 * r * math.cos(a), cy + 70 * r * math.sin(a)),
                       (cx + 40 * math.cos(a + 0.05), cy + 26 * math.sin(a + 0.05))]
                poly(d, pts, "#FFF0A0", None)
        vec(L, rays)
        clip(L, (10, 10, 310, 120))
    draw(L, line("なにっ", "rock", 24, 98, 30, "c"), "rock", dict(fill=RED, ow=3, rw=2),
         lambda c: None if T(i) < 1 else (0, 0, back(prog(i, 1, 2)), -8))
    big = line("サーンス!!", "rock", 36, 200, 76, "c")

    def fx(c):
        u = prog(i, 3 + c["j"] * 0.3, 4.2 + c["j"] * 0.3)
        if u <= 0:
            return None
        pul = 1 + 0.05 * math.sin(i * 1.4)
        st = (1 + 0.35 * (0.5 + 0.5 * math.sin(i * 1.2))) if c["ch"] == "ー" else 1
        hop = -abs(8 * math.sin(i * 1.5 + c["j"])) if c["ch"] == "!" else 0
        return (0, hop, (0.2 + 0.8 * back(u)) * pul, (1 - u) * -40, st, 1)
    draw(L, big, "rock", lambda c: dict(fill="#F2B705", ow=3, rw=2, sh=3, shfill=RED_D), fx)


# ==== 14 置き配でよくね?: スマホのメッセージ(入力中の…→ふきだし) ====
def s14(L, i, F):
    t = T(i)
    fl = 2 * math.sin(i * 0.8)
    if 1 <= t < 4:  # 入力中
        def typing(d):
            rrect(d, (16, 92, 82, 124), 16, "#D6ECFF", INK, 2.4)
            for k in range(3):
                up = 4 if (t + k) % 3 == 0 else 0
                ell(d, (32 + k * 14 - 4, 104 - up, 32 + k * 14 + 4, 112 - up), "#7A8FA8", None)
        vec(L, typing)
        return
    g = back(prog(i, 3.4, 4.6), 1.4)

    def bub(d):
        x1, y0 = 16 + 160 * g, 124 - 92 * g
        rrect(d, (16, y0 + fl, x1, 126 + fl), 22, "#D6ECFF", INK, 2.6)
        if g > 0.9:
            poly(d, [(150, 122 + fl), (176, 140 + fl), (166, 118 + fl)], "#D6ECFF", None)
            seg(d, [(150, 125.5 + fl), (176, 140 + fl), (164, 123 + fl)], INK, 2.6)
    vec(L, bub)
    if g < 0.95:
        return
    draw(L, line("置き配で", "mplus", 26, 32, 62 + fl), "mplus", dict(fill=NAVY), lambda c: None if t < 5 else (0, 0, 1, 0))
    draw(L, line("よくね?", "mplus", 31, 32, 101 + fl), "mplus", dict(fill=RED),
         lambda c: None if t < 6 else (0, 0, back(prog(i, 6, 7)), -6 if c["ch"] == "?" else 0))
    draw(L, line("23:58", "mplus", 11, 20, 140), "mplus", dict(fill="#5E6B7D", ow=2))


# ==== 15 双子の兄弟 / 兄は暑がり: 赤いリボンの見出しが広がる+名札が落ちてきてゆれる(矢印で雪だるま)+汗 ====
def s15(L, i, F):
    w = eo(prog(i, 1, 4))
    cx = 130
    if w > 0.05:
        def rib(d):
            hw = 104 * w
            for sg in (-1, 1):
                poly(d, [(cx + sg * (hw + 20), 26), (cx + sg * hw, 26), (cx + sg * hw, 64), (cx + sg * (hw + 20), 64),
                         (cx + sg * (hw + 11), 45)], RED_D, INK, 2.2)
            rrect(d, (cx - hw, 18, cx + hw, 58), 3, RED, INK, 2.4)
            seg(d, [(cx - hw + 4, 23), (cx + hw - 4, 23)], "#F07A72", 1.6)
            seg(d, [(cx - hw + 4, 53), (cx + hw - 4, 53)], RED_D, 1.6)
        vec(L, rib)
        sub = new()
        draw(sub, line("双子の兄弟", "zenmaru", 30, cx, 38, "c"), "zenmaru", dict(fill=WHITE, rw=2, rfill=RED_D))
        clip(sub, (cx - 104 * w, 0, cx + 104 * w, CH))
        L.alpha_composite(sub)
    u = prog(i, 5, 6)
    if u <= 0:
        return
    t = T(i)
    ang = 14 * math.exp(-(t - 6) * 0.5) * math.cos((t - 6) * 1.7) if 6 <= t < 12 else 4 * math.sin(i * 0.9)
    sub = new()
    pin = (252, 68)

    def tag(d):
        seg(d, [pin, (252, 76)], INK, 2)
        ell(d, (247, 63, 257, 73), GOLD, INK, 1.4)
        poly(d, [(196, 86), (206, 76), (298, 76), (306, 86), (306, 110), (196, 110)], "#FFF7E6", INK, 2.4)
        seg(d, [(262, 112), (258, 118)], INK, 2.4)  # 小さな矢印(下の雪だるまへ)
        poly(d, [(253, 117), (263, 117), (257, 124)], INK, None)
    vec(sub, tag)
    l = line("兄は暑がり", "klee", 20, 251, 95, "c")
    draw(sub, l, "klee", lambda c: dict(fill=INK if c["j"] < 2 else RED, thick=1))
    sub = sub.rotate(ang, resample=Image.BICUBIC, center=pin)
    X.comp(L, sub, 0, -(1 - bounce(u)) * 110)
    if t >= 9:  # 汗
        def sweat(d):
            for k, (x, y) in enumerate(((276, 140), (284, 160))):
                yy = y + ((i * 3 + k * 5) % 8)
                poly(d, [(x, yy - 7), (x + 4, yy + 1), (x, yy + 4), (x - 4, yy + 1)], "#8FD3FF", INK, 1.4)
        vec(L, sweat)


# ==== 17 トナカイの検索は年イチ: 検索バーで字を打つ→「年イチ」のバッジがくるっと出る ====
def s17(L, i, F):
    up = (1 - eo(prog(i, 1, 2))) * 60

    def barf(d):
        rrect(d, (16, 212 + up, 304, 252 + up), 20, WHITE, INK, 2.6)
        ell(d, (28, 222 + up, 44, 238 + up), None, "#7A8798", 3)
        seg(d, [(41, 235 + up), (49, 244 + up)], "#7A8798", 3.4)
    vec(L, barf)
    chars = line("トナカイの検索は", "klee", 21, 58, 232 + up)
    n = 8 if T(i) >= 8 else max(0, int((T(i) - 2) * 1.4))
    draw(L, chars, "klee", lambda c: dict(fill=NAVY if c["j"] < 4 else INK, thick=1), lambda c: (0, 0, 1, 0) if c["j"] < n else None)
    cur_x = chars[n - 1]["x"] + chars[n - 1]["w"] / 2 + 3 if n else 58
    if T(i) < 8 or (i // 3) % 2 == 0:
        vec(L, lambda d: seg(d, [(cur_x, 222 + up), (cur_x, 242 + up)], "#3A7BD5", 2))
    u = prog(i, 8, 9.5)
    if u > 0:
        s = back(u)
        rot = (1 - eo(u)) * 360 + 6 * math.sin(i * 1.1)
        sub = new()
        vec(sub, lambda d: (poly(d, star(264, 172, 42, 34, 12), RED, INK, 2.4)))
        draw(sub, line("年イチ", "dela", 23, 264, 172, "c"), "dela", dict(fill=WHITE))
        b = sub.crop((220, 128, 309, 217))
        put(L, b, 264, 172, s, rot)
        if 9 <= T(i) <= 10:
            vec(L, lambda d: impact(d, 264, 172, 46, 54, 8, GOLD, 2.4))


# ==== 18 12月26日: 日めくりカレンダー(25日がやぶれて飛んでいく→26日) ====
def cal_page(day, col):
    sub = new()

    def fn(d):
        rrect(d, (104, 46, 218, 120), 6, WHITE, INK, 2.6)
        d.rectangle(X.P(106, 46, 216, 52), fill=WHITE)
    vec(sub, fn)
    draw(sub, line(day, "dela", 50, 158, 82, "c"), "dela", dict(fill=col))
    draw(sub, line("日", "zenkaku", 16, 200, 104, "c"), "zenkaku", dict(fill=col))
    draw(sub, line("SAT" if day == "26" else "FRI", "zenkaku", 10, 124, 110, "c"), "zenkaku", dict(fill=col))
    return sub


def s18(L, i, F):
    def base(d):
        rrect(d, (104, 14, 218, 122), 6, "#F4F4F4", INK, 2.6)
        rrect(d, (104, 14, 218, 46), 6, RED, INK, 2.6)
        d.rectangle(X.P(106, 34, 216, 45), fill=RED)
        for x in (132, 190):
            ell(d, (x - 6, 6, x + 6, 22), "#C9C9C9", INK, 2)
    vec(L, base)
    L.alpha_composite(cal_page("26", "#2E6FD8"))
    draw(L, line("12月", "zenkaku", 18, 161, 31, "c"), "zenkaku", dict(fill=WHITE))
    t = T(i)
    if t < 8:  # 25日のページ: やぶれて飛んでいく
        old = cal_page("25", INK)
        if t >= 4:
            u = (t - 4) / 4
            old = old.rotate(-u * 70, resample=Image.BICUBIC, center=(214, 46))
            X.comp(L, old, u * 90, u * u * 150)
        else:
            L.alpha_composite(old)
    if t >= 8:
        g = back(prog(i, 8, 9))
        if T(i) <= 10:
            vec(L, lambda d: [sparkle(d, x, y, 7 * g) for x, y in ((96, 70), (226, 60), (228, 110))])


# ==== カード(20コマ) ====
CARD = json.load(open(ROOT / "work/set05/base/cards.json")) if (ROOT / "work/set05/base/cards.json").exists() else {}


def pen(L, x, y):
    import newyear
    newyear.pen(L, x, y)


def write_on(L, i, chars, name, style, t0, per=0.7, show_pen=True):
    """ペンで1文字ずつ書く(書いている字にペンの先)。戻り値: 書き終わる時間。"""
    n = 0
    for k, c in enumerate(chars):
        if T(i) >= t0 + k * per:
            n = k + 1
    draw(L, chars, name, style, lambda c: (0, 0, 1, 0) if chars.index(c) < n else None)
    if show_pen and n < len(chars) and T(i) >= t0:
        c = chars[n - 1] if n else chars[0]
        pen(L, c["x"] + 6, c["y"] + 10)
    return t0 + len(chars) * per


def s11(L, i, F):  # いらねって返された: ペンで書く→「返品」のはんこ+なみだ
    l1 = line("いらねって", "kure", 32, 160, 66, "c")
    l2 = line("返された", "kure", 32, 160, 108, "c")
    st = dict(fill="#5C6F99", thick=1)
    allc = l1 + l2
    write_on(L, i, allc, "kure", lambda c: dict(fill="#5C6F99" if c in l1 else "#3F4E78", thick=1), 1, 0.9)
    u = prog(i, 11.5, 12.5)
    if u > 0:
        seal(L, 222, 146, 21, [("返品", 15, 0)], s=1 + (1 - eo(u)) * 1.6, rot=-14, square=True)
        if 12.5 <= T(i) <= 13.5:
            vec(L, lambda d: impact(d, 222, 146, 27, 36, 8, RED, 2.2))
    if T(i) >= 13:
        y = 128 + ((i * 4) % 22)
        x = l2[0]["x"] - 20
        vec(L, lambda d: poly(d, [(x, y - 8), (x + 5, y + 2), (x, y + 6), (x - 5, y + 2)], "#8FD3FF", INK, 1.4))


def s12(L, i, F):  # サンタ募集: 求人ポスター(見出しが落ちる→条件にチェック)
    drop = -(1 - bounce(prog(i, 1, 3))) * 80
    band = eo(prog(i, 3, 4.5))
    if band > 0:
        vec(L, lambda d: rrect(d, (82, 38, 82 + 156 * band, 70), 4, YEL, None))
    draw(L, line("サンタ募集", "zenkaku", 30, 160, 54 + drop, "c"), "zenkaku", dict(fill=RED, ow=2),
         lambda c: (0, 0, 1 + (0.06 * math.sin(i * 1.2) if T(i) > 14 else 0), 0))
    lab = back(prog(i, 5, 6))
    if lab > 0:
        vec(L, lambda d: rrect(d, (84, 80, 84 + 46 * lab, 98), 9, GREEN, None))
        if lab > 0.9:
            draw(L, line("条件", "zenkaku", 13, 107, 89, "c"), "zenkaku", dict(fill=WHITE))
    for k, (txt, t0) in enumerate((("70歳以上の白髭", 6.5), ("夜型", 9.5))):
        y = 114 + k * 26
        u = prog(i, t0, t0 + 1.5)
        if u <= 0:
            continue
        chars = line(txt, "klee", 18 if k == 0 else 22, 104, y, sizes=None)
        draw(L, chars, "klee", dict(fill=INK, thick=1), lambda c: (-(1 - eo(u)) * 40, 0, 1, 0))
        ck = prog(i, t0 + 1.5, t0 + 2.5)

        def box(d, y=y, ck=ck):
            rrect(d, (84, y - 8, 98, y + 6), 2, WHITE, INK, 1.8)
            if ck > 0:
                pts = [(86, y - 1), (90, y + 4), (100, y - 10)]
                seg(d, pts[:2] if ck < 0.5 else pts, RED, 3)
        vec(L, box)


def s16(L, i, F):  # 数か月後は暑くてクーラー: 雪のように字が降る→「暑くて」が赤くなる→「クーラー」の風
    l1 = line("数か月後は", "stick", 32, 160, 80, "c")

    def fx(c):
        u = prog(i, 1 + c["j"] * 0.9, 3 + c["j"] * 0.9)
        if u <= 0:
            return None
        return (8 * math.sin(u * 6 + c["j"]) * (1 - u), -(1 - eo(u)) * 50, 1, (1 - u) * 30)
    draw(L, l1, "stick", dict(fill="#D9EEFF", rw=2, rfill="#1B2A55", thick=1), fx)
    l2a = line("暑くて", "zenmaru", 28, 0, 126)
    l2b = line("クーラー", "zenmaru", 28, 0, 126)
    x0 = 150 - (width(l2a) + width(l2b) + 4) / 2
    l2a = line("暑くて", "zenmaru", 28, x0, 126)
    l2b = line("クーラー", "zenmaru", 28, x0 + width(l2a) + 4, 126)
    h = prog(i, 7, 11)
    if T(i) >= 7:
        cols = ["#7FC4FF", "#FFB36B", "#FF7A45", "#FF4B3A"]
        col = cols[min(3, int(h * 3.99))]
        draw(L, l2a, "zenmaru", dict(fill=col, ow=2, rw=2, rfill="#1B2A55"), lambda c: (0, 2 * math.sin(i * 1.4 + c["j"]), 1, 0))
        if h >= 1:  # 熱のゆらゆら
            vec(L, lambda d: [seg(d, [(x + 3 * math.sin(y * 0.4 + i), y) for y in range(104, 92, -2)], "#FF8A5C", 2)
                              for x in (l2a[0]["x"], l2a[2]["x"])])
    u = prog(i, 11, 13)
    if u > 0:
        draw(L, l2b, "zenmaru", dict(fill="#5CC8FF", ow=2, rw=2, rfill="#1B2A55"), lambda c: ((1 - eo(u)) * 90, 0, 1, 0))
        if u >= 1:  # 冷たい風
            def wind(d):
                x0 = l2b[-1]["x"] + 18
                for k in range(3):
                    ph = (i * 4 + k * 7) % 12
                    seg(d, [(x0 + ph, 112 + k * 9), (x0 + ph + 10, 110 + k * 9), (x0 + ph + 16, 114 + k * 9)], "#BFE8FF", 2)
            vec(L, wind)


def s19(L, i, F):  # 対面しないなら私服で良くね?: 字がくるっとめくれて出る+「私服」にマーカー+Tシャツ
    l1 = line("対面しないなら", "hachi", 29, 152, 92, "c")
    l2 = line("私服で良くね?", "hachi", 31, 146, 136, "c")
    m = eo(prog(i, 10, 12))
    if m > 0:
        x0, x1 = l2[0]["x"] - 15, l2[1]["x"] + 15
        vec(L, lambda d: rrect(d, (x0, 127, x0 + (x1 - x0) * m, 149), 3, "#FFE97A", None))

    def flip(t0):
        def fx(c):
            u = prog(i, t0 + c["j"] * 0.5, t0 + 1 + c["j"] * 0.5)
            if u <= 0:
                return None
            hop = -abs(6 * math.sin(i * 1.3)) if c["ch"] == "?" else 0
            return (0, hop, 1, 0, 1, max(0.05, back(u)))
        return fx
    draw(L, l1, "hachi", dict(fill=NAVY, thick=1), flip(1))
    draw(L, l2, "hachi", lambda c: dict(fill=RED if c["j"] < 2 else GREEN, thick=1), flip(5))
    s = back(prog(i, 12, 13))
    if s > 0:
        def shirt(d):
            cx, cy, k = 270, 136, s
            pts = [(-14, -12), (-6, -15), (0, -11), (6, -15), (14, -12), (20, -4), (13, 0), (11, -4), (11, 14), (-11, 14),
                   (-11, -4), (-13, 0), (-20, -4)]
            sw = 3 * math.sin(i * 0.9)
            poly(d, [(cx + x * k, cy + y * k + sw * (y < 0)) for x, y in pts], "#FF8A80", INK, 2)
            seg(d, [(cx - 11 * k, cy + 4), (cx + 11 * k, cy + 4)], WHITE, 2)
        vec(L, shirt)


def s20(L, i, F):  # 不在通知票: 赤い見出しが下りる→罫線→チェック→はんこ
    d1 = 0
    bw = eo(prog(i, 1, 2.2))  # 赤い見出しが真ん中から左右へ広がる
    vec(L, lambda d: rrect(d, (160 - 78 * bw, 32, 160 + 78 * bw, 68), 4, RED, INK, 2.2) if bw > 0.05 else None)
    title = line("不在通知票", "zenkaku", 27, 160, 50, "c")
    draw(L, title, "zenkaku", dict(fill=WHITE),
         lambda c: None if T(i) < 2 + c["j"] * 0.4 else (0, d1, back(prog(i, 2 + c["j"] * 0.4, 3 + c["j"] * 0.4)), 0))
    for k in range(3):
        y = 80 + k * 22
        w = eo(prog(i, 5 + k, 7 + k))

        def row(d, y=y, w=w, k=k):
            if w > 0:
                seg(d, [(104, y + 8), (104 + 128 * w, y + 8)], "#B8A88A", 1.6)
                rrect(d, (86, y - 4, 98, y + 8), 2, WHITE, INK, 1.6)
            if w >= 1:
                pts = [(108 + j * 6, y + 2 - 4 * math.sin(j * 1.7 + k)) for j in range(10 + k * 2)]
                seg(d, pts, "#6B7FA8", 1.6)  # 手書きのメモ
            if prog(i, 8 + k * 1.5, 9 + k * 1.5) > 0:
                seg(d, [(88, y + 1), (91, y + 6), (99, y - 6)], RED, 2.6)
        vec(L, row)
    u = prog(i, 13, 14)
    if u > 0:
        seal(L, 220, 136, 16, [("済", 18, 0)], s=1 + (1 - eo(u)) * 1.8, rot=-10)


def s21(L, i, F):  # 再配達、やってないから: 「再配達」に赤い禁止マーク+字が横からすべりこむ
    l1 = line("再配達、", "dela", 28, 160, 66, "c")
    draw(L, l1, "dela", dict(fill=INK, ow=2),
         lambda c: None if T(i) < 1 + c["j"] * 0.6 else (0, 0, back(prog(i, 1 + c["j"] * 0.6, 2 + c["j"] * 0.6)), 0))
    r = prog(i, 5, 7.5)
    if r > 0:
        def no(d):
            d.arc(X.P(88, 38, 220, 94), -90, -90 + 360 * r, fill=RED, width=5 * X.K)
            if T(i) >= 8:
                seg(d, [(112, 44), (196, 88)], RED, 5)
        vec(L, no)
    l2 = line("やってないから", "reggae", 22, 160, 118, "c")
    sub = new()
    draw(sub, l2, "reggae", dict(fill=RED, ow=3, rw=2),
         lambda c: None if T(i) < 9 + c["j"] * 0.4 else ((1 - eo(prog(i, 9 + c["j"] * 0.4, 10.5 + c["j"] * 0.4))) * 120, 0, 1, 0))
    clip(sub, (77, 28, 243, 242))  # カードの内側だけ
    L.alpha_composite(sub)


def s22(L, i, F):  # 来年はここには来ません: 上から下へ字が現れる→「来ません」がずーん(たて線)
    l1 = line("来年はここには", "kaisei", 26, 132, 112, "c")

    def wipe(c):
        u = prog(i, 1 + c["j"] * 0.7, 2 + c["j"] * 0.7)
        if u <= 0:
            return None
        return (0, -(1 - u) * 8, 1, 0, 1, max(0.05, eo(u)))
    draw(L, l1, "kaisei", dict(fill=NAVY, thick=1), wipe)
    u = prog(i, 9, 10.5)
    if u > 0:
        if T(i) >= 10:
            def gloom(d):
                for k in range(7):
                    x = 70 + k * 20
                    ln = 9 + 3 * math.sin(i * 0.8 + k)
                    seg(d, [(x, 131), (x, 131 + ln)], "#9AA6C2", 1.8)
            vec(L, gloom)
        draw(L, line("来ません", "kaisei", 38, 132, 172, "c"), "kaisei", dict(fill=RED, ow=2, thick=1),
             lambda c: (0, -(1 - bounce(u)) * 40 + (2 if T(i) > 11 else 0) * math.sin(i * 0.6 + c["j"]), 1, 0))


def s23(L, i, F):  # 今から質屋入れんだけど、たばこ行く?: ひそひそ吹き出し(点線)+ぼやけた字がはっきりする
    n = int(40 * eo(prog(i, 1, 4)))

    def bub(d):
        cx, cy, rx, ry = 160, 76, 80, 50
        for k in range(n):
            a0 = k / 40 * 2 * math.pi
            d.arc(X.P(cx - rx, cy - ry, cx + rx, cy + ry), math.degrees(a0), math.degrees(a0) + 5, fill="#8C7B6B", width=2 * X.K)
        if n >= 40:
            for k, (x, y, r) in enumerate(((104, 130, 4), (96, 140, 2.5))):
                ell(d, (x - r, y - r, x + r, y + r), None, "#8C7B6B", 1.6)
    vec(L, bub)
    rows = [("今から質屋に", 21, 50, 4, "#6B5B4E"), ("入れんだけど、", 21, 76, 6.5, "#6B5B4E"), ("たばこ行く?", 24, 104, 9.5, GREEN)]
    for txt, sz, y, t0, col in rows:
        chars = line(txt, "yomogi", sz, 160, y, "c")
        u = prog(i, t0, t0 + 2)
        if u <= 0:
            continue
        if u < 1:  # ぼやけ(うすい字がずれて重なる)→ぴたっ
            off = (1 - u) * 6
            for dx in (-off, off):
                draw(L, chars, "yomogi", dict(fill="#D8CEC4", thick=1), lambda c, dx=dx: (dx, 0, 1, 0))
        draw(L, chars, "yomogi", dict(fill=col, thick=1),
             lambda c: (0, 0, 1, (8 * math.sin(i * 1.1) if c["ch"] == "?" else 0)) if u >= 1 or u > 0.5 else None)


def s24(L, i, F):  # 年賀状もクリスマスも、もうやめない? 必要?: ペンで書く→間をおいて「必要?」がどーん
    l1 = line("年賀状もクリスマスも、", "klee", 21, 158, 70, "c")
    l2 = line("もうやめない?", "klee", 23, 158, 98, "c")
    end = write_on(L, i, l1 + l2, "klee",
                   lambda c: dict(fill=RED if c in l1 and 4 <= c["j"] <= 8 else INK, thick=1), 1, 0.5)
    u = prog(i, end + 1.5, end + 2.5)
    if u > 0:
        big = line("必要?", "mochiy", 34, 96, 140, "c")
        draw(L, big, "mochiy", lambda c: dict(fill=GREEN if c["ch"] == "?" else RED, ow=3, rw=2),
             lambda c: (0, -abs(5 * math.sin(i * 1.3)) if c["ch"] == "?" else 0, 1 + (1 - eo(u)) * 1.2,
                        (10 * math.sin(i * 0.9) if c["ch"] == "?" else 0)))


SPECS = {f"{k:02d}": globals()[f"s{k:02d}"] for k in range(1, 25)}


# ==== 書き出し ====

def frames_of(n):
    base = Image.open(ROOT / f"work/set05/base/{n}.png").convert("RGBA")
    cols = 5 if n in CARDS else 4
    F = 20 if n in CARDS else 12
    M = 11  # 文字は縁から 11px 以上あける
    layers = []
    for i in range(F):
        L = new()
        SPECS[n](L, i, F)
        layers.append(L)
    # できあがり(1コマ目)の文字がはみ出すときは、全コマの文字を同じだけ縮めて内側へずらす(絵は動かさない)
    b = layers[0].getbbox()
    k, dx, dy = 1.0, 0, 0
    if b:
        k = min(1.0, (CW - 2 * M) / (b[2] - b[0]), (CH - 2 * M) / (b[3] - b[1]))
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        hw, hh = (b[2] - b[0]) * k / 2, (b[3] - b[1]) * k / 2
        ncx = min(max(cx, M + hw), CW - M - hw)
        ncy = min(max(cy, M + hh), CH - M - hh)
        dx, dy = ncx - cx, ncy - cy
    out = []
    for i, L in enumerate(layers):
        if k < 1.0 or dx or dy:
            T_ = new()
            im = L.resize((round(CW * k), round(CH * k)), Image.LANCZOS) if k < 1.0 else L
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            X.comp(T_, im, cx + dx - cx * k, cy + dy - cy * k)
            L = T_
        clip(L, (M, M, CW - M, CH - M))  # 出てくる途中も縁の外には描かない
        x0, y0 = (i % cols) * CW, (i // cols) * CH
        cell = base.crop((x0, y0, x0 + CW, y0 + CH))
        cell.alpha_composite(L)
        out.append(cell)
    return out, cols


def save(frames, cols, path):
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (CW * cols, CH * rows), (0, 255, 0, 255))
    for i, c in enumerate(frames):
        sheet.alpha_composite(c, ((i % cols) * CW, (i // cols) * CH))
    sheet.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stamp", choices=sorted(SPECS))
    ap.add_argument("--png", required=True)
    a = ap.parse_args()
    frames, cols = frames_of(a.stamp)
    save(frames, cols, a.png)
    print(f"シート: {a.png}", file=sys.stderr)


if __name__ == "__main__":
    main()
