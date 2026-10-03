#!/usr/bin/env python3
"""LINEスタンプ画像ジェネレーター.

stamps.json の内容から、LINE Creators Market の提出仕様に沿った
スタンプ画像 (01.png ...)、メイン画像 (main.png)、タブ画像 (tab.png)
を生成し、提出用 ZIP にまとめる。

使い方:
    python3 make_stamps.py                  # stamps.json から生成
    python3 make_stamps.py -c my.json       # 別の設定ファイルを使う
    python3 make_stamps.py --check out/     # 既存フォルダを仕様チェックだけする
"""

import argparse
import json
import math
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

# --- LINE スタンプ仕様 -------------------------------------------------------
STAMP_MAX = (370, 320)   # スタンプ画像の最大サイズ (幅, 高さ)
MAIN_SIZE = (240, 240)   # メイン画像
TAB_SIZE = (96, 74)      # トークルームタブ画像
MARGIN = 10              # 画像の周囲に必要な余白 (px)
MAX_BYTES = 1024 * 1024  # 1 画像あたり 1MB 以下
ALLOWED_COUNTS = (8, 16, 24, 32, 40)

SCALE = 4  # 高解像度で描いて縮小することでアンチエイリアスをかける

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def load_font(path, size):
    paths = [path] if path else []
    for p in paths + FONT_CANDIDATES:
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    sys.exit("日本語フォントが見つかりません。stamps.json の \"font\" にフォントファイルのパスを指定してください。")


