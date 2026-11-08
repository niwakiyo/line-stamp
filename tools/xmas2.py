#!/usr/bin/env python3
"""set04 クリスマス: 残りの22個(02〜04・06〜24)。xmas.py のサンタ・トナカイ・ツリー・そりを使う。

  確認用シート : python3 tools/xmas2.py 02 --png sheet.png
  (キャラのスタンプは 12コマ=4x3、手書きのセリフとカードは 20コマ=5x4)

守ること(docs/user_profile.md・docs/stamp_rules.md):
- 構図を4つに区切らない。大きな季節の物をキャラの後ろ(back)や前(front)に重ね、1枚の絵にする
- キャラは移動・ジャンプ・大きな腕や足の動き。飾りも動く。最後のコマまで何も消えない
- 小物は形・色・光で工夫(1色・直線・丸だけにしない)。背景の物は使い回さない
- 文字はカーブ・段差・色の変化。小さい文字はフチを細く
"""
import argparse
import math
import random
import tempfile

from PIL import Image, ImageDraw, ImageFont

import inko
import soft
import winter
import newyear
import xmas
from soft import kf, S, J0, J1, J2, B1, B2, happy, blink
from winter import make, sh
from xmas import (P, santa, reindeer, talk_santa, talk_deer, tree, tree_page, star_path, sleigh_image, both, snowf,
                  RED, RED_D, GREEN, GREEN_D, GOLD, WHITE)

CW, CH = 320, 270
L = soft.LINE


# ---- 小物の絵(3倍で描いて縮める) ---------------------------------------------------

