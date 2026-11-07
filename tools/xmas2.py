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
    # al・ar はどちらも「外へ上げる角度」。サンタの右腕(P6)は向きが逆なので符号を反転して渡す
    return [dict(al=-al[i], ar=ar[i], hat=hat[i], hl=hl[i], hr=hr[i], **extra) for i in range(12)]


HAT_SWING = [0, -8, -14, -6, 10, 16, 8, -6, -12, -4, 8, 4]

STAMPS = {}
SANTA, DEER = set(), set()

# 02 プレゼントです: サンタが真ん中で、大きなプレゼントを前へさし出す(ぴょんと跳ねて、ぐっと前へ)。
#    うしろにプレゼントの山、上からリボンの紙ふぶき。文字は右上
MV02 = santa_moves([0, 6, 14, 22, 30, 36, 36, 30, 24, 30, 36, 30], [0, 10, 26, 40, 26, 10, -4, 10, 28, 42, 28, 12], HAT_SWING,
                   hl=[0, 3, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0], hold="biggift")
PATH02 = [(140, 256), (140, 250), (140, 244), (140, 250), (140, 256), (140, 256), (140, 256), (140, 250), (140, 246),
          (140, 250), (140, 256), (140, 256)]
POSE02 = [S, J0, J1, J0, S, S, S, J0, J1, J0, S, S]
STAMPS["02"] = with_layers(paths(make(
    "xmas", [("プレゼント", 34, True), ("です", 32, False)], "A",
    lambda i: [POSE02[i], happy, P(**MV02[i]), santa],
    lambda i, av: winter.confetti(2, 7, i, box=(24, 30, 120, 110)), m=dict(scale=0.94, anchor=PATH02[0]), x0=126),
    PATH02), back=lambda L_, i: put_img(L_, pile_img(), 248, 196, 1.15))
SANTA.add("02")

# 03 今年もありがとう: 大きなリースの前で、サンタがていねいにおじぎ(帽子が遅れてゆれる)。
#    ハートが下から上へ流れる。文字は左に大きく
POSE03 = [B1, S, S, B1, B2, B2, B2, B1, S, S, B1, B1]
MV03 = santa_moves([0, 4, -4, -14, -20, -22, -20, -14, -2, 6, -10, 0], [0, -4, 6, -10, -18, -24, -18, -10, 4, -4, -12, 0],
                   [0, 6, -4, -12, -16, -6, 6, 14, 6, -6, -10, 0], gift=False, hold=None)
STAMPS["03"] = with_layers(paths(make(
    "xmas", [("今年も", 42, True), ("ありがとう", 32, False)], "A",
    lambda i: [POSE03[i], happy, P(**MV03[i]), santa],
    lambda i, av: [("heart", 40 + j * 34, 250 - ((i * 14 + j * 40) % 120), 8 + j % 2 * 2) for j in range(3)],
    m=dict(scale=0.9, anchor=(214, 256)), x0=14), [(214, 256)] * 12),
    back=lambda L_, i: put_img(L_, wreath_img(160, i), 222, 136))
SANTA.add("03")

# 04 いい子にしてた?: 上にくつしたのガーランドがゆれる。サンタは右から歩いてきて、首をかしげる(体ごと左右にかたむく)。
#    「?」が跳ねる。文字は下
POSE04 = [S, S, J0, S, J0, S, S, S, S, S, S, S]
MV04 = santa_moves([0, 10, -6, 12, -4, 8, 18, 24, 18, 10, 18, 22], [0, -8, 10, -6, 12, -2, -10, -6, -10, -6, -8, -4],
                   HAT_SWING, hl=[0, 3, 0, 3, 0, 3, 0, 0, 0, 0, 0, 0], hr=[0, 0, 3, 0, 3, 0, 0, 0, 0, 0, 0, 0], hold=None)
PATH04 = [(160, 214), (232, 212), (214, 208), (196, 212), (180, 208), (168, 212), (160, 214), (160, 214), (160, 214),
          (160, 214), (160, 214), (160, 214)]