# --- キャラクター描画 --------------------------------------------------------
def draw_character(draw, cx, cy, r, expression, body, outline, cheek):
    """丸いおもち型キャラクターを描く。(cx, cy) は中心、r は半径。"""
    lw = max(1, int(r * 0.06))
    ink = hex_rgb(outline)

    # 体 (少し横長の楕円) と 小さな耳
    for ex in (-1, 1):
        ear = [cx + ex * r * 0.55 - r * 0.22, cy - r * 0.95,
               cx + ex * r * 0.55 + r * 0.22, cy - r * 0.55]
        draw.ellipse(ear, fill=hex_rgb(body), outline=ink, width=lw)
    draw.ellipse([cx - r * 1.1, cy - r * 0.85, cx + r * 1.1, cy + r * 0.85],
                 fill=hex_rgb(body), outline=ink, width=lw)

    ey = cy - r * 0.1           # 目の高さ
    ex_off = r * 0.42           # 目の左右オフセット
    er = r * 0.1                # 目の大きさ
    my = cy + r * 0.25          # 口の高さ

    def dot_eyes(size=er):
        for e in (-1, 1):
            x = cx + e * ex_off
            draw.ellipse([x - size, ey - size, x + size, ey + size], fill=ink)

    def arc_eyes(up=True):
        for e in (-1, 1):
            x = cx + e * ex_off
            box = [x - er * 1.6, ey - er * 1.2, x + er * 1.6, ey + er * 1.6]
            draw.arc(box, 200 if up else 20, 340 if up else 160, fill=ink, width=lw)

    def cheeks():
        for e in (-1, 1):
            x = cx + e * r * 0.72
            draw.ellipse([x - r * 0.16, my - r * 0.12, x + r * 0.16, my + r * 0.06],
                         fill=hex_rgb(cheek))

    def mouth_smile(w=0.22):
        draw.arc([cx - r * w, my - r * 0.18, cx + r * w, my + r * 0.12], 20, 160, fill=ink, width=lw)

    def mouth_open(w=0.16, h=0.22):
        draw.ellipse([cx - r * w, my - r * 0.08, cx + r * w, my - r * 0.08 + r * h],
                     fill=hex_rgb("#E5545B"), outline=ink, width=lw)

    def heart(x, y, size, color):
        c = hex_rgb(color)
        draw.ellipse([x - size, y - size * 0.6, x, y + size * 0.4], fill=c)
        draw.ellipse([x, y - size * 0.6, x + size, y + size * 0.4], fill=c)
        draw.polygon([(x - size * 0.97, y - size * 0.0), (x + size * 0.97, y - size * 0.0),
                      (x, y + size * 1.05)], fill=c)

    if expression == "smile":
        dot_eyes(); cheeks(); mouth_smile()
    elif expression == "happy":
        arc_eyes(up=True); cheeks(); mouth_open(0.2, 0.26)
    elif expression == "love":
        for e in (-1, 1):
            heart(cx + e * ex_off, ey - er * 0.6, er * 1.6, "#FF4F7B")
        cheeks(); mouth_smile()
    elif expression == "sad":
        dot_eyes(er * 0.9)
        for e in (-1, 1):  # 下がり眉
            x = cx + e * ex_off
            draw.line([x - e * er * 2, ey - er * 2.6, x + e * er * 1.4, ey - er * 1.8], fill=ink, width=lw)
        draw.arc([cx - r * 0.2, my, cx + r * 0.2, my + r * 0.3], 200, 340, fill=ink, width=lw)
        tx = cx + ex_off + er * 0.4  # 涙
        draw.polygon([(tx, ey + er), (tx - er * 0.9, ey + er * 3.2), (tx + er * 0.9, ey + er * 3.2)],
                     fill=hex_rgb("#6EC6FF"))
        draw.ellipse([tx - er * 0.9, ey + er * 2.4, tx + er * 0.9, ey + er * 4.0], fill=hex_rgb("#6EC6FF"))
    elif expression == "angry":
        dot_eyes()
        for e in (-1, 1):  # つり眉
            x = cx + e * ex_off
            draw.line([x + e * er * 2, ey - er * 2.8, x - e * er * 1.4, ey - er * 1.6], fill=ink, width=lw)
        draw.arc([cx - r * 0.2, my, cx + r * 0.2, my + r * 0.3], 200, 340, fill=ink, width=lw)
        # 怒りマーク (中心に向かって膨らむ 4 本の弧)
        ax, ay, a = cx + r * 0.72, cy - r * 0.5, r * 0.12
        red = hex_rgb("#E53935")
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            ox, oy = ax + dx * a * 1.6, ay + dy * a * 1.6
            mid = math.degrees(math.atan2(-dy, -dx))
            draw.arc([ox - a, oy - a, ox + a, oy + a],
                     mid - 50, mid + 50, fill=red, width=int(lw * 1.6))
    elif expression == "surprised":
        for e in (-1, 1):
            x = cx + e * ex_off
            draw.ellipse([x - er * 1.5, ey - er * 1.8, x + er * 1.5, ey + er * 1.8],
                         fill=(255, 255, 255, 255), outline=ink, width=lw)
            draw.ellipse([x - er * 0.7, ey - er * 0.7, x + er * 0.7, ey + er * 0.7], fill=ink)
        draw.ellipse([cx - r * 0.1, my - r * 0.02, cx + r * 0.1, my + r * 0.22], outline=ink, width=lw)
    elif expression == "sleepy":
        for e in (-1, 1):
            x = cx + e * ex_off
            draw.line([x - er * 1.5, ey, x + er * 1.5, ey], fill=ink, width=lw)
        cheeks()
        draw.ellipse([cx - r * 0.07, my - r * 0.02, cx + r * 0.07, my + r * 0.1], outline=ink, width=lw)
    elif expression == "wink":
        x = cx - ex_off
        draw.ellipse([x - er, ey - er, x + er, ey + er], fill=ink)
        x = cx + ex_off
        draw.line([x - er * 1.5, ey - er * 0.9, x + er * 1.2, ey], fill=ink, width=lw)
        draw.line([x - er * 1.5, ey + er * 0.9, x + er * 1.2, ey], fill=ink, width=lw)
        cheeks(); mouth_open(0.14, 0.2)
    elif expression == "think":
        dot_eyes()
        draw.line([cx - r * 0.15, my + r * 0.05, cx + r * 0.15, my + r * 0.05], fill=ink, width=lw)
        # はてなマーク代わりの吹き出し点
        for i, k in enumerate((0.06, 0.09, 0.13)):
            x = cx + r * (0.95 + i * 0.22)
            y = cy - r * (0.55 + i * 0.28)
            draw.ellipse([x - r * k, y - r * k, x + r * k, y + r * k],
                         fill=(255, 255, 255, 255), outline=ink, width=max(1, lw // 2))
    else:
        raise ValueError(f"未知の表情です: {expression}")


def draw_outlined_text(img, xy, text, font, fill, stroke, stroke_width):
    """縁取り文字を描く。字の内側の小さなすき間も縁色で埋める。"""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=font, fill=255, anchor="mm",
                              stroke_width=stroke_width, stroke_fill=255, align="center")
    # 外側から塗りつぶして、外側に繋がっていない穴 (す・み の輪の中など) を縁取りに含める
    solid = mask.point(lambda v: 255 if v >= 128 else 0)
    ImageDraw.floodfill(solid, (0, 0), 128)
    inside = solid.point(lambda v: 0 if v == 128 else 255)
    mask = ImageChops.lighter(mask, inside)
    img.paste(Image.new("RGBA", img.size, hex_rgb(stroke)), (0, 0), mask)
    ImageDraw.Draw(img).text(xy, text, font=font, fill=hex_rgb(fill), anchor="mm", align="center")


def fit_font(draw, text, font_path, max_w, max_h, start):
    size = start
    while size > 8:
        font = load_font(font_path, size)
        box = draw.multiline_textbbox((0, 0), text, font=font, anchor="mm",
                                      stroke_width=int(size * 0.16), align="center")
        if box[2] - box[0] <= max_w and box[3] - box[1] <= max_h:
            return font
        size -= 2 * SCALE
    return load_font(font_path, size)


def trim_and_fit(img, max_size, margin):
    """透明部分を切り落とし、余白を付けて最大サイズ以内・偶数ピクセルに収める。"""
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    inner_w, inner_h = max_size[0] - margin * 2, max_size[1] - margin * 2
    ratio = min(inner_w / img.width, inner_h / img.height, 1.0)
    img = img.resize((max(1, round(img.width * ratio)), max(1, round(img.height * ratio))), Image.LANCZOS)
    w = img.width + margin * 2
    h = img.height + margin * 2
    w += w % 2
    h += h % 2
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2), img)
    return canvas