def art(w, h, fn):
    S3 = 3
    im = Image.new("RGBA", (w * S3, h * S3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def p(*xy):
        return [v * S3 for v in xy]
    fn(d, p, S3)
    return im.resize((w, h), Image.LANCZOS)


def wreath_img(sz, t=0):
    """リース: 深い緑の葉を輪に重ね(2色)、赤い実のかたまり、金の小さな玉、下に大きな赤いリボン。"""
    def fn(d, p, k):
        c, R = sz / 2, sz * 0.36
        for j in range(26):
            a = j / 26 * 2 * math.pi
            x, y = c + R * math.cos(a), c + R * math.sin(a)
            r = sz * 0.13
            d.ellipse(p(x - r, y - r * 0.8, x + r, y + r * 0.8), fill="#3E9A6C" if j % 2 else GREEN, outline=L, width=2 * k)
        for j in range(7):
            a = j / 7 * 2 * math.pi + 0.3
            x, y = c + R * math.cos(a), c + R * math.sin(a)
            for dx, dy in ((-3, 0), (3, -2), (0, 3)):
                d.ellipse(p(x + dx - 3, y + dy - 3, x + dx + 3, y + dy + 3), fill=RED, outline=L, width=k)
        for j in range(7):
            a = j / 7 * 2 * math.pi + 0.75
            x, y = c + R * math.cos(a), c + R * math.sin(a)
            col = GOLD if (j + t) % 2 else "#FFF2B0"  # 金の玉がかわるがわる光る
            d.ellipse(p(x - 3.5, y - 3.5, x + 3.5, y + 3.5), fill=col, outline=L, width=k)
        bx, by = c, c + R
        d.polygon(p(bx - 4, by, bx - 14, by + 24, bx - 6, by + 22, bx - 1, by + 4), fill=RED_D, outline=L)
        d.polygon(p(bx + 4, by, bx + 14, by + 24, bx + 6, by + 22, bx + 1, by + 4), fill=RED_D, outline=L)
        d.ellipse(p(bx - 22, by - 10, bx - 2, by + 6), fill=RED, outline=L, width=2 * k)
        d.ellipse(p(bx + 2, by - 10, bx + 22, by + 6), fill=RED, outline=L, width=2 * k)
        d.ellipse(p(bx - 6, by - 6, bx + 6, by + 4), fill=RED, outline=L, width=2 * k)
    return art(sz, sz + 20, fn)


def gift_img(w, h, body, rib, lid=True):
    """プレゼント: ふた・リボン十字・リボン結び。ふたは少し濃い色。"""
    def fn(d, p, k):
        top = h * 0.32
        d.rounded_rectangle(p(2, top, w - 2, h - 2), radius=3 * k, fill=body, outline=L, width=2 * k)
        if lid:
            d.rounded_rectangle(p(0, top - 6, w, top + 4), radius=3 * k, fill=body, outline=L, width=2 * k)
        d.rectangle(p(w / 2 - 3, top - 5, w / 2 + 3, h - 3), fill=rib)
        d.rectangle(p(3, top + (h - top) / 2 - 3, w - 3, top + (h - top) / 2 + 3), fill=rib)
        bw = min(w * 0.3, 16)
        d.ellipse(p(w / 2 - bw - 1, top - 6 - bw * 0.7, w / 2 + 1, top - 3), fill=rib, outline=L, width=2 * k)
        d.ellipse(p(w / 2 - 1, top - 6 - bw * 0.7, w / 2 + bw + 1, top - 3), fill=rib, outline=L, width=2 * k)
        d.ellipse(p(w / 2 - 4, top - 9, w / 2 + 4, top - 2), fill=rib, outline=L, width=2 * k)
    return art(w, h, fn)


def pile_img():
    """プレゼントの山: 大きさ・色のちがう箱を4つ重ねる。"""
    im = Image.new("RGBA", (130, 110), (0, 0, 0, 0))
    for (x, y, w, h, b, r) in ((4, 46, 54, 62, RED, GOLD), (56, 56, 46, 52, GREEN, RED), (96, 70, 32, 38, "#7FC4FF", WHITE),
                               (26, 6, 42, 46, GOLD, RED)):
        im.alpha_composite(gift_img(w, h, b, r), (x, y))
    return im


def table_img(w, t=0):
    """テーブル(前に置く): 赤いテーブルクロスに白いレースのすそ、金のライン。"""
    def fn(d, p, k):
        d.rounded_rectangle(p(2, 2, w - 2, 34), radius=4 * k, fill=RED, outline=L, width=2 * k)
        d.line(p(6, 12, w - 6, 12), fill=GOLD, width=2 * k)
        for j in range(int(w / 16) + 1):
            x = 6 + j * 16
            if x + 8 <= w - 2:
                d.ellipse(p(x, 28, x + 16, 42), fill=WHITE, outline=L, width=2 * k)
    return art(w, 44, fn)


def chicken_img(t=0):
    """ローストチキン: 白いお皿、こんがりチキン(つや)、白い飾り紙の骨2本、緑のハーブと赤いミニトマト。"""
    def fn(d, p, k):
        d.ellipse(p(2, 40, 118, 66), fill=WHITE, outline=L, width=2 * k)
        d.ellipse(p(10, 44, 110, 62), outline="#BFE0F5", width=2 * k)
        d.ellipse(p(22, 14, 98, 56), fill="#C9772E", outline=L, width=2 * k)
        d.ellipse(p(36, 20, 66, 34), fill="#E6A15A")  # つや
        d.ellipse(p(44, 22, 54, 27), fill="#F7D29A")
        for side in (-1, 1):
            x0 = 60 + side * 34
            d.line(p(60 + side * 22, 30, x0, 14), fill=L, width=9 * k)
            d.line(p(60 + side * 22, 30, x0, 14), fill="#F3E3CC", width=5 * k)
            for j in range(4):  # 飾り紙(白いひらひら)
                d.ellipse(p(x0 - 7 + j * 3.5 * side * 0 - 4 + j * 2.5, 4 + (j % 2) * 3, x0 - 4 + j * 2.5 + 6, 12 + (j % 2) * 3),
                          fill=WHITE, outline=L, width=k)
        for x in (16, 100):
            d.ellipse(p(x - 7, 46, x + 7, 58), fill=GREEN, outline=L, width=k)
        d.ellipse(p(12, 48, 22, 58), fill=RED, outline=L, width=k)
        d.ellipse(p(98, 48, 108, 58), fill=RED, outline=L, width=k)
    return art(120, 70, fn)


def cake_img(t=0):
    """いちごのショートケーキ(ホール): 白いクリームのふちどり、赤いいちご、ろうそく3本(赤白しま)の炎がゆれる。"""
    def fn(d, p, k):
        d.ellipse(p(2, 84, 138, 104), fill="#EAF6FF", outline=L, width=2 * k)  # お皿
        d.rounded_rectangle(p(14, 50, 126, 94), radius=10 * k, fill="#FFF7EE", outline=L, width=2 * k)
        d.ellipse(p(14, 40, 126, 62), fill=WHITE, outline=L, width=2 * k)
        for j in range(8):  # 横のいちごの断面ライン
            x = 22 + j * 13
            d.ellipse(p(x, 66, x + 9, 74), fill="#F49CA8")
        for j in range(7):  # 上のクリームとふちのしぼり
            x = 20 + j * 15
            d.ellipse(p(x - 2, 88, x + 12, 98), fill=WHITE, outline=L, width=k)
        for j, x in enumerate((30, 52, 88, 108)):  # いちご
            d.polygon(p(x - 7, 44, x + 7, 44, x, 56), fill=RED, outline=L)
            d.ellipse(p(x - 7, 38, x + 7, 50), fill=RED, outline=L, width=k)
            d.polygon(p(x - 5, 39, x + 5, 39, x, 34), fill=GREEN)
        for j, x in enumerate((48, 70, 92)):  # ろうそくと炎
            d.rounded_rectangle(p(x - 4, 14, x + 4, 48), radius=2 * k, fill=WHITE, outline=L, width=k)
            for yy in (20, 30, 40):
                d.line(p(x - 3, yy, x + 3, yy - 3), fill=RED, width=2 * k)
            sway = 2.5 * math.sin(t * 1.4 + j)
            hgt = 12 + 3 * math.sin(t * 2.1 + j * 2)
            d.ellipse(p(x - 5 + sway, 14 - hgt, x + 5 + sway, 15), fill="#FFB43C", outline=L, width=k)
            d.ellipse(p(x - 2.5 + sway, 14 - hgt * 0.6, x + 2.5 + sway, 13), fill="#FFF2B0")
    return art(140, 106, fn)


def snowman_img(t=0):
    """雪だるま: 大小の白い玉(水色のかげ)、赤いマフラー(先がゆれる)、黒いシルクハットと赤い帯、
    人参の鼻、炭の目と口、ボタン、枝の腕(左右で別にふる)。"""
    def fn(d, p, k):
        d.ellipse(p(14, 70, 106, 150), fill=WHITE, outline=L, width=2 * k)
        d.ellipse(p(20, 120, 100, 148), fill="#E3F1FB")
        d.ellipse(p(28, 22, 92, 82), fill=WHITE, outline=L, width=2 * k)
        a1 = math.radians(-30 + 14 * math.sin(t * 1.2))
        a2 = math.radians(210 + 10 * math.sin(t * 1.2 + 1.5))
        for (x0, y0, a) in ((96, 92, a1), (24, 92, a2)):
            x1, y1 = x0 + 30 * math.cos(a), y0 + 30 * math.sin(a)
            d.line(p(x0, y0, x1, y1), fill="#7A5236", width=4 * k)
            d.line(p((x0 + x1) / 2, (y0 + y1) / 2, (x0 + x1) / 2 + 8 * math.cos(a - 0.8), (y0 + y1) / 2 + 8 * math.sin(a - 0.8)),
                   fill="#7A5236", width=3 * k)
        d.rounded_rectangle(p(30, 72, 90, 84), radius=5 * k, fill=RED, outline=L, width=2 * k)  # マフラー
        sw = 4 * math.sin(t * 1.5)
        d.polygon(p(72, 80, 84, 80, 88 + sw, 112, 76 + sw, 112), fill=RED, outline=L)
        d.line(p(74 + sw * 0.6, 100, 86 + sw * 0.6, 100), fill=WHITE, width=2 * k)
        d.rounded_rectangle(p(36, 22, 84, 28), radius=2 * k, fill="#2E2A2A", outline=L, width=2 * k)  # 帽子
        d.rounded_rectangle(p(44, -2 + 2, 76, 24), radius=3 * k, fill="#2E2A2A", outline=L, width=2 * k)
        d.rectangle(p(45, 16, 75, 21), fill=RED)
        d.ellipse(p(70, 12, 78, 20), fill=GREEN, outline=L, width=k)
        for x in (48, 66):
            d.ellipse(p(x, 44, x + 6, 51), fill="#2E2A2A")
        d.polygon(p(58, 54, 60, 60, 80, 60), fill="#F28A2E", outline=L)
        for j, x in enumerate((50, 55, 60, 65, 70)):
            d.ellipse(p(x - 1.5, 64 + abs(j - 2) * -1.5 + 3, x + 1.5, 67 + abs(j - 2) * -1.5 + 3), fill="#2E2A2A")
        for y in (96, 112, 128):
            d.ellipse(p(57, y, 63, y + 6), fill="#2E2A2A")
        d.ellipse(p(36, 56, 46, 62), fill="#FFC4D2")
        d.ellipse(p(74, 56, 84, 62), fill="#FFC4D2")
    return art(120, 152, fn)


def fireplace_img(t=0):
    """暖炉: れんが色の囲い、白いマントル、ゆれる炎、上に緑のガーランドと点滅する電球、くつした3つ。"""
    def fn(d, p, k):
        d.rounded_rectangle(p(4, 30, 156, 150), radius=4 * k, fill="#B5523B", outline=L, width=2 * k)
        for r in range(6):
            for cidx in range(8):
                off = 10 if r % 2 else 0
                x = 6 + cidx * 20 + off
                y = 40 + r * 18
                if x + 18 < 154:
                    d.rounded_rectangle(p(x, y, x + 18, y + 16), radius=2 * k, outline="#8E3B2A", width=k)
        d.rounded_rectangle(p(40, 70, 120, 150), radius=30 * k, fill="#3A2E2E", outline=L, width=2 * k)
        for j in range(3):
            x = 60 + j * 20
            h = 30 + 8 * math.sin(t * 1.7 + j * 1.3)
            d.ellipse(p(x - 12, 146 - h, x + 12, 146), fill="#F28A2E", outline=L, width=k)
            d.ellipse(p(x - 6, 146 - h * 0.6, x + 6, 146), fill="#FFD24D")
        d.rounded_rectangle(p(46, 140, 114, 150), radius=3 * k, fill="#7A5236", outline=L, width=k)
        d.rounded_rectangle(p(0, 22, 160, 36), radius=4 * k, fill="#FFF7EE", outline=L, width=2 * k)
        for j in range(9):  # ガーランド
            x = 8 + j * 18
            d.ellipse(p(x - 9, 10, x + 9, 26), fill=GREEN if j % 2 else GREEN_D, outline=L, width=k)
        cols = [RED, GOLD, "#7FC4FF", WHITE]
        for j in range(8):
            x = 16 + j * 18
            d.ellipse(p(x - 3.5, 20, x + 3.5, 28), fill=cols[(j + t) % 4], outline=L, width=k)
        for j, (x, col) in enumerate(((30, RED), (80, GREEN), (130, RED))):  # くつした(左右に少しゆれる)
            sw = 3 * math.sin(t * 1.3 + j)
            pts = [(x - 9 + sw, 36), (x + 9 + sw, 36), (x + 9 + sw * 1.5, 62), (x + 18 + sw * 1.6, 66),
                   (x + 18 + sw * 1.6, 76), (x - 2 + sw * 1.5, 76), (x - 9 + sw * 1.4, 66)]
            d.polygon(p(*sum(pts, ())), fill=col, outline=L)
            d.rounded_rectangle(p(x - 11 + sw, 34, x + 11 + sw, 44), radius=3 * k, fill=WHITE, outline=L, width=k)
    return art(160, 152, fn)


def night_img():
    """夜空: 大きな三日月(金)と、まわりの雲。"""
    def fn(d, p, k):
        d.ellipse(p(10, 6, 70, 66), fill="#FFE27A", outline=L, width=2 * k)
        d.ellipse(p(26, -2, 82, 54), fill=(0, 0, 0, 0))
        d.ellipse(p(26, -2, 82, 54), outline=None)
    im = art(84, 70, fn)
    # 三日月にする: 右上の丸をくりぬく
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse((28, 0, 84, 52), fill=255)
    a = im.getchannel("A")
    im.putalpha(Image.composite(Image.new("L", im.size, 0), a, mask))
    d = ImageDraw.Draw(im)
    d.arc((28, 0, 84, 52), 105, 205, fill=L, width=2)
    return im


def village_img():
    """雪の村: 白い丘(水色のかげ)、雪の屋根の家3けん(窓に明かり)、小さなツリー。"""
    def fn(d, p, k):
        d.ellipse(p(-60, 60, 200, 180), fill=WHITE, outline=L, width=2 * k)
        d.ellipse(p(140, 70, 380, 190), fill="#F4FAFF", outline=L, width=2 * k)
        d.ellipse(p(-20, 120, 340, 220), fill=WHITE, outline=L, width=2 * k)
        for (x, y, w, h, col) in ((40, 52, 50, 44, "#E8A486"), (110, 62, 44, 38, "#F3D9A8"), (220, 66, 54, 46, "#D98C7A")):
            d.rectangle(p(x, y, x + w, y + h), fill=col, outline=L, width=2 * k)
            d.polygon(p(x - 8, y + 2, x + w / 2, y - 22, x + w + 8, y + 2), fill=RED_D, outline=L)
            d.polygon(p(x - 10, y + 4, x + w / 2, y - 20, x + w + 10, y + 4, x + w / 2, y - 12), fill=WHITE, outline=L)
            d.rectangle(p(x + 8, y + 12, x + 20, y + 24), fill="#FFD24D", outline=L, width=k)
            d.rectangle(p(x + w - 20, y + 12, x + w - 8, y + 24), fill="#FFD24D", outline=L, width=k)
        for x in (180, 300):
            d.polygon(p(x, 40, x - 16, 80, x + 16, 80), fill=GREEN, outline=L)
            d.polygon(p(x - 14, 50, x, 40, x + 14, 50, x, 46), fill=WHITE)
    return art(320, 160, fn)


def card_img(kind=0):
    """クリスマスカード(角は丸くしない四角い紙): 生成りの紙、赤い太わくと金の細わく、角にヒイラギ。"""
    def fn(d, p, k):
        x0, y0, x1, y1 = 4, 4, 156, 244
        d.rectangle(p(x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill=WHITE)
        d.rectangle(p(x0, y0, x1, y1), fill="#FFF9EE", outline=L, width=2 * k)
        d.rectangle(p(x0 + 5, y0 + 5, x1 - 5, y1 - 5), outline=RED if kind % 2 == 0 else GREEN, width=4 * k)
        d.rectangle(p(x0 + 11, y0 + 11, x1 - 11, y1 - 11), outline=GOLD, width=k)
        for (cx, cy, fl) in ((x0 + 14, y0 + 14, 1), (x1 - 14, y1 - 14, -1)):
            for a in (-0.5, 0.9):
                ex, ey = cx + 12 * math.cos(a) * fl, cy + 12 * math.sin(a) * fl
                d.ellipse(p(min(cx, ex) - 4, min(cy, ey) - 4, max(cx, ex) + 4, max(cy, ey) + 4), fill=GREEN, outline=L, width=k)
            for dx, dy in ((0, 0), (5, -3), (3, 4)):
                d.ellipse(p(cx + dx * fl - 3.5, cy + dy * fl - 3.5, cx + dx * fl + 3.5, cy + dy * fl + 3.5), fill=RED, outline=L, width=k)
    return art(160, 248, fn)


# ---- 置き方 -----------------------------------------------------------------------

def put_img(layer, im, x, y, k=1.0, rot=0):
    """im を中心 (x, y)・k倍・rot 度で置く。"""
    if k != 1.0:
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    layer.alpha_composite(im, (round(x - im.width / 2), round(y - im.height / 2)))


def with_layers(frames, back=None, front=None):
    """各コマに、キャラの後ろ(back)と前(front)に描く絵の関数をつける。f(layer, i) の形。"""
    for i, fr in enumerate(frames):
        fr["back"] = (lambda layer, i=i: back(layer, i)) if back else None
        fr["front"] = (lambda layer, i=i: front(layer, i)) if front else None
    return frames


def paths(frames, path):
    for i, fr in enumerate(frames):
        fr["anchor"] = path[i]
    return frames


# ---- サンタの動き(左右の腕は別々・帽子は遅れてゆれる) ------------------------------

def santa_moves(al, ar, hat, hl=None, hr=None, **extra):
    hl = hl or [0] * 12
    hr = hr or [0] * 12
    # al・ar はどちらも「外へ上げる角度」(xmas.santa の arm_part は両腕とも正で外・上へ開く。符号は反転しない)
    # 60 で肩の高さ、100 以上で頭の上まで上がる
    return [dict(al=al[i], ar=ar[i], hat=hat[i], hl=hl[i], hr=hr[i], **extra) for i in range(12)]


HAT_SWING = [0, -8, -14, -6, 10, 16, 8, -6, -12, -4, 8, 4]

STAMPS = {}
SANTA, DEER = set(), set()

def char_icon(name, height, pose=None):
    """カードのすみに描く、小さなサンタ・トナカイ(キャラと同じ図形)。pose で腕などを変えられる。"""
    fn = santa if name == "santa" else reindeer
    fr = [kf([S, happy, P(gift=False, hold=None, **(pose or {})), fn], scale=1.0, anchor=(160, 258))]
    with tempfile.TemporaryDirectory() as tmp:
        soft.chara_png(fr, f"{tmp}/s.png")
        im = Image.open(f"{tmp}/s.png").convert("RGBA").crop((0, 0, CW, CH))
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    im = im.crop(im.getbbox())
    k = height / im.height
    return im.resize((round(im.width * k), height), Image.LANCZOS)



GOLD_T = xmas.GOLD_T


def twinkles(pts, i, base=7):
    """またたく星: 場所ごとに大きさが順番に変わる。"""
    return [("spark", x, y, base + ((i + j) % 3) * 3) for j, (x, y) in enumerate(pts)]


# 02 プレゼントです: サンタが大きなプレゼントを前へさし出して跳ねる。うしろのプレゼントの山はキラキラ光る
MV02 = santa_moves([0, 10, 24, 36, 44, 50, 44, 36, 24, 36, 44, 36], [0, 10, 26, 40, 26, 10, -4, 10, 28, 42, 28, 12], HAT_SWING,
                   hl=[0, 3, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0], hold="biggift")
PATH02 = [(140, 256), (140, 250), (140, 240), (140, 248), (140, 256), (140, 256), (140, 256), (140, 246), (140, 236),
          (140, 246), (140, 256), (140, 256)]
POSE02 = [S, J0, J1, J0, S, S, S, J0, J1, J0, S, S]
STAMPS["02"] = with_layers(paths(make(
    "xmas", [("プレゼント", 34, True), ("です", 32, False)], "A",
    lambda i: [POSE02[i], happy, P(**MV02[i]), santa],
    lambda i, av: winter.confetti(2, 7, i, box=(24, 30, 120, 110)) + [("spark", x, y, (8, 13, 19, 13)[(i + j) % 4]) for j, (x, y) in enumerate(((212, 146), (264, 132), (298, 170), (238, 190), (286, 212), (204, 226)))],
    m=dict(scale=0.94, anchor=PATH02[0]), x0=126), PATH02), back=lambda L_, i: put_img(L_, pile_img(), 248, 196, 1.15))
SANTA.add("02")


# 03 今年もありがとう: 大きなリース(大きな玉・金のベル・大きなリボン)の前で、サンタが右腕(見て左)で大きく手をふる
def wreath_big(sz, t=0):
    """豪華なリース: 葉の輪の上に、大きなつやのある玉(赤・金・青・白)、金のベル3つ、赤い実、上に大きな赤いリボン。
    玉は順番に光る(光った玉は白いつやが大きくなる)。"""
    base = wreath_img(sz, t)

    def fn(d, p, k):
        c, R = sz / 2, sz * 0.36
        cols = [RED, GOLD, "#7FC4FF", RED, WHITE, GOLD, "#C83A6A"]
        for j in range(10):
            a = j / 10 * 2 * math.pi + 0.95
            x, y = c + R * math.cos(a), c + 10 + R * math.sin(a)
            r = 12 if j % 2 == 0 else 9.5
            col = cols[j % len(cols)]
            lit = (j + t) % 4 == 0
            d.line(p(x, y - r, x, y - r - 4), fill=L, width=2 * k)  # つり糸
            d.rounded_rectangle(p(x - 3.5, y - r - 4, x + 3.5, y - r + 1), radius=k, fill=GOLD, outline=L, width=k)
            d.ellipse(p(x - r, y - r, x + r, y + r), fill=col, outline=L, width=2 * k)
            d.arc(p(x - r * 0.75, y - r * 0.75, x + r * 0.75, y + r * 0.75), 20, 160, fill=L, width=k)  # 玉のもよう
            g = 0.55 if lit else 0.32
            d.ellipse(p(x - r * 0.62, y - r * 0.66, x - r * 0.62 + r * g * 1.3, y - r * 0.66 + r * g), fill=WHITE)
        for a in (-2.5, -0.65, 3.9):  # 金のベル(大きめ、ゆれる)
            x, y = c + R * math.cos(a), c + 10 + R * math.sin(a)
            sw = 0.35 * math.sin(t * 1.3 + a)
            q = lambda u, v: (x + u * math.cos(sw) - v * math.sin(sw), y + u * math.sin(sw) + v * math.cos(sw))
            pts = [q(-11, 11), q(-8, -5), q(0, -11), q(8, -5), q(11, 11)]
            d.polygon(p(*[v for pt in pts for v in pt]), fill=GOLD, outline=L, width=2 * k)
            hx, hy = q(0, 12)
            d.ellipse(p(hx - 4, hy - 3, hx + 4, hy + 5), fill="#B8860B", outline=L, width=k)
        # 上の大きなリボン(赤、金のふち)
        bx, by = c, c + 10 - R
        for sgn in (-1, 1):
            d.polygon(p(bx, by, bx + sgn * 30, by - 16, bx + sgn * 34, by + 2, bx + sgn * 26, by + 12), fill=RED, outline=L, width=2 * k)
            d.line(p(bx + sgn * 6, by - 2, bx + sgn * 26, by - 10), fill=RED_D, width=2 * k)
            d.polygon(p(bx + sgn * 3, by + 4, bx + sgn * 16, by + 34, bx + sgn * 8, by + 30, bx + sgn * 2, by + 38), fill=RED_D, outline=L, width=k * 2)
        d.ellipse(p(bx - 8, by - 7, bx + 8, by + 8), fill=RED, outline=L, width=2 * k)
        d.ellipse(p(bx - 3, by - 4, bx + 1, by - 1), fill=WHITE)
    deco = art(sz, sz + 20, fn)
    base.alpha_composite(deco, (0, -10))
    return base


# リースは小さく現れて、だんだん大きくなる(1コマ目は完成形。2コマ目から小→大、最後は少しふくらんでゆっくり息をする)
GROW = [1.0, 0.36, 0.46, 0.56, 0.66, 0.76, 0.85, 0.93, 1.0, 1.05, 1.02, 1.0]


MV03 = santa_moves([0, 70, 110, 90, 122, 92, 118, 90, 122, 92, 114, 96], [0, 6, 10, 6, 12, 6, 10, 6, 12, 6, 10, 6],
                   [0, 6, -4, -12, -6, 6, 14, 6, -6, -10, 4, 0], gift=False, hold=None)
POSE03 = [S, S, J0, S, J0, S, S, S, J0, S, J0, S]
STAMPS["03"] = with_layers(paths(make(
    "xmas", [("今年も", 42, True), ("ありがとう", 34, True)], "A",
    lambda i: [POSE03[i], happy, P(**MV03[i]), santa],
    lambda i, av: [("heart", 30 + j * 40, 240 - ((i * 14 + j * 40) % 100), 14 + j % 2 * 4) for j in range(3)],
    m=dict(scale=0.9, anchor=(214, 256)), x0=20), [(214 - i * 2 if i < 6 else 202 + (i - 6) * 2, 256) for i in range(12)]),
    back=lambda L_, i: put_img(L_, wreath_big(170, i), 222, 132 - (1 - GROW[i]) * 86, GROW[i]))  # 上のはしをそろえて大きくなる(サンタにかくれない)
SANTA.add("03")

# 04 いい子にしてた?: くつしたのガーランドがゆれる。サンタは右から歩いてきて、両手を高く上げて手をふる。
#    「?」は3つ、形(大きさ・色・かたむき)がちがい、順番に跳ねる
POSE04 = [S, S, J0, S, J0, S, S, J0, S, J0, S, S]
MV04 = santa_moves([0, 60, 100, 122, 98, 124, 100, 122, 98, 124, 104, 118], [0, 70, 122, 98, 122, 100, 124, 98, 122, 100, 118, 104],
                   HAT_SWING, hl=[0, 3, 0, 3, 0, 3, 0, 0, 0, 0, 0, 0], hr=[0, 0, 3, 0, 3, 0, 0, 0, 0, 0, 0, 0], hold=None)
PATH04 = [(226, 262), (238, 258), (235, 262), (232, 262), (229, 258), (227, 262), (226, 262), (226, 256), (226, 262),
          (226, 256), (226, 262), (226, 262)]


_STOCK = {}


def stocking_img(kind, sc, t=0):
    """クリスマスの靴下(1足): ふわふわの白い口(波のふち)、かかと・つま先の別色、柄、口からのぞくプレゼントやキャンディ。
    kind ごとに色・柄・のぞく物を変える。つり下げる点は画像の上の真ん中(ひもの輪)。"""
    key = (kind, sc, 0)
    t = 0  # 1コマごとに絵を変えない(チカチカさせない)
    if key in _STOCK:
        return _STOCK[key]
    K = 3 * sc
    W, H = int(52 * K), int(92 * K)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P_ = lambda pts: [(x * K, y * K) for x, y in pts]
    lw = max(2, round(2.2 * K))
    ox, oy = 8, 26  # 靴下の左上(上にのぞく物と、ひもの輪のぶん空ける)
    q = lambda pts: P_([(x + ox, y + oy) for x, y in pts])
    bz = xmas._bez
    shape = (bz((4, 10), (3, 24), (2, 34), (4, 42)) + bz((4, 42), (6, 56), (22, 60), (34, 58))
             + bz((34, 58), (44, 56), (44, 44), (34, 42)) + bz((34, 42), (29, 41), (27, 36), (27, 28)) + [(27, 10)])
    body, heel, pat, cuffdeco, peek = [
        (RED, GREEN, "snow", "holly", "cane"),
        (GREEN, RED, "stripe", "bell", "gift"),
        (WHITE, RED, "candy", "pom", "star"),
        (RED, GOLD, "zigzag", "holly", "gift2"),
        (GREEN, GOLD, "dots", "bell", "cane"),
    ][kind]
    # のぞく物(靴下のうしろ、口の上へ)
    if peek == "cane":
        c = bz((14, 14), (14, -6), (14, -16), (20, -18)) + bz((20, -18), (27, -20), (28, -10), (24, -8))
        d.line(q(c), fill=L, width=round(7 * K), joint="curve")
        d.line(q(c), fill=WHITE, width=round(4.4 * K), joint="curve")
        for j in range(0, len(c) - 2, 3):
            d.line(q(c[j:j + 2]), fill=RED, width=round(4.4 * K))
    elif peek in ("gift", "gift2"):
        col, rib = (GOLD, RED) if peek == "gift" else ("#7FC4FF", WHITE)
        d.rounded_rectangle(q([(9, -6), (25, 10)]), radius=2 * K, fill=col, outline=L, width=lw)
        d.rectangle(q([(15.5, -5), (18.5, 9)]), fill=rib)
        for sx in (-1, 1):
            d.ellipse(q([(17 + sx * 6 - 4, -12), (17 + sx * 6 + 4, -5)]), fill=rib, outline=L, width=lw)
    elif peek == "star":
        pts = [(17 + (9 if j % 2 == 0 else 4) * math.sin(j * math.pi / 5), -6 - (9 if j % 2 == 0 else 4) * math.cos(j * math.pi / 5)) for j in range(10)]
        d.line(q([(17, 2), (17, 10)]), fill=L, width=round(3 * K))
        d.polygon(q(pts), fill=GOLD, outline=L, width=lw)
        d.ellipse(q([(13, -9), (16, -6)]), fill="#FFF6C8")
    # 本体と柄(柄は靴下の形で切り抜く)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon(q(shape), fill=255)
    pl = Image.new("RGBA", im.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    pd.rectangle((0, 0, W, H), fill=body)
    if pat == "snow":
        for (x, y) in ((10, 22), (20, 32), (11, 44), (24, 50)):
            for a in range(3):
                r = math.radians(a * 60)
                pd.line(q([(x - 3.5 * math.cos(r), y - 3.5 * math.sin(r)), (x + 3.5 * math.cos(r), y + 3.5 * math.sin(r))]), fill=WHITE, width=round(1.4 * K))
    elif pat == "stripe":
        for y in (20, 30, 40):
            pd.rectangle(q([(0, y), (50, y + 4)]), fill=WHITE)
            pd.rectangle(q([(0, y + 4), (50, y + 6)]), fill=RED)
    elif pat == "candy":
        for x in range(-40, 50, 9):
            pd.polygon(q([(x, 0), (x + 4, 0), (x + 64, 64), (x + 60, 64)]), fill=RED)
    elif pat == "zigzag":
        for y in (22, 36):
            z = [(x, y + (3 if (x // 4) % 2 else -3)) for x in range(0, 48, 4)]
            pd.line(q(z), fill=WHITE, width=round(2.4 * K))
            pd.line(q([(0, y + 6), (48, y + 6)]), fill=GREEN, width=round(1.6 * K))
    elif pat == "dots":
        for (x, y) in ((9, 20), (19, 26), (8, 34), (18, 40), (26, 50), (14, 52)):
            pd.ellipse(q([(x - 2.2, y - 2.2), (x + 2.2, y + 2.2)]), fill=WHITE)
    # かかと・つま先
    pd.ellipse(q([(-4, 44), (14, 64)]), fill=heel)
    pd.ellipse(q([(32, 40), (50, 62)]), fill=heel)
    im.alpha_composite(Image.composite(pl, Image.new("RGBA", im.size, (0, 0, 0, 0)), mask))
    d.line(q(shape + shape[:1]), fill=L, width=lw, joint="curve")
    # ふわふわの白い口(下が波のふち)
    cuff = [(0, 2), (31, 2)] + [(31 - j * 31 / 8, 14 + (2.2 if j % 2 else -0.4)) for j in range(9)]
    d.polygon(q(cuff), fill=WHITE, outline=L, width=lw)
    d.ellipse(q([(4, 4), (10, 9)]), fill="#EEF4FA")
    if cuffdeco == "holly":
        for sx in (-1, 1):
            d.ellipse(q([(15 + sx * 7 - 6, 4), (15 + sx * 7 + 6, 10)]), fill=GREEN, outline=L, width=max(1, lw // 2))
        for dx in (-2, 2, 0):
            d.ellipse(q([(15 + dx - 2.4, 4 + (dx == 0) * 2), (15 + dx + 2.4, 8.8 + (dx == 0) * 2)]), fill=RED, outline=L, width=max(1, lw // 2))
    elif cuffdeco == "bell":
        sw = 4 if t % 2 else -4
        d.polygon(q([(24 + sw * 0.2, 8), (20 + sw * 0.4, 18), (30 + sw * 0.4, 18)]), fill=GOLD, outline=L, width=lw)
        d.ellipse(q([(23 + sw * 0.5, 17), (27 + sw * 0.5, 21)]), fill="#B8860B", outline=L, width=max(1, lw // 2))
        d.ellipse(q([(21, 5), (27, 10)]), fill=RED, outline=L, width=max(1, lw // 2))
    elif cuffdeco == "pom":
        for x in (6, 15, 24):
            d.ellipse(q([(x - 3, 12), (x + 3, 18)]), fill=RED, outline=L, width=max(1, lw // 2))
    # つり下げのひもの輪
    d.ellipse(q([(1, -4), (7, 4)]), outline=L, width=round(2.4 * K))
    d.ellipse(q([(1, -4), (7, 4)]), outline=GOLD, width=round(1.2 * K))
    im = im.resize((W // 3, H // 3), Image.LANCZOS)
    _STOCK[key] = im
    return im


def fir_garland(layer, pts, i):
    """もみの葉のガーランド: 濃さのちがう緑の葉を重ね、赤と金の玉、点滅する電球、金のビーズのひもを通す。"""
    big = Image.new("RGBA", (layer.width * 3, layer.height * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    P3 = lambda *v: [x * 3 for x in v]
    dense = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for u in range(6):
            dense.append((x0 + (x1 - x0) * u / 6, y0 + (y1 - y0) * u / 6))
    dense.append(pts[-1])
    rnd = random.Random(4)
    leaves = []
    for j, (x, y) in enumerate(dense):
        if j % 2:
            continue
        up = -6 if (j // 2) % 2 else 5  # 上下にでこぼこ(葉のふさ)
        for (dx, dy, r, col) in ((-5, up - 2, 10, GREEN_D), (5, -up * 0.4, 10, GREEN), (0, up + 3, 8, "#3E9A6C"),
                                 (-1, up * 0.5, 6, "#5DB585")):
            leaves.append((x + dx + rnd.uniform(-1.5, 1.5), y + dy, r, col))
    for (x, y, r, col) in leaves:  # 全体の輪郭だけ線を引き、中の葉は線なしで重ねる(黒っぽい帯に見せない)
        d.ellipse(P3(x - r - 1.2, y - r * 0.7 - 1.2, x + r + 1.2, y + r * 0.7 + 1.2), fill=L)
    for (x, y, r, col) in leaves:
        d.ellipse(P3(x - r, y - r * 0.7, x + r, y + r * 0.7), fill=col)
    for j, (x, y) in enumerate(dense[1::3]):  # もみの葉の針(明るい緑の短い線、ふさごとに向きを変える)
        for a in (-0.9, -0.3, 0.3, 0.9):
            a += 0.3 * math.sin(j)
            d.line(P3(x, y, x + 7 * math.sin(a), y - 6 * math.cos(a)), fill="#7CCB9A", width=3)
    # 電球はついたまま(消えない)。1つだけが順番に少し明るく光る(チカチカさせない)
    lights = ["#FF6B6B", "#FFD24D", "#7FC4FF"]
    bulbs = dense[5::10]
    for j, (x, y) in enumerate(bulbs):
        col = lights[j % len(lights)]
        if j == (i // 2) % len(bulbs):
            d.ellipse(P3(x - 9, y, x + 9, y + 20), fill=col + "50")
        d.rounded_rectangle(P3(x - 3, y + 1, x + 3, y + 5), radius=3, fill="#555", outline=L, width=2)
        d.ellipse(P3(x - 5, y + 4, x + 5, y + 16), fill=col, outline=L, width=3)
        d.ellipse(P3(x - 2.5, y + 6, x, y + 9), fill=WHITE)
    layer.alpha_composite(big.resize(layer.size, Image.LANCZOS))


# 靴下は5足: 大きさ・色・柄・口からのぞく物(キャンディ・プレゼント・星)をそれぞれ変える
# (x, 種類, 大きさ, ひもの長さ)
STOCKS04 = [(48, 0, 1.3, 6), (122, 1, 1.05, 12), (196, 2, 1.38, 4), (268, 4, 1.12, 10)]


def stockings_front(layer, i):
    """もみの葉のガーランド(両はしに大きな赤いリボン)に、5足のクリスマスの靴下を赤いリボンでつるす。
    靴下は大きさ・ひもの長さ・色・柄・のぞく物がちがい、それぞれちがう速さでゆれる。"""
    sag = lambda x: 20 + 12 * math.sin((x - 16) / 288 * math.pi)
    pts = [(x, sag(x)) for x in range(16, 305, 18)] + [(304, sag(304))]
    fir_garland(layer, pts, i)
    d = ImageDraw.Draw(layer)
    for j, (x, kind, sc, drop) in enumerate(STOCKS04):
        im = stocking_img(kind, sc)
        ang = 4 * math.sin(i * 2 * math.pi / 12 + j * 0.8)  # ゆっくり小さく(12コマで1往復)
        top = sag(x) + 4
        hx, hy = im.width * 4 / 52, im.height * 26 / 92  # ひもの輪(画像の中の位置)
        a = math.radians(ang)
        ex, ey = x - drop * math.sin(a), top + drop * math.cos(a)
        d.line((x, top, ex, ey), fill=L, width=4)
        d.line((x, top, ex, ey), fill=GOLD, width=2)
        pad = int(max(im.size) * 2.2)
        cv = Image.new("RGBA", (pad, pad), (0, 0, 0, 0))
        cv.alpha_composite(im, (round(pad / 2 - hx), round(pad / 2 - hy)))
        cv = cv.rotate(ang, resample=Image.BICUBIC, center=(pad // 2, pad // 2))
        layer.alpha_composite(cv, (round(ex - pad / 2), round(ey - pad / 2)))
    for x in (16, 304):  # 両はしの大きなリボン
        y = sag(x)
        for sx in (-1, 1):
            d.polygon((x, y, x + sx * 12, y - 9, x + sx * 13, y + 7), fill=RED, outline=L)
        d.polygon((x - 2, y + 2, x - 7, y + 20, x - 2, y + 17), fill=RED_D, outline=L)
        d.polygon((x + 2, y + 2, x + 7, y + 20, x + 2, y + 17), fill=RED_D, outline=L)
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=RED_D, outline=L, width=1)


def qmarks_front(layer, i):
    """「?」3つ: 大きさ・色・かたむきを変えて、順番に跳ねる。"""
    for j, (x, y, sz, col, rot) in enumerate(((96, 142, 46, RED, -14), (156, 132, 36, GREEN, 14), (34, 148, 32, GOLD_T, -8))):
        hop = abs(math.sin((i + j * 2) * 0.9)) * 10
        font = ImageFont.truetype(str(soft.HAND_FONT), sz)
        g = Image.new("RGBA", (sz + 30, sz + 30), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((g.width / 2, g.height / 2), "?", font=font, anchor="mm", fill=col, stroke_width=5,
                               stroke_fill="white")
        put_img(layer, g, x, y - hop, 1.0, rot + 8 * math.sin(i * 1.2 + j))


STAMPS["04"] = with_layers(paths(make(
    "xmas", [("いい子に", 32, True), ("してた?", 32, True)], "B",
    lambda i: [POSE04[i], happy, P(**MV04[i]), santa], lambda i, av: [],
    m=dict(scale=0.86, anchor=PATH04[0]), x0=12, y0=172), PATH04),
    front=lambda L_, i: (stockings_front(L_, i), qmarks_front(L_, i)))
SANTA.add("04")


# ---- 横向きのトナカイと、そりを引くひとまとまりの絵 --------------------------------------

DEER_C, DEER_FACE_C, DEER_FRONT_C, DEER_BACK_C = "#8C5A3A", "#DDB383", "#D2A675", "#6B4329"


# 走る足の4つの形(ギャロップ): (前足の手前, 前足の向こう, 後ろ足の手前, 後ろ足の向こう, 体の上下)
# 角度は 正=前(右)へ。1・3 は大きく前後に伸ばして体が上がり、2・4 は足を体の下へ集める
GALLOP = [(48, 30, -46, -30, -6), (-14, 4, 22, 34, 2), (40, 54, -38, -50, -4), (-24, -6, 30, 18, 2)]


def deer_side(t=0, k=1.0):
    """横向き(右向き)のトナカイ。足は4つの形で走り続ける(ひざが曲がる。前足は明るい茶、後ろ足はこい茶)。
    大きな赤い鼻・白い口元・2色の耳・ベージュの角(枝先は丸い)・頭の毛とヒイラギ・赤い首輪と金の鈴・白いしっぽ。"""
    W, H = 136, 124
    ff, fb, bf, bb, dy = GALLOP[t % 4]

    def fn(d, p, kk):
        def leg(hx, hy, ang, col, front):
            a = math.radians(ang)
            # 上の足を ang へ、下の足はひざで曲げる(前足は後ろへ、後ろ足は前へ折れる)
            kx, ky = hx + 17 * math.sin(a), hy + 17 * math.cos(a)
            bend = (-36 if front else 30) if abs(ang) > 12 else 0
            if front and ang < -10: bend = -10
            b = math.radians(ang + bend)
            fx, fy = kx + 17 * math.sin(b), ky + 17 * math.cos(b)
            for w, c_ in ((13, L), (9, col)):
                d.line(p(hx, hy, kx, ky), fill=c_, width=round(w * kk))
                d.line(p(kx, ky, fx, fy), fill=c_, width=round(w * kk))
                d.ellipse(p(kx - w / 2, ky - w / 2, kx + w / 2, ky + w / 2), fill=c_)
            d.ellipse(p(fx - 6.5, fy - 4.5, fx + 6.5, fy + 5), fill="#3E2A22", outline=L, width=kk)
        o = dy
        # 向こう側の足(少しこい)
        leg(42, 80 + o, bb, "#4E3020", False)
        leg(86, 80 + o, fb, "#B8885A", True)
        # しっぽ(白くて上を向く)
        d.ellipse(p(8, 46 + o, 30, 62 + o), fill=WHITE, outline=L, width=2 * kk)
        d.ellipse(p(12, 50 + o, 22, 56 + o), fill="#F2E6D8")
        # 体
        d.ellipse(p(18, 50 + o, 104, 94 + o), fill=DEER_C, outline=L, width=2 * kk)
        d.ellipse(p(30, 78 + o, 92, 93 + o), fill="#A87048")  # おなかのかげ
        d.ellipse(p(78, 60 + o, 104, 88 + o), fill="#F4E6D2")  # 胸のふわふわ
        # 首と頭
        d.polygon(p(80, 62 + o, 100, 40 + o, 112, 46 + o, 98, 74 + o), fill=DEER_C)
        d.line(p(80, 62 + o, 100, 40 + o), fill=L, width=2 * kk)
        d.line(p(112, 46 + o, 98, 74 + o), fill=L, width=2 * kk)
        hy0 = o
        # 角(頭のうしろから上へ、ベージュ、枝先は丸い)
        for (bx, by, sx) in ((100, 26, -1), (106, 24, 1)):
            by += hy0
            d.line(p(bx, by, bx + sx * 4, by - 18), fill=L, width=round(7 * kk))
            d.line(p(bx, by, bx + sx * 4, by - 18), fill="#E8C690", width=round(4 * kk))
            d.line(p(bx + sx * 2, by - 9, bx + sx * 12, by - 14), fill=L, width=round(6 * kk))
            d.line(p(bx + sx * 2, by - 9, bx + sx * 12, by - 14), fill="#E8C690", width=round(3.5 * kk))
            d.ellipse(p(bx + sx * 4 - 3, by - 21, bx + sx * 4 + 3, by - 15), fill="#E8C690", outline=L, width=kk)
        q = lambda *v: p(*[x + (hy0 if i % 2 else 0) for i, x in enumerate(v)])
        d.ellipse(q(90, 22, 124, 52), fill=DEER_FACE_C, outline=L, width=2 * kk)  # 頭
        d.ellipse(q(110, 34, 130, 50), fill="#FFF3E2", outline=L, width=2 * kk)  # 口元
        d.ellipse(q(121, 32, 134, 44), fill="#E2463F", outline=L, width=2 * kk)  # 鼻
        d.ellipse(q(124, 34, 127, 36), fill=WHITE)
        d.ellipse(q(84, 24, 101, 34), fill="#6B4329", outline=L, width=2 * kk)  # 耳(外)
        d.ellipse(q(87, 26, 98, 32), fill="#F7C9C3")  # 耳(内)
        # 頭の毛(こい茶のふさ)とヒイラギ
        d.polygon(q(98, 24, 102, 14, 106, 22, 110, 15, 112, 25), fill="#6B4329", outline=L)
        for lx, ang in ((92, -0.5), (99, 0.4)):
            d.polygon(q(lx, 22, lx + 5 + 3 * ang, 16, lx + 11, 19, lx + 6, 24), fill=GREEN, outline=L)
        for bx_, by_ in ((97, 20), (101, 22), (99, 17)):
            d.ellipse(q(bx_ - 2.4, by_ - 2.4, bx_ + 2.4, by_ + 2.4), fill=RED, outline=L, width=kk)
        d.ellipse(q(108, 28, 115, 37), fill="#2E2A2A")  # 目
        d.ellipse(q(110, 29, 112, 31), fill=WHITE)
        d.ellipse(q(102, 38, 110, 43), fill="#FFB3C1")  # ほっぺ
        d.arc(q(114, 42, 122, 48), 20, 160, fill=L, width=kk)
        # 首輪と鈴
        d.line(q(86, 58, 106, 70), fill=L, width=round(8 * kk))
        d.line(q(86, 58, 106, 70), fill=RED, width=round(5 * kk))
        d.ellipse(q(94, 66, 104, 76), fill=GOLD, outline=L, width=kk)
        d.line(q(96, 72, 102, 72), fill=L, width=kk)
        # 手前の足(前足は明るい茶、後ろ足はこい茶)
        leg(36, 80 + o, bf, DEER_BACK_C, False)
        leg(92, 80 + o, ff, DEER_FRONT_C, True)
    im = art(W, H, fn)
    if k != 1.0:
        im = im.resize((round(W * k), round(H * k)), Image.LANCZOS)
    return im


_TEAM = {}


def sleigh_team(t=0, k=1.0, santa_in=True):
    """そりを引くひとまとまり: 左にそり(サンタが乗って手をふる。荷物はうしろに積み、サンタの顔をかくさない)、
    右に横向きのトナカイ(走り続ける)。赤い手綱でつなぐ。"""
    key = (t % 4, round(k, 2), santa_in)
    if key in _TEAM:
        return _TEAM[key]
    W, H = 300, 136
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if santa_in:
        gifts = sleigh_image(0.95, 0, part="gifts")
        body = sleigh_image(0.95, 0, part="body")
        im.alpha_composite(gifts, (4, H - body.height - 6))
        ik = ("santa_wave", t % 2)
        if ik not in _TEAM:
            _TEAM[ik] = char_icon("santa", 74, dict(ar=118 if t % 2 else 84, al=10))
        sa = _TEAM[ik]
        im.alpha_composite(sa, (round(4 + body.width * 0.26), H - body.height - 6))
        im.alpha_composite(body, (4, H - body.height))
    else:
        sl = sleigh_image(0.95, 0)
        body = sl
        im.alpha_composite(sl, (4, H - sl.height))
    deer = deer_side(t)
    x0, y0 = W - deer.width - 2, H - deer.height - 2
    im.alpha_composite(deer, (x0, y0))
    d = ImageDraw.Draw(im)
    dy = GALLOP[t % 4][4]
    # 手綱: そりの前 → トナカイの体の横(胴ベルト) → 首輪
    rope = [(4 + body.width * 0.84, H - body.height * 0.58), (x0 + 22, y0 + 72 + dy), (x0 + 96, y0 + 68 + dy)]
    d.line(rope, fill=L, width=6, joint="curve")
    d.line(rope, fill=RED, width=3, joint="curve")
    for j in range(3):
        x = rope[0][0] + (rope[1][0] - rope[0][0]) * (j + 1) / 4
        y = rope[0][1] + (rope[1][1] - rope[0][1]) * (j + 1) / 4
        d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=GOLD, outline=L, width=1)
    if k != 1.0:
        im = im.resize((round(W * k), round(H * k)), Image.LANCZOS)
    _TEAM[key] = im
    return im


def snowy_pine(d, x, y, h):
    """雪をかぶったもみの木(3段、段ごとに白い雪が乗る)。"""
    for j in range(3):
        top = y - h + j * h * 0.28
        w = h * (0.32 + j * 0.14)
        d.polygon((x, top, x + w / 2, top + h * 0.4, x - w / 2, top + h * 0.4), fill=GREEN if j % 2 else GREEN_D, outline=L)
        d.polygon((x, top + 1, x + w * 0.2, top + h * 0.16, x + w * 0.05, top + h * 0.13, x - w * 0.08, top + h * 0.18,
                   x - w * 0.2, top + h * 0.15), fill=WHITE, outline=L)
    d.rectangle((x - 3, y - h * 0.04, x + 3, y + 4), fill="#8C5A3A", outline=L)


def snow_ground(layer, i):
    d = ImageDraw.Draw(layer)
    for x, y, h in ((40, 222, 54), (262, 226, 64), (300, 232, 44)):
        snowy_pine(d, x, y, h)
    d.ellipse((-60, 214, 200, 320), fill=WHITE, outline=L, width=2)
    d.ellipse((140, 222, 400, 320), fill="#F4FAFF", outline=L, width=2)
    # 雪の上のそりのあと(走ったところに2本の線が伸びる)
    if i:
        x1 = TEAM06[i][0] - 60
        d.line((10, 236, x1, 236 - max(0, i - 6) * 4), fill="#C9DDF0", width=3)
        d.line((14, 244, x1 + 4, 244 - max(0, i - 6) * 4), fill="#C9DDF0", width=3)


def ease(u):
    return u * u * (3 - 2 * u)


# 06 いってきます!: 横向きのトナカイがサンタの乗ったそりを引いて、雪の上を左から右へ走り、後半は空へ(前を上げてかたむく)
TEAM06 = [(160, 196)] + [(104 + 110 * (j / 10) ** 1.3, 202 - (max(0, j - 5) ** 1.6) * 5) for j in range(11)]
TILT06 = [0] + [max(0, j - 5) * 3 for j in range(11)]
STAMPS["06"] = with_layers(make(
    "xmas", [("いって", 44, True), ("きます!", 38, True)], "B",
    lambda i: [], lambda i, av: winter.snow(6, 7, i, avoid=((0, 120, 320, 270),)), m=dict(scale=1.0, anchor=(160, 258)),
    x0=16), back=snow_ground, front=lambda L_, i: put_img(L_, sleigh_team(i, 0.66), TEAM06[i][0], TEAM06[i][1], 1.0, TILT06[i]))
for fr in STAMPS["06"]:
    fr["nochar"] = True


# 07 今から帰ります: 夜の空(囲みなし)。大きな三日月と星。サンタのそり(左向き)が右上の月の前から左下へ、だんだん速くかけおりる
def night_free(layer, i):
    put_img(layer, night_img(), 270, 50, 0.9)
    winter.draw_marks2(layer, twinkles(((24, 24), (110, 18), (190, 30), (300, 140), (20, 130), (60, 76), (230, 100)), i, 6), 0, 0)


TEAM07 = [(158, 90)] + [(214 - 108 * ease(j / 10), 62 + 44 * ease(j / 10)) for j in range(11)]
TILT07 = [4] + [8 - abs(j - 5) for j in range(11)]


def team_left(t, k):
    return sleigh_team(t, k).transpose(Image.FLIP_LEFT_RIGHT)


STAMPS["07"] = with_layers(make(
    "xmas", [("今から", 38, True), ("帰ります", 34, True)], "A",
    lambda i: [], lambda i, av: [], m=dict(scale=1.0, anchor=(160, 258)), x0=92, y0=148),
    back=night_free, front=lambda L_, i: put_img(L_, team_left(i, 0.66), TEAM07[i][0], TEAM07[i][1], 1.0, TILT07[i]))
for fr in STAMPS["07"]:
    fr["nochar"] = True

# 08 飾りつけ中: 大きなツリー。サンタがツリーの側の手で星を持って、背のびしながら跳ねる
POSE08 = [J0, S, J0, J1, J0, S, J0, J1, J0, S, J0, J1]
MV08 = santa_moves([0, 20, 30, 40, 30, 20, 30, 40, 30, 20, 30, 40], [0, 30, 44, 56, 44, 30, 44, 56, 44, 30, 44, 56], HAT_SWING,
                   hold="star", hand="P7")
STAMPS["08"] = paths(make(
    "xmas", [("飾りつけ", 38, True), ("中です", 32, True)], "A",
    lambda i: [POSE08[i], happy, P(**MV08[i]), santa, tree_page(150, 52, 206, (110, 256), 0.9, i, style="ball")],
    lambda i, av: twinkles(((96, 70), (150, 110), (240, 60)), i), m=dict(scale=0.9, anchor=(110, 256)), x0=14),
    [(96 + min(i, 6) * 2, 256) for i in range(12)])
SANTA.add("08")

# 09 キラキラ: 電球のツリーの方へ、トナカイが右から跳ねながら近づいて、うっとり見上げる(その場でゆらさない)
# トナカイはツリーへぴょんぴょん近づいて、またはねながら戻る(場所が変わる。その場でゆらさない)
WALK09 = [(240, 258), (254, 252), (240, 232), (226, 258), (212, 232), (198, 258), (186, 236), (176, 258), (190, 232),
          (206, 258), (222, 234), (240, 258)]
MV09 = [dict(), dict(fl=26, lfl=8, el=-12), dict(fr=26, lfr=8, er=-12), dict(fl=26, lfl=8, el=-12), dict(fr=26, lfr=8, er=-12),
        dict(fl=20, lfl=6), dict(fr=20, lfr=6), dict(el=-10, er=10), dict(fl=14, fr=14, lfl=4, lfr=4, el=-14, er=-14),
        dict(el=-10, er=10), dict(fl=10, fr=10, el=-12, er=-12), dict(el=-6, er=6)]
STAMPS["09"] = paths(make(
    "xmas", [("キラキラ", 46, True)], "C",
    lambda i: [S, happy, P(**MV09[i]), reindeer, tree_page(14, 94, 164, WALK09[i], 0.82, i, style="lights")],
    lambda i, av: twinkles(((28, 130), (150, 112), (30, 232), (294, 120), (284, 150)), i, 8),
    m=dict(scale=0.82, anchor=(240, 258)), x0=108, y0=16, wave_amp=5), WALK09)
DEER.add("09")

# 10 楽しみです♪: 暖炉の前で、サンタが両手を高く上げてぴょんぴょん
POSE10 = [S, J0, J1, J2, J1, J0, S, J0, J1, J2, J1, J0]
MV10 = santa_moves([0, 70, 110, 126, 116, 100, 96, 112, 122, 128, 114, 100], [0, 74, 112, 128, 118, 102, 98, 114, 124, 126, 116, 102],
                   HAT_SWING, gift=False, hold=None)
STAMPS["10"] = with_layers(paths(make(
    "xmas", [("楽しみ", 46, True), ("です♪", 38, True)], "B",
    lambda i: [POSE10[i], happy, P(**MV10[i]), santa],
    lambda i, av: [("note", 286 + (i % 3) * 6, 64 - (i % 4) * 10, 26), ("note", 296, 170 - ((i + 2) % 4) * 10, 22)],
    m=dict(scale=0.86, anchor=(218, 256)), x0=14), [(218 - min(i, 6) * 3, 256) for i in range(12)]),
    back=lambda L_, i: put_img(L_, fireplace_img(i), 84, 204, 0.8))
SANTA.add("10")

# 13 かんぱい: サンタが右腕(見て左)でグラスを高く上げてジャンプ。泡とキラキラ、金の紙ふぶき
MV13 = santa_moves([0, 60, 100, 122, 112, 124, 112, 124, 112, 124, 112, 104], [0, 10, 20, 26, 20, 26, 20, 26, 20, 26, 20, 16], HAT_SWING,
                   gift=False, hold="glass")
POSE13 = [S, J0, J1, J2, J1, J0, S, J0, J1, J2, J1, S]
STAMPS["13"] = paths(make(
    "xmas", [("かんぱい", 36, True), ("♪♪", 34, True)], "B",
    lambda i: [POSE13[i], happy, P(**MV13[i]), santa],
    lambda i, av: winter.confetti(13, 8, i, box=(30, 30, 300, 120)) + twinkles(((70, 70), (40, 120)), i, 8),
    m=dict(scale=0.9, anchor=(126, 256)), x0=150, y0=40), [(126, 256)] * 12)
SANTA.add("13")


# 14 寒いですね…: 雪の丘を、分厚いマフラーのトナカイが右から歩いてきて、ぶるぶる(体をちぢめる)
def scarf_deer(c):
    """分厚い毛糸のマフラー: 首を太く(高さ46)ぐるりと巻き、横じま(白・緑)。右に長いたれ(横じま+白いふさ)。"""
    fx, fy = winter.face_off(c)
    X, Y = 102 + fx, 190 + fy
    xmas.put(c, "NECK9_b_band", RED, 2.6, 116, 50, X, Y,
             "M4 10 C30 26 86 26 112 10 C117 22 116 34 111 41 C84 55 32 55 5 41 C0 34 -1 22 4 10 Z", vw=116, vh=50)
    xmas.put(c, "NECK9_c_s1", WHITE, 0, 116, 50, X, Y,
             "M5 21 C32 37 84 37 112 21 L113 27 C84 43 32 43 4 27 Z", vw=116, vh=50)
    xmas.put(c, "NECK9_c_s2", GREEN, 0, 116, 50, X, Y,
             "M5 32 C32 47 84 47 112 32 L111 37 C84 52 32 52 6 37 Z", vw=116, vh=50)
    xmas.put(c, "NECK9_c_knot", RED_D, 2, 26, 24, X + 74, Y + 22, soft.ellipse_d(26, 24))
    TX, TY = X + 80, Y + 30
    xmas.put(c, "NECK9_d_tail", RED, 2.6, 30, 40, TX, TY, "M4 2 L27 2 C29 14 30 26 28 36 L4 38 C1 28 1 14 4 2 Z", rot=-8, vw=30, vh=40)
    xmas.put(c, "NECK9_e_t1", WHITE, 0, 30, 40, TX, TY, "M3 12 L28 11 L28 17 L3 18 Z", rot=-8, vw=30, vh=40)
    xmas.put(c, "NECK9_e_t2", GREEN, 0, 30, 40, TX, TY, "M3 23 L29 22 L29 28 L3 29 Z", rot=-8, vw=30, vh=40)
    xmas.put(c, "NECK9_f_fringe", WHITE, 2, 30, 14, TX + 1, TY + 35,
             "M2 2 L28 2 L27 6 L25 13 L22 6 L19 13 L16 6 L13 13 L10 6 L7 13 L4 6 Z", rot=-8, vw=30, vh=14)


def hills_back(layer, i):
    d = ImageDraw.Draw(layer)
    d.ellipse((-80, 180, 200, 330), fill=WHITE, outline=L, width=2)
    d.ellipse((150, 196, 420, 330), fill="#F4FAFF", outline=L, width=2)


# 右から歩いてきて(場所が変わる)、止まってからは足ぶみ(その場でぶるぶるゆらさない)
WALK14 = [(226, 246), (262, 242), (254, 246), (246, 242), (238, 246), (232, 242), (228, 246), (226, 246), (226, 242),
          (226, 246), (226, 242), (226, 246)]
STAMPS["14"] = with_layers(paths(make(
    "xmas", [("寒い", 50, True), ("ですね…", 32, True)], "B",
    lambda i: [S, blink, P(el=-18, er=18, fl=16 if 1 <= i <= 6 and i % 2 else 0, fr=16 if 1 <= i <= 6 and i % 2 == 0 else 0),
               reindeer, scarf_deer],
    lambda i, av: winter.snow(14, 12, i, avoid=((100, 110, 300, 262),)), m=dict(scale=0.9, anchor=(226, 246)), x0=13),
    WALK14), back=hills_back)
DEER.add("14")

# 15 雪だるま作ったよ!: 雪だるま(腕をふる)の横で、サンタが両手を高く上げてぴょん
POSE15 = [S, J0, J1, J2, J1, J0, S, J0, J1, J2, J1, J0]
MV15 = santa_moves([0, 70, 110, 126, 116, 100, 96, 112, 122, 128, 114, 100], [0, 74, 112, 128, 118, 102, 98, 114, 124, 126, 116, 102],
                   HAT_SWING, gift=False, hold=None)
STAMPS["15"] = with_layers(paths(make(
    "xmas", [("雪だるま", 40, True), ("作ったよ!", 34, True)], "A",
    lambda i: [POSE15[i], happy, P(**MV15[i]), santa],
    lambda i, av: winter.snow(15, 5, i, avoid=tuple(av) + ((180, 100, 300, 270), (40, 60, 180, 262))),
    m=dict(scale=0.86, anchor=(108, 256)), x0=96, y0=8), [(108 + min(i, 6) * 2, 256) for i in range(12)]),
    back=lambda L_, i: put_img(L_, snowman_img(i), 238, 192, 1.0))
SANTA.add("15")

# 17 Merry Christmas: 上の真ん中に大きな豪華なリース(飾りは文字でかくさない)。トナカイが左からぴょんぴょん跳ねて
#    リースの輪の中へ入り、輪の中で高さを変えて跳ねる。文字はリースの下をリボンのように横切る(4分の1に区切らない)
WALK17 = [(160, 170), (74, 192), (90, 164), (106, 188), (122, 160), (138, 184), (152, 158), (160, 172), (160, 148),
          (160, 172), (160, 158), (160, 172)]
STAMPS["17"] = with_layers(paths(make(
    "xmas", [("Merry", 42, True), ("Christmas", 38, True)], "B",
    lambda i: [S, happy, P(fl=20 * (i % 2), fr=20 * ((i + 1) % 2), lfl=6 * (i % 2), lfr=6 * ((i + 1) % 2), el=-10, er=10),
               reindeer],
    both(xmas.bells_travel, xmas.sparkle_field(((40, 40), (282, 150), (290, 214), (30, 110), (250, 22), (70, 120), (250, 120), (160, 18), (196, 240)))), m=dict(scale=0.7, anchor=WALK17[0]), x0=18, y0=134), WALK17),
    back=lambda L_, i: put_img(L_, wreath_big(190, i), 160, 108, GROW[i]))
DEER.add("17")

# 18 メリクリ!: 大きな文字。小さなサンタが下を走りぬける。跳ねる高さを毎回変える
JUMP18 = [0, 6, 20, 4, 30, 8, 14, 2, 26, 6, 18, 0]
RUN18 = [(160, 262)] + [(74 + i * 17, 262 - JUMP18[i + 1]) for i in range(11)]
STAMPS["18"] = paths(make(
    "xmas", [("メリクリ!", 54, True)], "C",
    lambda i: [S if JUMP18[i] < 10 else J0, happy,
               P(**santa_moves([0] + [56, 30] * 5 + [40], [0] + [30, 56] * 5 + [44], HAT_SWING, hold=None, gift=False)[i]), santa],
    lambda i, av: winter.confetti(18, 8, i, box=(20, 100, 300, 150)), m=dict(scale=0.78, anchor=RUN18[0]), x0=22, y0=22,
    wave_amp=6), RUN18)
SANTA.add("18")


# ---- クリスマスカード(9枚・ペンで書いていく・20コマ) ----------------------------------

def card_paper(kind, W, H):
    """カードの紙(角は丸くしない)。kind ごとに色・わく・柄を変える。"""
    paper, frame, inner, pat = {
        "red": ("#FFF9EE", RED, GOLD, "dots"),
        "green": ("#F6FBF4", GREEN, GOLD, "stripe"),
        "navy": ("#24305E", GOLD, WHITE, "stars"),
        "white": ("#FFFFFF", RED, GREEN, "ribbon_tr"),
        "white2": ("#FFFFFF", RED, GREEN, "ribbon_bl"),
        "gold": ("#FFF6DC", GOLD, RED, "holly"),
        "pink": ("#FFF0F3", "#E8577A", GOLD, "hearts"),
    }[kind]

    def fn(d, p, k):
        d.rectangle(p(1, 1, W - 1, H - 1), fill=WHITE)
        d.rectangle(p(4, 4, W - 4, H - 4), fill=paper, outline=L, width=2 * k)
        d.rectangle(p(10, 10, W - 10, H - 10), outline=frame, width=4 * k)
        d.rectangle(p(16, 16, W - 16, H - 16), outline=inner, width=k)
        if pat == "dots":  # わくの上に白い水玉
            for x in range(14, W - 10, 14):
                for y in (10, H - 10):
                    d.ellipse(p(x - 2, y - 2, x + 2, y + 2), fill=WHITE)
        elif pat == "stripe":  # キャンディのしま(わくに斜めの白線)
            for x in range(10, W - 10, 10):
                d.line(p(x, 8, x + 4, 12), fill=WHITE, width=2 * k)
                d.line(p(x, H - 12, x + 4, H - 8), fill=WHITE, width=2 * k)
        elif pat.startswith("ribbon"):  # 赤いリボンを角にななめにかけて、角にリボン結び(文字の上には通さない)
            tr = pat == "ribbon_tr"
            sx, sy = (W, 0) if tr else (0, H)
            gx, gy = (-1, 1) if tr else (1, -1)
            band = [(sx + gx * 4, sy + gy * 44), (sx + gx * 4, sy + gy * 62), (sx + gx * 62, sy + gy * 4), (sx + gx * 44, sy + gy * 4)]
            d.polygon(p(*[v for pt in band for v in pt]), fill=RED, outline=L, width=k)
            cx, cy = sx + gx * 30, sy + gy * 30
            for a in (-1, 1):
                ex, ey = cx + a * 16, cy - a * 16 * gx * gy
                d.ellipse(p(ex - 10, ey - 10, ex + 10, ey + 10), fill=RED, outline=L, width=2 * k)
                d.ellipse(p(ex - 4, ey - 4, ex + 2, ey + 2), fill="#F77F7A")
            for a in (-1, 1):  # たれ
                d.polygon(p(cx, cy, cx + a * 8 + gx * 14, cy + gy * 24 - a * 4, cx + a * 2 + gx * 18, cy + gy * 18), fill=RED_D, outline=L, width=k)
            d.ellipse(p(cx - 6, cy - 6, cx + 6, cy + 6), fill=RED_D, outline=L, width=2 * k)
        elif pat == "holly":
            for (cx, cy) in ((24, 24), (W - 24, 24), (24, H - 24), (W - 24, H - 24)):
                d.ellipse(p(cx - 12, cy - 5, cx, cy + 5), fill=GREEN, outline=L, width=k)
                d.ellipse(p(cx, cy - 5, cx + 12, cy + 5), fill=GREEN, outline=L, width=k)
                d.ellipse(p(cx - 4, cy - 4, cx + 4, cy + 4), fill=RED, outline=L, width=k)
        elif pat == "hearts":
            for x in range(20, W - 10, 22):
                d.ellipse(p(x - 4, 6, x, 10), fill="#F49CB4")
                d.ellipse(p(x, 6, x + 4, 10), fill="#F49CB4")
                d.polygon(p(x - 4, 8, x + 4, 8, x, 13), fill="#F49CB4")
    return art(W, H, fn)


def card_text(lines, x0, y0, W, cols):
    """カードの文字(ペンで書く): (文字, 大きさ) の行。行ごとに左右へずらし、ゆるい弧と段差、3色以上を1文字ずつ。"""
    chars = []
    y = y0
    for li, (text, size) in enumerate(lines):
        while True:  # カードのわくからはみ出さないよう、行ごとに大きさを自動で小さくする
            font = ImageFont.truetype(str(soft.HAND_FONT), size)
            adv = [font.getlength(ch) for ch in text]
            total = sum(adv)
            if total <= W - 20 or size <= 14:
                break
            size -= 1
        x = x0 + W / 2 - total / 2 + (-6, 8, -2, 6)[li % 4]
        x = max(x0 + 8, min(x, x0 + W - 8 - total))  # わくの内側におさめる
        n = len(text)
        for j, (ch, w) in enumerate(zip(text, adv)):
            if ch != " ":
                t = (j + 0.5) / n - 0.5
                dy = -size * 0.18 * (1 - 4 * t * t) + 2 * math.sin(j * 1.7)
                g = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
                c_ = cols[(j + li) % len(cols)]  # ペン文字は少し太く(同じ色で1px太らせる)
                ImageDraw.Draw(g).text(((size + 20) / 2, (size + 20) / 2), ch, font=font, anchor="mm",
                                       fill=c_, stroke_width=1, stroke_fill=c_)
                chars.append((g, (round(x + w / 2 - g.width / 2), round(y + size * 0.6 + dy - g.height / 2))))
            x += w
        y += size * 1.25
    return chars


def card_frames(paper, pos, lines, cols, scene, n=20):
    """カード20コマ: 1コマ目は完成形。2コマ目から、ペンが左右にゆれながら一文字ずつ書き、
    書き終わると飾りがぽんと出る。scene(im, t, k) は最初から最後まで動き続ける絵(雪・電球・ベル・キャラなど)。"""
    W, H = paper.size
    px, py = pos
    tx0, ty0, tw = lines[0], lines[1], lines[2]
    chars = card_text(lines[3], px + tx0, py + ty0, tw, cols)
    N = len(chars)
    per = max(1, math.ceil(N / 13))
    rnd = random.Random(N)

    def draw(t, shown, k_deco, pen_at=None):
        im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        im.alpha_composite(paper, (px, py))
        scene(im, t, k_deco)
        for g, xy in chars[:shown]:
            im.alpha_composite(g, xy)
        if pen_at:
            newyear.pen(im, *pen_at)
        return im

    frames = [draw(0, N, 1.0)]
    shown, t = 0, 1
    frames.append(draw(t, 0, 0.0, (chars[0][1][0] + 10, chars[0][1][1] + 24)))
    while shown < N:
        t += 1
        shown = min(N, shown + per)
        g, (gx, gy) = chars[shown - 1]
        bb = g.getbbox()
        pen = (gx + rnd.uniform(bb[0], bb[2]), gy + rnd.uniform(bb[1] + (bb[3] - bb[1]) * 0.4, bb[3]))
        frames.append(draw(t, shown, 0.0, pen))
    t += 1
    frames.append(draw(t, N, 1.25))
    while len(frames) < n:
        t += 1
        frames.append(draw(t, N, 1.0))
    return frames[:n]


POSE_ICON = {"santa": [dict(ar=30, al=6), dict(ar=96, al=14), dict(ar=124, al=20), dict(ar=96, al=14)],
             "deer": [dict(el=-14, er=14), dict(el=-24, er=4, fl=18, lfl=6), dict(el=-6, er=22, fr=18, lfr=6), dict(el=-24, er=4, fl=18, lfl=6)]}


def icon_pose(name, h, t):
    """カードの中のサンタ・トナカイ: 4つのポーズを順番に(手をふる・耳と足が動く)。同じ絵のままにしない。"""
    v = t % 4
    key = ("pose", name, h, v)
    if key not in _TEAM:
        _TEAM[key] = char_icon(name, h, POSE_ICON[name][v])
    return _TEAM[key]


def icon_cache(name, h):
    key = ("icon", name, h)
    if key not in _TEAM:
        _TEAM[key] = char_icon(name, h)
    return _TEAM[key]


def snow_on(im, t, box, n=10, seed=1):
    rnd = random.Random(seed)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    for j in range(n):
        x = rnd.uniform(x0, x1) + 3 * math.sin(t * 0.7 + j)
        y = y0 + (rnd.uniform(0, y1 - y0) + t * 6) % (y1 - y0)
        r = rnd.choice((2.5, 3, 3.5))
        d.ellipse((x - r, y - r, x + r, y + r), fill=WHITE, outline="#BFD9EE")


def bell_swing(im, x, y, s, t, ph=0):
    soft.draw_marks(im, [("bell", x, y, s, 22 * math.sin(t * 1.2 + ph))], 0, 0)


TREE_CACHE = {}


def tree_small(t):
    key = t % 4
    if key not in TREE_CACHE:
        only_tree = lambda c: [c.pop(k) for k in list(c) if not k.startswith("BG")]
        fr = [kf([tree(70, 108, 0.95, key, "lights"), only_tree], scale=1.0, anchor=(160, 258))]
        with tempfile.TemporaryDirectory() as tmp:
            soft.chara_png(fr, f"{tmp}/t.png")
            im = Image.open(f"{tmp}/t.png").convert("RGBA").crop((0, 0, CW, CH))
        im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
        TREE_CACHE[key] = im.crop(im.getbbox())
    return TREE_CACHE[key]


XC = [RED, GREEN, GOLD_T]
XC2 = [GREEN, RED, GOLD_T]
NIGHT = ["#FFE27A", WHITE, "#9FD3F5"]


def card_A():  # 21 Merry Christmas: 赤のカード(白い水玉)。電球のツリーが光り、サンタが手をふり、雪がずっと降る
    paper = card_paper("red", 200, 248)

    def scene(im, t, k):
        snow_on(im, t, (68, 20, 252, 250), 14, 21)
        put_img(im, tree_small(t), 118, 194, 0.58)
        # サンタはツリーのまわりを、手をふりながら左右へぴょんぴょん行き来する
        x = 196 + 10 * math.sin(t * 2 * math.pi / 10)
        put_img(im, icon_pose("santa", 70, t), x, 208 - abs(math.sin(t * 1.6)) * 12)
        bell_swing(im, 82, 34, 13, t)
        bell_swing(im, 238, 34, 13, t, 1.6)
        winter.draw_marks2(im, [("spark", x, y, (5, 8, 12, 8)[(t + j * 3) % 4]) for j, (x, y) in
                                enumerate(((92, 128), (236, 150), (160, 150), (84, 240), (240, 240), (150, 196), (230, 104)))], 0, 0)
    return card_frames(paper, (60, 11), (18, 26, 164, [("Merry", 44), ("Christmas", 30)]), XC, scene)


def card_B():  # 22 Happy Holidays: 緑のカード(キャンディのしま)、横長。そりが上を横切り、トナカイが跳ねる
    paper = card_paper("green", 290, 200)

    def scene(im, t, k):
        put_img(im, sleigh_team(t, 0.34), (160 if t == 0 else 80 + t * 8.5), 84 - 12 * t / 19, 1.0, 5)  # 左から右上へ1回だけ
        put_img(im, icon_pose("deer", 74, t), 248, 182 - abs(math.sin(t * 1.1)) * 12)
        snow_on(im, t, (20, 40, 300, 225), 8, 22)
        if k:
            winter.draw_marks2(im, twinkles(((40, 200), (196, 210)), t, 6), 0, 0)
    return card_frames(paper, (15, 35), (20, 70, 200, [("Happy", 40), ("Holidays", 32)]), XC2, scene)


def card_C():  # 23 メリークリスマス: 白いカードに赤いリボン。リースの玉が順番に光り、ベルがゆれる
    paper = card_paper("white2", 200, 248)

    def scene(im, t, k):
        put_img(im, wreath_big(98, t), 150, 194)
        put_img(im, icon_pose("deer", 62, t), 222, 214 - abs(math.sin(t * 1.4)) * 10)
        bell_swing(im, 96, 130, 13, t)
        bell_swing(im, 226, 132, 13, t, 1.5)
        winter.draw_marks2(im, [("spark", x, y, (5, 8, 12, 8)[(t + j * 3) % 4]) for j, (x, y) in
                                enumerate(((84, 170), (232, 170), (150, 132), (110, 246), (196, 150), (186, 244)))], 0, 0)
    return card_frames(paper, (60, 11), (18, 22, 164, [("メリー", 40), ("クリスマス", 32)]), XC, scene)


def card_D():  # 24 よいお年を: 金のカード(すみにヒイラギ)、横長。雪だるまが手をふり、プレゼントがきらり
    paper = card_paper("gold", 290, 200)

    def scene(im, t, k):
        put_img(im, snowman_img(t), 250, 180, 0.6)
        put_img(im, gift_img(46, 46, RED, GOLD), 62, 198)
        put_img(im, icon_pose("santa", 62, t), 146 + 30 * math.sin(t * 2 * math.pi / 19), 200 - abs(math.sin(t * 1.5)) * 8)
        winter.draw_marks2(im, [("spark", x, y, (6, 10, 14, 10)[(t + j) % 4]) for j, (x, y) in
                                enumerate(((44, 170), (84, 180), (200, 150)))], 0, 0)
    return card_frames(paper, (15, 35), (14, 24, 236, [("よいお年を", 38), ("おむかえください", 28)]), XC, scene)


def card_E():  # 11 素敵なクリスマスを: ピンクのカード(ハート)。プレゼントの山がきらきら、ハートが上がる
    paper = card_paper("pink", 200, 248)

    def scene(im, t, k):
        put_img(im, pile_img(), 132, 210, 0.72)
        put_img(im, icon_pose("santa", 64, t), 212, 208 - abs(math.sin(t * 1.5)) * 8)
        winter.draw_marks2(im, [("spark", x, y, (6, 10, 14, 10)[(t + j) % 4]) for j, (x, y) in
                                enumerate(((92, 170), (160, 160), (118, 150), (170, 210)))], 0, 0)
        soft.draw_marks(im, [("heart", 86 + j * 70, 240 - (t * 8 + j * 30) % 100, 8) for j in range(3)], 0, 0)
    return card_frames(paper, (60, 11), (18, 26, 164, [("素敵な", 34), ("クリスマス", 32), ("を", 30)]), XC2, scene)


def card_F():  # 12 楽しいクリスマスを: 緑のカード、たて長。サンタがそりで手をふりながら上下にゆれ、星がまたたく
    paper = card_paper("green", 200, 248)

    def scene(im, t, k):
        x = 160 + 6 * math.sin(t * 2 * math.pi / 10)
        put_img(im, sleigh_team(t, 0.5), x, 196 - 10 * math.sin(t * 2 * math.pi / 10), 1.0, 4 * math.cos(t * 2 * math.pi / 10))
        snow_on(im, t, (68, 130, 252, 250), 8, 12)
        winter.draw_marks2(im, twinkles(((84, 140), (236, 140), (160, 132)), t, 6), 0, 0)
    return card_frames(paper, (60, 11), (18, 24, 164, [("楽しい", 34), ("クリスマス", 32), ("を♪", 30)]), XC, scene)


def card_G():  # 16 ホワイトクリスマス: 紺のカード(星)、横長。雪の村に雪がたくさん降り続け、窓の明かりがまたたく
    paper = card_paper("navy", 290, 200)

    def scene(im, t, k):
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        put_img(lay, village_img(), 160, 192, 0.8)
        # 村はカードのわくの内側だけに見せる(はみ出さない)
        lay = Image.composite(lay, Image.new("RGBA", im.size, (0, 0, 0, 0)),
                              _box_mask(im.size, (33, 53, 287, 217)))
        im.alpha_composite(lay)
        snow_on(im, t, (34, 56, 286, 214), 24, 16)
        winter.draw_marks2(im, twinkles(((46, 66), (274, 70), (60, 120), (262, 120)), t, 6), 0, 0)
    return card_frames(paper, (15, 35), (20, 22, 260, [("ホワイト", 34), ("クリスマス", 34)]),
                       ["#FFE27A", WHITE, "#FF8A80", "#8FE3B0"], scene)


def _box_mask(size, box):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rectangle(box, fill=255)
    return m


def card_H():  # 19 よいクリスマスを: 白いカード(赤いリボン)、横長。トナカイがそりを引いて左から右へ走る
    paper = card_paper("white", 290, 200)

    def scene(im, t, k):
        snow_on(im, t, (24, 44, 296, 230), 10, 19)
        put_img(im, sleigh_team(t, 0.42), 92 + t * 7, 190 - 4 * abs(math.sin(t * 1.3)))  # 20コマで1回、左から右へ(もどらない)
    return card_frames(paper, (15, 35), (14, 26, 210, [("よい", 34), ("クリスマスを", 30)]), XC2, scene)


def card_I():  # 20 ありがとう: 金のカード、たて長。トナカイとサンタが並んでぺこり(交互に上下)、ハートとキラキラ
    paper = card_paper("gold", 200, 248)

    def scene(im, t, k):
        put_img(im, icon_pose("santa", 76, t), 114, 200 - (10 if t % 2 else 0))
        put_img(im, icon_pose("deer", 76, t + 2), 206, 200 - (10 if t % 2 == 0 else 0))
        soft.draw_marks(im, [("heart", 160 + 8 * math.sin(t), 190 - (t * 8 + j * 26) % 70, 9 - j * 2) for j in range(2)], 0, 0)
        winter.draw_marks2(im, twinkles(((84, 140), (236, 140)), t, 6), 0, 0)
    return card_frames(paper, (60, 11), (18, 40, 164, [("ありがとう", 36), ("♪", 34)]), XC, scene)


CARDS = {"11": card_E, "12": card_F, "16": card_G, "19": card_H, "20": card_I,
         "21": card_A, "22": card_B, "23": card_C, "24": card_D}

# 口パク
for name, frames in STAMPS.items():
    for i, fr in enumerate(frames):
        if i in soft.TALK_FRAMES and not fr.get("nochar"):
            fr["poses"] = fr["poses"] + [talk_santa if name in SANTA else talk_deer]


FIT_FIXED = None
FIT_LAST = None


def fit_all(cells, m=11):
    """全コマに同じ縮小・移動をかけて、どのコマも縁から m px 以上あける(コマごとに変えないので、ぶれない)。"""
    box = None
    for c in cells:
        b = c.getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    if box is None:
        return cells
    w, h = box[2] - box[0], box[3] - box[1]
    k = min(1.0, (CW - 2 * m) / w, (CH - 2 * m) / h)
    nw, nh = w * k, h * k
    # 中心はなるべく元の位置、はみ出す分だけ内側へ
    cx = min(max((box[0] + box[2]) / 2, m + nw / 2), CW - m - nw / 2)
    cy = min(max((box[1] + box[3]) / 2, m + nh / 2), CH - m - nh / 2)
    global FIT_LAST
    FIT_LAST = (box, k, cx, cy)
    if FIT_FIXED:  # 決まった縮小・移動を使う(set05: set04 と絵の位置・大きさを1pxも変えないため。やり方も同じ)
        box, k, cx, cy = FIT_FIXED
        nw, nh = (box[2] - box[0]) * k, (box[3] - box[1]) * k
        for i, c in enumerate(cells):
            b = c.getbbox()
            if b and (b[0] < box[0] or b[1] < box[1] or b[2] > box[2] or b[3] > box[3]):
                print(f"!! {i + 1}コマ目: 文字が set04 の範囲 {box} の外に出ています {b}")
    out = []
    for c in cells:
        part = c.crop(box)
        if k < 1.0:
            part = part.resize((max(1, round(nw)), max(1, round(nh))), Image.LANCZOS)
        n = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        n.alpha_composite(part, (round(cx - part.width / 2), round(cy - part.height / 2)))
        n.putalpha(n.getchannel("A").point(lambda v: 255 if v >= 110 else 0))
        out.append(n)
    return out


def render(frames, path):
    with tempfile.TemporaryDirectory() as tmp:
        soft.chara_png(frames, f"{tmp}/c.png")
        soft.text_png(frames, f"{tmp}/t.png")
        chara = Image.open(f"{tmp}/c.png").convert("RGBA")
        text = Image.open(f"{tmp}/t.png").convert("RGBA")
    cells = []
    for i, fr in enumerate(frames):
        x0, y0 = (i % 4) * CW, (i // 4) * CH
        cell = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        if fr.get("back"):
            fr["back"](cell)
        if not fr.get("nochar"):
            cc = chara.crop((x0, y0, x0 + CW, y0 + CH))
            a = cc.getchannel("A")
            # キャラがコマの外へはみ出すと、となりのコマに描かれてしまう。ふちに触れたら知らせる
            if any(a.crop(b).getbbox() for b in ((0, 0, 1, CH), (CW - 1, 0, CW, CH), (0, 0, CW, 1), (0, CH - 1, CW, CH))):
                print(f"!! {i + 1}コマ目: キャラがコマのふちに触れています(はみ出し)")
            cell.alpha_composite(cc)
        if fr.get("front"):
            fr["front"](cell)
        tt = text.crop((x0, y0, x0 + CW, y0 + CH))
        if any(tt.getchannel("A").crop(b).getbbox() for b in ((0, 0, 1, CH), (CW - 1, 0, CW, CH), (0, 0, CW, 1), (0, CH - 1, CW, CH))):
            print(f"!! {i + 1}コマ目: 文字がコマのふちに触れています(はみ出し)")
        cell.alpha_composite(tt)
        cells.append(cell)
    sheet = Image.new("RGBA", (CW * 4, CH * 3), inko.BG)
    for i, cell in enumerate(fit_all(cells)):
        sheet.alpha_composite(cell, ((i % 4) * CW, (i // 4) * CH))
    sheet.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stamp", choices=sorted(list(STAMPS) + list(CARDS)))
    ap.add_argument("--png", required=True)
    a = ap.parse_args()
    if a.stamp in CARDS:
        frames = fit_all(CARDS[a.stamp]())
        newyear.card_sheet(frames, a.png)
    else:
        render(STAMPS[a.stamp], a.png)
    print(f"シート: {a.png}")


if __name__ == "__main__":
    main()