TILT04 = [-6, 0, 0, 0, 0, 0, -6, -10, -6, 4, 8, 4]


def tilt(deg):
    return lambda c: [c[k].update(rot=c[k].get("rot", 0)) for k in c] if False else None


def stockings_front(layer, i):
    d = ImageDraw.Draw(layer)
    pts = [(14 + j * 29, 26 + 10 * math.sin(j / 10 * math.pi)) for j in range(11)]
    d.line(pts, fill=L, width=5)
    d.line(pts, fill=GOLD, width=3)
    for j, (x, y) in enumerate(pts[1:-1:2]):
        sw = 5 * math.sin(i * 1.1 + j)
        col = (RED, GREEN, "#7FC4FF", RED)[j % 4]
        poly = [(x - 8 + sw * 0.2, y), (x + 8 + sw * 0.2, y), (x + 8 + sw, y + 24), (x + 16 + sw * 1.1, y + 28),
                (x + 16 + sw * 1.1, y + 36), (x - 2 + sw, y + 36), (x - 8 + sw * 0.9, y + 28)]
        d.polygon(poly, fill=col, outline=L)
        d.rounded_rectangle((x - 10, y - 2, x + 10, y + 7), radius=3, fill=WHITE, outline=L, width=2)


STAMPS["04"] = with_layers(paths(make(
    "xmas", [("いい子に", 32, True), ("してた?", 32, True)], "B",
    lambda i: [POSE04[i], happy, (lambda c, d=TILT04[i]: inko.move(c, ["P8", "P9", "P10", "P11", "P12", "P13", "P14", "P15"], dx=d / 3)),
               P(**MV04[i]), santa],
    lambda i, av: [("note", 250, 92 - abs(math.sin(i * 0.9)) * 14, 30)] if False else [],
    m=dict(scale=0.86, anchor=PATH04[0]), x0=14, y0=164), PATH04), front=stockings_front)
SANTA.add("04")


def qmark_front(layer, i):
    font = ImageFont.truetype(str(soft.HAND_FONT), 40)
    d = ImageDraw.Draw(layer)
    y = 96 - abs(math.sin(i * 0.9)) * 16
    d.text((250, y), "?", font=font, anchor="mm", fill=GREEN, stroke_width=5, stroke_fill="white")


_st04 = STAMPS["04"]
for i, fr in enumerate(_st04):
    f0 = fr["front"]
    fr["front"] = (lambda layer, i=i, f0=f0: (f0(layer), qmark_front(layer, i)))

# 06 いってきます: トナカイが大きなそりを引いて、左から右へ走る(そりはトナカイのうしろで一緒に動く)。
#    雪が降る。文字は上
RUN06 = [(170, 258), (96, 256), (110, 250), (124, 256), (138, 250), (152, 256), (166, 250), (180, 256), (194, 250),
         (206, 256), (190, 250), (176, 256)]
MV06 = [dict(), dict(fl=30, lfl=10, hr=5, el=-14), dict(fr=30, lfr=10, hl=5, er=-14), dict(fl=30, lfl=10, hr=5, el=-14),
        dict(fr=30, lfr=10, hl=5, er=-14), dict(fl=30, lfl=10, hr=5, el=-14), dict(fr=30, lfr=10, hl=5, er=-14),
        dict(fl=30, lfl=10, hr=5, el=-14), dict(fr=30, lfr=10, hl=5, er=-14), dict(fl=24, lfl=8, el=-8),
        dict(fr=24, lfr=8, er=-8), dict(fl=16, lfl=4)]
STAMPS["06"] = with_layers(paths(make(
    "xmas", [("いって", 44, True), ("きます!", 38, True)], "B",
    lambda i: [S, happy, P(**MV06[i]), reindeer], snowf(6, 7), m=dict(scale=0.78, anchor=RUN06[0]), x0=16), RUN06),
    back=lambda L_, i: put_img(L_, sleigh_image(0.9, 0), RUN06[i][0] - 92, 214))
DEER.add("06")

