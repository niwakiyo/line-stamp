#!/usr/bin/env python3
"""ていねいインコ set03「ひつじ年のお正月」: ひつじのキャラと、筆で書いていく年賀状。

  確認用シート : python3 tools/newyear.py 01 --png sheet.png
  (キャラのスタンプは 12コマ=4x3、年賀状は 20コマ=5x4 のシートになる)

決まりごと(docs/stamp_rules.md)はそのまま守る。キャラの動きは winter.py / soft.py と同じ仕組み。
"""
import argparse
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import inko
import soft
import winter
from soft import kf, S, J0, J1, J2, B1, B2, happy, talk, step, flap, tuft, TUFT
from winter import add, head_off, face_off, HORN, confetti, make, MID

ROOT = Path(__file__).resolve().parent.parent
BRUSH_FONT = ROOT / "assets/fonts/YujiSyuku-Regular.ttf"

# ---- ひつじ ---------------------------------------------------------
WOOL = "#FFFDF6"
FACE_YELLOW = "#FFE98F"
HOOF = "#E8CFA6"

_scallop = soft.scallop


def wool_scallop(w, h, bumps=18, depth=1.6):
    """体のふちを、ひつじの毛のように大きく波打たせる。"""
    return _scallop(w, h, bumps=13, depth=4.2)


soft.scallop = wool_scallop

_order = winter.inko_order


def inko_order(key):
    if key.startswith("FACE"):  # 顔の黄色い部分は、体の毛より前・目や口より後ろ
        return winter.ORDER.index("P5") - 0.5
    return _order(key)


winter.inko_order = inko_order
soft.inko_order = inko_order


SHEEP_FACE = "#FFF1DC"
EAR = "#F3D9C0"
WOOL_TUFT = ("M5 20 C1 20 0 14 4 12 C3 6 9 3 13 6 C15 1 23 1 25 6 C29 5 31 10 28 13 C31 15 30 20 26 20 Z")
EAR_L = "M2 7 C6 1 18 0 27 5 C26 10 16 14 8 13 C4 12 2 10 2 7 Z"
EAR_R = "M26 7 C22 1 10 0 1 5 C2 10 12 14 20 13 C24 12 26 10 26 7 Z"
NOSE = "M3 2 C3 1 17 1 17 2 C17 5 13 7 10 7 C7 7 3 5 3 2 Z"
MOUTH = ("M3 6 C5 10 8 10 9 7 C10 10 13 10 15 6 C15 5 14 5 13.5 6 C12.5 8 10.5 8 9.8 5.5 L8.2 5.5 "
         "C7.5 8 5.5 8 4.5 6 C4 5 3 5 3 6 Z")
MOUTH_OPEN = "M4 4 C4 3 14 3 14 4 C14 10 12 13 9 13 C6 13 4 10 4 4 Z"


def sheep(c):
    """ひつじ: もこもこの白い毛の体と前足、生成りの顔、たれた耳、くるんとした角、頭の毛のかたまり。
    くちばしの代わりに小さな鼻と「ω」の口。目とほっぺはシリーズで同じ描き方。
    顔・耳は顔(P14)の位置から、角・頭の毛は頭(P1)の位置から置くので、おじぎやジャンプについて行く。"""
    fx, fy = face_off(c)  # 鼻(P14)を描き替える前に、顔のずれを取っておく
    hx, hy = head_off(c)
    for k in ("P4", "P5", "P6", "P7"):
        c[k]["fill"] = WOOL
    c["P1"].update(fill=WOOL, d=WOOL_TUFT, w=32, h=24, left=c["P1"]["left"] - 1, top=c["P1"]["top"] + 2)
    for k in ("P2", "P3"):
        c[k]["fill"] = HOOF
    add(c, "FACE1", SHEEP_FACE, inko.INK, 1.5, 84, 62, 118 + fx, 149 + fy, soft.ellipse_d(84, 62))
    add(c, "FACE2_earL", EAR, inko.INK, 2, 30, 15, 92 + fx, 162 + fy, EAR_L, rot=-18)
    add(c, "FACE3_earR", EAR, inko.INK, 2, 30, 15, 198 + fx, 162 + fy, EAR_R, rot=18)
    add(c, "ACC1_hornL", "#E9C98F", inko.INK, 2, 26, 26, 104 + hx, 134 + hy, HORN, rot=-20)
    add(c, "ACC2_hornR", "#E9C98F", inko.INK, 2, 26, 26, 190 + hx, 134 + hy, HORN, rot=-160)
    c["P14"].update(d=NOSE, fill="#C9957A", sw=0, stroke=None)
    c["P15"].update(d=MOUTH, fill=soft.LINE, sw=0, stroke=None)