def render_stamp(item, cfg):
    """1 枚のスタンプを高解像度で描画して返す (余白・リサイズ前)。"""
    s = SCALE
    W, H = STAMP_MAX[0] * s, STAMP_MAX[1] * s
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    text = item.get("text", "")
    style = {**cfg.get("text_style", {}), **item.get("text_style", {})}

    if item.get("image"):
        # 自作イラストを使う場合
        art = Image.open(Path(cfg["_base"]) / item["image"]).convert("RGBA")
        area_h = H * (0.72 if text else 0.95)
        ratio = min(W * 0.95 / art.width, area_h / art.height)
        art = art.resize((int(art.width * ratio), int(art.height * ratio)), Image.LANCZOS)
        img.paste(art, ((W - art.width) // 2, int(H * 0.02)), art)
    else:
        ch = cfg.get("character", {})
        r = H * (0.27 if text else 0.36)
        cy = H * (0.38 if text else 0.5)
        draw_character(draw, W / 2, cy, r, item.get("expression", "smile"),
                       ch.get("body", "#FFF4E0"), ch.get("outline", "#4A3B32"),
                       ch.get("cheek", "#FFB3B3"))

    if text:
        font = fit_font(draw, text, cfg.get("font"), W * 0.92, H * 0.3, 64 * s)
        sw = max(2, int(font.size * 0.16))
        draw_outlined_text(img, (W / 2, H * 0.83), text, font,
                           style.get("color", "#FF7A45"), style.get("stroke", "#FFFFFF"), sw)
    return img


# --- 仕様チェック ------------------------------------------------------------
def check_image(path, kind):
    errors = []
    img = Image.open(path)
    w, h = img.size
    if kind == "stamp":
        if w > STAMP_MAX[0] or h > STAMP_MAX[1]:
            errors.append(f"サイズ {w}x{h} が上限 {STAMP_MAX[0]}x{STAMP_MAX[1]} を超えています")
        if w % 2 or h % 2:
            errors.append(f"サイズ {w}x{h} は縦横とも偶数にしてください")
    else:
        expected = MAIN_SIZE if kind == "main" else TAB_SIZE
        if (w, h) != expected:
            errors.append(f"サイズ {w}x{h} は {expected[0]}x{expected[1]} である必要があります")
    if img.format != "PNG":
        errors.append("PNG 形式ではありません")
    if img.mode != "RGBA":
        errors.append("背景透過 (RGBA) になっていません")
    elif img.getpixel((0, 0))[3] != 0:
        errors.append("左上の画素が透明ではありません (背景透過を確認してください)")
    if path.stat().st_size > MAX_BYTES:
        errors.append("ファイルサイズが 1MB を超えています")
    return errors


def check_dir(out):
    out = Path(out)
    stamps = sorted(p for p in out.glob("[0-9][0-9].png"))
    problems = []
    if len(stamps) not in ALLOWED_COUNTS:
        problems.append(f"スタンプ枚数 {len(stamps)} 枚: {ALLOWED_COUNTS} のいずれかにしてください")
    for p, kind in [(p, "stamp") for p in stamps] + [(out / "main.png", "main"), (out / "tab.png", "tab")]:
        if not p.exists():
            problems.append(f"{p.name}: ファイルがありません")
            continue
        problems += [f"{p.name}: {e}" for e in check_image(p, kind)]
    return stamps, problems


# --- メイン処理 --------------------------------------------------------------
def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["_base"] = cfg_path.parent
    out = cfg_path.parent / cfg.get("output", "output")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    items = cfg["stamps"]
    if len(items) not in ALLOWED_COUNTS:
        print(f"⚠ スタンプは {len(items)} 枚です。提出には {ALLOWED_COUNTS} 枚のいずれかが必要です。")

    rendered = []
    for i, item in enumerate(items, 1):
        big = render_stamp(item, cfg)
        small = big.resize((STAMP_MAX[0], STAMP_MAX[1]), Image.LANCZOS)
        stamp = trim_and_fit(small, STAMP_MAX, MARGIN)
        stamp.save(out / f"{i:02d}.png", optimize=True)
        rendered.append(big)
        print(f"  {i:02d}.png  {stamp.width}x{stamp.height}  {item.get('text', '')!r}")

    # メイン・タブ画像は指定スタンプ (既定は 1 枚目) の文字なし版から作る
    main_idx = cfg.get("main_stamp", 1) - 1
    base_item = {k: v for k, v in items[main_idx].items() if k != "text"}
    base = render_stamp(base_item, cfg).resize(STAMP_MAX, Image.LANCZOS)
    for name, size, margin in (("main.png", MAIN_SIZE, MARGIN), ("tab.png", TAB_SIZE, 2)):
        fitted = trim_and_fit(base, size, margin)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2), fitted)
        canvas.save(out / name, optimize=True)

    # 一覧プレビュー (提出物ではなく確認用)
    make_preview(out, len(items))

    stamps, problems = check_dir(out)
    zip_path = out.parent / f"{cfg.get('name', 'line_stamp')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in stamps + [out / "main.png", out / "tab.png"]:
            z.write(p, p.name)
    report(problems)
    print(f"\n✅ 出力: {out}/  提出用 ZIP: {zip_path}")