# 07 今から帰ります: 夜空。大きな三日月、星がまたたく。トナカイが右上から左下へ空をかけおりてくる(跳ねる姿勢)。文字は下
FLY07 = [(110, 186), (250, 116), (230, 124), (210, 134), (190, 144), (170, 154), (150, 164), (130, 174), (116, 182),
         (110, 186), (110, 180), (110, 186)]


def night_back(layer, i):
    d0 = ImageDraw.Draw(layer)  # 夜空(紺の角丸パネル)
    d0.rounded_rectangle((12, 12, 308, 200), radius=26, fill="#24305E", outline=L, width=3)
    d0.chord((12, 150, 308, 250), 180, 360, fill=WHITE, outline=L, width=2)  # 雪の丘(パネルの下に)
    put_img(layer, night_img(), 262, 56, 1.0)
    d = ImageDraw.Draw(layer)
    for j, (x, y) in enumerate(((40, 30), (110, 22), (196, 40), (70, 84), (300, 110), (24, 120))):
        s = 6 + ((i + j) % 3) * 3
        winter.draw_marks2(layer, [("spark", x, y, s)], 0, 0)


STAMPS["07"] = with_layers(paths(make(
    "xmas", [("今から", 38, True), ("帰ります", 32, False)], "A",
    lambda i: [J1 if 1 <= i <= 7 else S, happy, P(fl=24, fr=24, lfl=6, lfr=6, el=-16, er=-16) if 1 <= i <= 7 else P(el=-4, er=4),
               reindeer],
    lambda i, av: [], m=dict(scale=0.66, anchor=FLY07[0]), x0=120, y0=170), FLY07), back=night_back)
DEER.add("07")

# 08 飾りつけ中: 大きなツリー(飾りが少しずつふえる)。サンタが左から背のびして、星をてっぺんへ。文字は左上
POSE08 = [J0, S, J0, J1, J0, S, J0, J1, J0, S, J0, J1]
MV08 = santa_moves([0, -4, 4, 10, 4, -4, 4, 10, 4, -4, 4, 10], [0, 30, 44, 56, 44, 30, 44, 56, 44, 30, 44, 56], HAT_SWING,
                   hold="star", hand="P7")  # ツリーの側(見て右)の手で星をのせる
STAMPS["08"] = paths(make(
    "xmas", [("飾りつけ", 40, True), ("中です", 34, False)], "A",
    lambda i: [POSE08[i], happy, P(**MV08[i]), santa, tree_page(108, 30, 226, (110, 256), 0.9, i, style="ball")],
    lambda i, av: [("spark", 96 + (i % 3) * 30, 70 + (i % 2) * 20, 7)], m=dict(scale=0.9, anchor=(110, 256)), x0=14),
    [(110, 256)] * 12)
SANTA.add("08")

# 09 キラキラ: 電球がいっぱいの大きなツリーが、コマごとに光の色をかえる。まわりに光の線。
#    トナカイが右から見上げて、うっとり左右にゆれる。文字は上に大きく
STAMPS["09"] = with_layers(paths(make(
    "xmas", [("キラキラ", 50, True)], "C",
    lambda i: [S, happy, P(el=-10 + 4 * (i % 2), er=10 - 4 * (i % 2), fl=8 * (i % 2), fr=8 * ((i + 1) % 2)), reindeer,
               tree_page(30, 64, 200, (240, 258), 0.82, i, style="lights")],
    lambda i, av: [("spark", x, y, 8 + ((i + j) % 3) * 4) for j, (x, y) in enumerate(((22, 120), (150, 150), (40, 230), (156, 88)))],
    m=dict(scale=0.82, anchor=(240, 258)), x0=20, wave_amp=5), [(240 + (3 if i % 2 else -3), 258) for i in range(12)]))
DEER.add("09")

# 10 楽しみです: 暖炉とくつした。サンタがうれしくて、その場でぴょんぴょん(手を交互に上げる)。文字は上
POSE10 = [S, J0, J1, J2, J1, J0, S, J0, J1, J2, J1, J0]
MV10 = santa_moves([0, 20, 40, 50, 30, 10, 0, 10, 24, 34, 20, 6], [0, 6, 18, 30, 44, 50, 30, 20, 40, 50, 34, 14],
                   HAT_SWING, gift=False, hold=None)