def sheep_talk(c):
    """ひつじの口パク: 口の形を少し開いた丸にして、色を変えるだけ(大きさ・位置はそのまま)。"""
    c["P15"].update(d=MOUTH_OPEN, fill=soft.BEAK_OPEN_FILL, sw=1.5, stroke=inko.INK)


# ---- 01 あけまして/おめでとう/ございます(ひつじのインコ) ----------------------------

def cf01(i, av):
    return confetti(31, 4, i, box=(240, 30, 296, 84)) + confetti(32, 4, i, box=(30, 196, 112, 250))


STAMPS = {
    "01": make("new", [("あけまして", 46, True), ("おめでとう", 34, False), ("ございます", 34, False)], "A",
               lambda i: [[S, happy], [J0, happy], [J1, happy], [J1, happy, J2], [J1, happy], [J0, happy],
                          [S, happy], [B1, happy], [B2, happy], [B1, happy], [S, happy], [S, happy]][i] + [sheep],
               cf01, m=MID),
}

ARMS = {  # (左の前足, 右の前足) 肩を支点に最大16°。跳ぶときは開き、おじぎでは小さく
    "01": ([0, -6, 14, 16, 12, -4, 4, 2, 4, 2, 6, 2], [0, -4, 10, 14, 16, -6, 8, 4, 2, 4, 2, 6]),
}

for name, frames in STAMPS.items():
    left, right = ARMS[name]
    for i, fr in enumerate(frames):
        extra = []
        if i in soft.TALK_FRAMES:
            extra.append(sheep_talk)
        if i in soft.STEP_FRAMES:
            extra.append(step(soft.STEP_FRAMES[i]))
        if i:
            extra += [flap("P6", left[i]), flap("P7", right[i]), tuft(TUFT[i])]
        fr["poses"] = fr["poses"] + extra


# ---- 年賀状(筆で書いていく) --------------------------------------------------------
CW, CH = 320, 270
CARD = "#FFF9EE"
INK_BLACK = "#2E2A2A"
SHU = "#D8402F"


def sheep_icon(height):
    """年賀状のすみに描く、小さなひつじ(キャラと同じ図形を描いて縮める)。"""
    frames = [kf([S, happy, sheep], scale=1.0, anchor=(160, 258))]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "s.png"
        soft.chara_png(frames, p)
        im = Image.open(p).convert("RGBA").crop((0, 0, CW, CH))
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    im = im.crop(im.getbbox())
    k = height / im.height
    return im.resize((round(im.width * k), height), Image.LANCZOS)


def card_base():
    """はがき(生成り・朱の細い枠)。外側に白いふちを付けて、暗い背景でも形が分かるようにする。"""
    im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 82, 16, 238, 254
    d.rounded_rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), radius=12, fill="white")
    d.rounded_rectangle((x0, y0, x1, y1), radius=9, fill=CARD, outline=soft.LINE, width=3)
    d.rounded_rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), radius=5, outline=SHU, width=2)
    return im


def glyph(ch, size, color=INK_BLACK):
    font = ImageFont.truetype(str(BRUSH_FONT), size)
    g = Image.new("RGBA", (size + 20, size + 20), (0, 0, 0, 0))
    # 少し太らせて、筆の墨のたっぷりした感じを出す
    ImageDraw.Draw(g).text(((size + 20) / 2, (size + 20) / 2), ch, font=font, anchor="mm", fill=color,
                           stroke_width=1, stroke_fill=color)
    return g