def make_preview(out, count):
    cols = 4
    rows = math.ceil(count / cols)
    cell = (STAMP_MAX[0] + 20, STAMP_MAX[1] + 20)
    sheet = Image.new("RGB", (cell[0] * cols, cell[1] * rows), (140, 171, 216))  # LINE のトーク背景色風
    for i in range(count):
        img = Image.open(out / f"{i + 1:02d}.png")
        x = (i % cols) * cell[0] + (cell[0] - img.width) // 2
        y = (i // cols) * cell[1] + (cell[1] - img.height) // 2
        sheet.paste(img, (x, y), img)
    sheet.save(out.parent / "preview.png")


def report(problems):
    if problems:
        print("\n❌ 仕様チェックで問題が見つかりました:")
        for p in problems:
            print("  -", p)
    else:
        print("\n✔ 仕様チェック OK (サイズ・偶数px・透過・1MB以下・枚数)")


def main():
    ap = argparse.ArgumentParser(description="LINEスタンプ画像ジェネレーター")
    ap.add_argument("-c", "--config", default="stamps.json", help="設定ファイル (既定: stamps.json)")
    ap.add_argument("--check", metavar="DIR", help="指定フォルダの画像が仕様を満たすかだけ確認する")
    args = ap.parse_args()
    if args.check:
        _, problems = check_dir(args.check)
        report(problems)
        sys.exit(1 if problems else 0)
    build(args.config)


if __name__ == "__main__":
    main()