STAMPS["10"] = with_layers(paths(make(
    "xmas", [("楽しみ", 46, True), ("です♪", 38, True)], "B",
    lambda i: [POSE10[i], happy, P(**MV10[i]), santa],
    lambda i, av: [("note", 40 + (i % 3) * 8, 120 - (i % 4) * 10, 26), ("note", 290, 150 - ((i + 2) % 4) * 10, 22)],
    m=dict(scale=0.86, anchor=(218, 256)), x0=14), [(218, 256)] * 12),
    back=lambda L_, i: put_img(L_, fireplace_img(i), 96, 190, 1.0))
SANTA.add("10")

# 11 いただきます: テーブルのチキン。サンタがテーブルのうしろで、両手を交互に上げてうれしそう。文字は上
MV11 = santa_moves([0, 50, 24, 50, 24, 50, 24, 50, 24, 50, 24, 40], [0, 24, 50, 24, 50, 24, 50, 24, 50, 24, 50, 30], HAT_SWING,
                   gift=False, hold=None)


def table11(layer, i):
    put_img(layer, table_img(260), 160, 238)
    put_img(layer, chicken_img(i), 160, 220, 0.95)
    soft.draw_marks(layer, [("steam", 140 + j * 18, 200, 7 + (i + j) % 3 * 2, i * 0.9 + j) for j in range(3)], 0, 0)


STAMPS["11"] = with_layers(paths(make(
    "xmas", [("いただきます!", 34, True)], "B",
    lambda i: [S, happy, P(**MV11[i]), santa], lambda i, av: [], m=dict(scale=0.8, anchor=(160, 198)), x0=30, y0=8),
    [(160, 198 - (4 if i % 2 else 0)) for i in range(12)]), front=table11)
SANTA.add("11")

# 12 ケーキ食べよう: 前に大きなケーキ(ろうそくの炎がゆれる)。トナカイがうしろでぴょこぴょこ。文字は上
STAMPS["12"] = with_layers(paths(make(
    "xmas", [("ケーキ", 40, True), ("食べよう!", 32, False)], "B",
    lambda i: [S if i % 2 == 0 else J0, happy, P(el=-12 if i % 2 else 6, er=12 if i % 2 else -6, fl=20 * (i % 2), fr=20 * ((i + 1) % 2),
                                               lfl=6 * (i % 2), lfr=6 * ((i + 1) % 2)), reindeer],
    lambda i, av: [("spark", 60, 190, 8 + (i % 2) * 3), ("spark", 268, 180, 7 + ((i + 1) % 2) * 3)],
    m=dict(scale=0.78, anchor=(196, 210)), x0=14, y0=10), [(196, 210 - (6 if i % 2 else 0)) for i in range(12)]),
    front=lambda L_, i: put_img(L_, cake_img(i), 150, 206, 1.1))
DEER.add("12")

# 13 かんぱい: サンタがグラスを高く上げて「かんぱい」。泡とキラキラがはじける。金の紙ふぶき。文字は右
MV13 = santa_moves([0, -6, 4, -4, 6, -2, 4, -4, 6, -2, 4, 0], [0, 20, 44, 60, 50, 60, 44, 56, 50, 60, 48, 40], HAT_SWING,
                   gift=False, hold="glass")
for m_ in MV13:
    m_["al"], m_["ar"] = -m_["ar"], -m_["al"]  # グラスを持つ右手(見て左)を高く上げる
STAMPS["13"] = paths(make(
    "xmas", [("かんぱい", 36, True), ("♪♪", 34, True)], "B",
    lambda i: [S if i % 3 else J0, happy, P(**MV13[i]), santa],
    lambda i, av: winter.confetti(13, 8, i, box=(30, 30, 300, 120)) + [("spark", 70, 70 - (i % 3) * 6, 9 + (i % 2) * 4)],
    m=dict(scale=0.9, anchor=(108, 256)), x0=150, y0=40), [(112, 256 - (5 if i % 3 == 0 and i else 0)) for i in range(12)])