def reveal(g, k, n=4):
    """書いている途中: 字を上から n 本の帯に分け、k 本目まで見せる。
    筆は帯ごとに左右へ振れながら下りる(偶数本目は右端、奇数本目は左端で止まる)。戻り値は (画像, 筆先の位置)。"""
    bb = g.getbbox()
    x0, y0, x1, y1 = bb
    y = y0 + (y1 - y0) * (k + 1) / n
    out = g.copy()
    if k < n - 1:
        ImageDraw.Draw(out).rectangle((0, round(y), g.width, g.height), fill=(0, 0, 0, 0))
    bx = x1 - 4 if k % 2 == 0 else x0 + 4
    return out, (bx, y)


def brush(layer, x, y):
    """筆: 穂先(墨)が (x, y) にあり、柄が右上へのびる。"""
    d = ImageDraw.Draw(layer)
    tx, ty = x + 30, y - 34
    d.line([(x + 6, y - 8), (tx, ty)], fill=soft.LINE, width=10)
    d.line([(x + 6, y - 8), (tx, ty)], fill="#B07A4A", width=6)
    d.polygon([(x, y), (x + 3, y - 14), (x + 12, y - 10)], fill=INK_BLACK, outline="white")


def seal(layer, cx, cy, s, ch="未"):
    """朱色のはんこ(四角に白抜きの字)。"""
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), radius=3, fill=SHU, outline="white",
                        width=2)
    font = ImageFont.truetype(str(BRUSH_FONT), round(s * 0.78))
    d.text((cx, cy + 1), ch, font=font, anchor="mm", fill=CARD)


def card05(icon):
    """05 謹賀新年: 縦書きの4文字を、1文字4コマずつ筆を左右に振りながら書く → ひつじが出て、はんこを押す。"""
    text, size, cx, top, step_y = "謹賀新年", 50, 176, 26, 48
    glyphs = [glyph(ch, size) for ch in text]

    def draw(n_full, partial=None, show_icon=None, seal_s=None, brush_at=None, pops=False):
        im = card_base()
        for k in range(len(text)):
            g = glyphs[k]
            y = top + k * step_y
            if k < n_full:
                im.alpha_composite(g, (round(cx - g.width / 2), round(y)))
            elif k == n_full and partial is not None:
                pg, (bx, by) = reveal(g, partial)
                gx = round(cx - g.width / 2)
                im.alpha_composite(pg, (gx, round(y)))
                brush_at = (gx + bx, y + by)
        d = ImageDraw.Draw(im)
        d.ellipse((94, 28, 106, 40), fill="#F49CB4", outline=soft.LINE, width=2)  # 左上の小さな梅
        d.ellipse((98, 32, 102, 36), fill="#FFD24D")
        if show_icon:
            ic = icon.resize((round(icon.width * show_icon), round(icon.height * show_icon)), Image.LANCZOS)
            im.alpha_composite(ic, (round(114 - ic.width / 2), round(246 - ic.height)))
        if seal_s:
            seal(im, 214, 228, seal_s)
        if pops:
            winter.draw_marks2(im, [("spark", 140, 190, 9), ("spark", 226, 196, 7)], 0, 0)
        if brush_at:
            brush(im, *brush_at)
        return im

    frames = [draw(4, show_icon=1.0, seal_s=26)]                       # 0: 完成形
    frames.append(draw(0, brush_at=(cx + 2, top + 30)))                 # 1: 何も書いていない
    for i in range(16):                                                # 2〜17: 1文字4コマ、筆を左右に振りながら下へ
        frames.append(draw(i // 4, partial=i % 4))
    frames.append(draw(4, show_icon=1.2, seal_s=36, pops=True))         # 18: ひつじがぽん、はんこを押す
    frames.append(draw(4, show_icon=1.0, seal_s=26))                   # 19: 完成形
    return frames


CARDS = {"05": card05}


def card_sheet(frames, path, cols=5, rows=4):
    sheet = Image.new("RGBA", (CW * cols, CH * rows), inko.BG)
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, ((i % cols) * CW, (i // cols) * CH))
    sheet.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stamp", choices=sorted(list(STAMPS) + list(CARDS)))
    ap.add_argument("--png", required=True)
    a = ap.parse_args()
    if a.stamp in CARDS:
        frames = CARDS[a.stamp](sheep_icon(56))
        card_sheet(frames, a.png)
        print(f"シート: {a.png}(年賀状 {len(frames)}コマ, 5x4)")
        return
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