SANTA.add("13")

# 14 寒いですね: 雪がたくさん。トナカイが赤いマフラーで、ぶるぶる震える(左右に小きざみ)。うしろに雪の丘。文字は上
SHIV = [0, -4, 4, -4, 4, -3, 3, -4, 4, -3, 3, 0]


def scarf_deer(c):
    fx, fy = winter.face_off(c)
    xmas.put(c, "NECK9_scarf", RED, 2.4, 82, 18, 119 + fx, 200 + fy,
             "M2 6 C26 16 56 16 80 6 L80 14 C56 24 26 24 2 14 Z", vw=82, vh=24)
    xmas.put(c, "NECK9_scarft", RED, 2.4, 16, 34, 182 + fx, 206 + fy,
             "M2 2 L14 2 L15 28 L12 32 L9 28 L6 32 L3 28 Z", rot=-8, vw=16, vh=34)
    xmas.put(c, "NECK9_scarfs", WHITE, 0, 12, 4, 184 + fx, 222 + fy, soft.ellipse_d(12, 4), rot=-8)


def hills_back(layer, i):
    d = ImageDraw.Draw(layer)
    d.ellipse((-80, 180, 200, 330), fill=WHITE, outline=L, width=2)
    d.ellipse((150, 196, 420, 330), fill="#F4FAFF", outline=L, width=2)


STAMPS["14"] = with_layers(paths(make(
    "xmas", [("寒い", 54, True), ("ですね…", 36, False)], "C",
    lambda i: [S, blink, P(el=-18, er=18), reindeer, scarf_deer],
    lambda i, av: winter.snow(14, 12, i, avoid=((118, 110, 290, 262),)), m=dict(scale=0.9, anchor=(196, 256)), x0=16, shiver=(2, 4)),
    [(196 + SHIV[i], 256) for i in range(12)]), back=hills_back)
DEER.add("14")

# 15 雪だるま作ったよ: 大きな雪だるま(腕をふる)の横で、サンタがばんざいでぴょん。文字は上
POSE15 = [S, J0, J1, J2, J1, J0, S, J0, J1, J2, J1, J0]
MV15 = santa_moves([0, 16, 36, 50, 36, 16, 0, 16, 36, 50, 36, 16], [0, 10, 30, 46, 40, 20, 4, 10, 30, 46, 40, 20],
                   HAT_SWING, gift=False, hold=None)
STAMPS["15"] = with_layers(paths(make(
    "xmas", [("雪だるま", 42, True), ("作ったよ!", 36, False)], "A",
    lambda i: [POSE15[i], happy, P(**MV15[i]), santa], snowf(15, 5),
    m=dict(scale=0.86, anchor=(108, 256)), x0=96), [(108, 256)] * 12),
    back=lambda L_, i: put_img(L_, snowman_img(i), 236, 188, 1.05))
SANTA.add("15")

# 16 ホワイトクリスマス: 雪の村。しんしんと雪。トナカイが丘の上で空を見上げ、雪をうけてうっとり。文字は上で大きくカーブ
STAMPS["16"] = with_layers(paths(make(
    "xmas", [("ホワイト", 42, True), ("クリスマス", 40, True)], "C",
    lambda i: [S, blink, P(el=-8 - 4 * (i % 2), er=8 + 4 * (i % 2)), reindeer],
    lambda i, av: winter.snow(16, 14, i, avoid=((96, 130, 224, 262),)), m=dict(scale=0.78, anchor=(160, 246)), x0=20, wave_amp=4),
    [(160, 246 - (3 if i % 2 else 0)) for i in range(12)]), back=lambda L_, i: put_img(L_, village_img(), 160, 196))
DEER.add("16")

# 17〜20 文字が主役(大きな文字+小さなキャラと飾り)
# 17 Merry Christmas: 英字が大きく波打つ。右下でトナカイがゆれ、左下に大きなリース、右上でベルがゆれる
STAMPS["17"] = with_layers(paths(make(
    "xmas", [("Merry", 56, True), ("Christmas", 44, True)], "C",
    lambda i: [S, happy, P(el=-6 * (i % 2), er=6 * (i % 2)), reindeer],
    lambda i, av: [("bell", 286, 40 + 6 * math.sin(i), 18, 18 * math.sin(i * 1.3))],
    m=dict(scale=0.62, anchor=(250, 262)), x0=4, wave_amp=6), [(250, 262 - (3 if i % 2 else 0)) for i in range(12)]),
    back=lambda L_, i: put_img(L_, wreath_img(120, i), 70, 202, 1.0))
DEER.add("17")

# 18 メリクリ!: 大きな文字。小さなサンタが下を走りぬける(左→右)。プレゼントがぽんぽん
RUN18 = [(160, 262), (60, 258), (82, 252), (104, 258), (126, 252), (148, 258), (170, 252), (192, 258), (214, 252),
         (236, 258), (250, 252), (260, 258)]
STAMPS["18"] = paths(make(
    "xmas", [("メリクリ!", 64, True)], "C",
    lambda i: [S if i % 2 == 0 else J0, happy, P(**santa_moves([0] + [30, -10] * 5 + [20], [0] + [-10, 30] * 5 + [-10], HAT_SWING,
                                                                hold=None, gift=False)[i]), santa],
    lambda i, av: winter.confetti(18, 8, i, box=(20, 120, 300, 180)), m=dict(scale=0.6, anchor=RUN18[0]), x0=14, y0=40,
    wave_amp=6), RUN18)
SANTA.add("18")

# 19 よいクリスマスを: 文字は上に2段。下をそりが左から右へかけぬける(そりは12コマずっと見える)。ベルが2つ跳ねる
STAMPS["19"] = with_layers(make(
    "xmas", [("よい", 46, True), ("クリスマスを", 40, True)], "A",
    lambda i: [S, happy, P(), reindeer], lambda i, av: [("bell", 40 + i * 4, 140 + 10 * math.sin(i), 18, 18 * math.sin(i * 1.3)),
                                                        ("bell", 286 - i * 3, 150 - 10 * math.sin(i), 16, -18 * math.sin(i * 1.3))],
    m=dict(scale=0.58, anchor=(0, 0)), x0=20, y0=20),
    back=None, front=lambda L_, i: (winter.draw_marks2(L_, [], 0, 0), put_img(L_, sleigh_image(0.95, 6), 70 + i * 16, 210 - i * 2)))
for fr in STAMPS["19"]:
    fr["nochar"] = True  # キャラは出さない(そりが主役)。そりにはプレゼントがのっている

# 20 ありがとう: 大きな文字。トナカイがぺこり。下にプレゼントの山、ハートがふわふわ
STAMPS["20"] = with_layers(paths(make(
    "xmas", [("ありがとう", 56, True)], "C",
    lambda i: [[B1, B2, B2, B1][i % 4] if 3 <= i <= 9 else S, happy, P(el=-10, er=10), reindeer],
    lambda i, av: [("heart", 260 + j * 16, 150 - ((i * 10 + j * 30) % 70), 9) for j in range(2)],
    m=dict(scale=0.66, anchor=(214, 262)), x0=14, y0=36, wave_amp=5), [(214, 262)] * 12),
    back=lambda L_, i: put_img(L_, pile_img(), 76, 210, 0.9))
DEER.add("20")


# ---- 21〜24 クリスマスカード(ペンで書いていく・20コマ) ---------------------------------

def card_base_x(kind):
    def f():
        im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        im.alpha_composite(card_img(kind), (80, 11))
        return im
    return f


def char_icon(name, height):
    """カードのすみに描く、小さなサンタ・トナカイ(キャラと同じ図形)。"""
    fn = santa if name == "santa" else reindeer
    fr = [kf([S, happy, P(gift=False, hold=None), fn], scale=1.0, anchor=(160, 258))]
    with tempfile.TemporaryDirectory() as tmp:
        soft.chara_png(fr, f"{tmp}/s.png")
        im = Image.open(f"{tmp}/s.png").convert("RGBA").crop((0, 0, CW, CH))
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    im = im.crop(im.getbbox())
    k = height / im.height
    return im.resize((round(im.width * k), height), Image.LANCZOS)


def pen_lines(lines):
    """カードに書く文字: (文字, 中心x, 中心y, 大きさ, 色) を、手書きの書体で一文字ずつ(白いフチなし)。"""
    out = []
    for text, cx, cy, size, col in lines:
        font = ImageFont.truetype(str(soft.HAND_FONT), size)
        adv = [font.getlength(ch) for ch in text]
        x = cx - sum(adv) / 2
        for j, (ch, w) in enumerate(zip(text, adv)):
            if ch != " ":
                g = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
                c_ = col[j % len(col)] if isinstance(col, list) else col
                ImageDraw.Draw(g).text(((size + 20) / 2, (size + 20) / 2), ch, font=font, anchor="mm", fill=c_)
                dy = 3 * math.sin(j * 0.9)  # 少しの段差(まっすぐ並べない)
                out.append((None, g, (round(x + w / 2 - g.width / 2), round(cy + dy - g.height / 2))))
            x += w
    return out


CARDS = {}


def card21():
    ic = char_icon("santa", 70)
    return newyear.write_frames(card_base_x(0), pen_lines([("Merry", 160, 64, 38, [RED, GREEN]), ("Christmas", 160, 108, 26, [RED, GREEN])]),
                                lambda im, k: (put_img(im, tree_ic(), 118, 200, 0.62 * k), put_img(im, ic, 196, 206, k)), newyear.pen)


def tree_ic():
    only_tree = lambda c: [c.pop(k) for k in list(c) if not k.startswith("BG")]
    fr = [kf([tree(70, 108, 0.95, 3), only_tree], scale=1.0, anchor=(160, 258))]
    with tempfile.TemporaryDirectory() as tmp:
        soft.chara_png(fr, f"{tmp}/t.png")
        im = Image.open(f"{tmp}/t.png").convert("RGBA").crop((0, 0, CW, CH))
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    return im.crop(im.getbbox())


def card22():
    ic = char_icon("deer", 74)

    def deco(im, k):
        winter.draw_marks2(im, [("spark", 116, 186, 9 * k), ("spark", 104, 222, 7 * k), ("spark", 136, 214, 6 * k)], 0, 0)
        put_img(im, ic, 194, 204, k)
    return newyear.write_frames(card_base_x(1), pen_lines([("Happy", 160, 64, 38, [GREEN, RED]), ("Holidays", 160, 108, 28, [GREEN, RED])]),
                                deco, newyear.pen)


def card23():
    ic = char_icon("santa", 66)
    return newyear.write_frames(card_base_x(2), pen_lines([("メリー", 160, 60, 36, RED), ("クリスマス", 160, 104, 30, GREEN_D)]),
                                lambda im, k: (put_img(im, wreath_img(70, 0), 124, 200, k), put_img(im, ic, 196, 208, k)), newyear.pen)


def card24():
    ic = char_icon("deer", 70)
    return newyear.write_frames(card_base_x(3), pen_lines([("よいお年を", 160, 70, 30, RED), ("おむかえください", 160, 108, 18, GREEN_D)]),
                                lambda im, k: (put_img(im, gift_img(46, 46, RED, GOLD), 122, 210, k), put_img(im, ic, 196, 204, k)),
                                newyear.pen)


CARDS = {"21": card21, "22": card22, "23": card23, "24": card24}

# 口パク
for name, frames in STAMPS.items():
    for i, fr in enumerate(frames):
        if i in soft.TALK_FRAMES and not fr.get("nochar"):
            fr["poses"] = fr["poses"] + [talk_santa if name in SANTA else talk_deer]


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
            cell.alpha_composite(chara.crop((x0, y0, x0 + CW, y0 + CH)))
        if fr.get("front"):
            fr["front"](cell)
        cell.alpha_composite(text.crop((x0, y0, x0 + CW, y0 + CH)))
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
