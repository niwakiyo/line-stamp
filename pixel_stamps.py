#!/usr/bin/env python3
"""ドット絵 RPG 風 LINE スタンプジェネレーター.

sprites.py のオリジナルキャラクターと、RPG のメッセージウィンドウ風の
吹き出しを組み合わせてスタンプを作る。

使い方:
    python3 pixel_stamps.py                     # pixel_stamps.json から生成
    python3 pixel_stamps.py -c other.json
"""

import argparse
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from make_stamps import MAIN_SIZE, STAMP_MAX, TAB_SIZE, check_dir, make_preview, report
from sprites import CHARACTERS, EFFECTS, EXPRESSIONS, EYES, MOUTHS, PALETTE

FONT_CANDIDATES = [
    Path(__file__).parent / "fonts" / "unifont_jp.otf",
    Path("/usr/share/fonts/opentype/unifont/unifont_jp.otf"),
]

W, H = STAMP_MAX
SPRITE_SCALE = 9          # 16x20 ドット → 144x180 px
SPRITE_X = 34             # キャラを左に置くときの x 座標
WINDOW = (10, 196, W - 10, H - 10)  # メッセージウィンドウの位置
PX = 4                    # ウィンドウ枠の 1 ドットの大きさ
PANEL_MIN_W = 160         # ステータスウィンドウの最小幅
EFFECT_SCALE = 7          # エフェクトの拡大率
PANEL_PAD = 3 * PX + 8    # ミニウィンドウの内側の余白


def set_layout(size, window, sprite_scale, sprite_x=34, panel_min_w=160, effect_scale=7,
               panel_pad=3 * PX + 8):
    """画像サイズと配置を切り替える (動くスタンプは 320x270 なので小さめの配置を使う)。"""
    global W, H, WINDOW, SPRITE_SCALE, SPRITE_X, PANEL_MIN_W, EFFECT_SCALE, PANEL_PAD
    W, H = size
    WINDOW, SPRITE_SCALE, SPRITE_X, PANEL_MIN_W = window, sprite_scale, sprite_x, panel_min_w
    EFFECT_SCALE, PANEL_PAD = effect_scale, panel_pad


def rgba(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def paint(grid, x, y, pattern):
    """grid (行ごとの文字リスト) の (x, y) を中心に pattern を上書きする。空白はそのまま。"""
    ph, pw = len(pattern), len(pattern[0])
    for dy, row in enumerate(pattern):
        for dx, c in enumerate(row):
            if c != " ":
                grid[y + dy][x - pw // 2 + dx] = c
    return ph


def sprite_image(char_id, expression, flip=False):
    ch = CHARACTERS[char_id]
    grid = [list(row) for row in ch["pixels"]]
    left, right, mouth, extras = EXPRESSIONS[expression]
    extras = ["tears"] if extras is True else (extras or [])
    (lx, ey), (rx, _) = ch["face"]["eyes"]
    paint(grid, lx, ey, EYES[left])
    paint(grid, rx, ey, EYES[right])
    mx, my = ch["face"]["mouth"]
    paint(grid, mx + 1, my, MOUTHS[mouth])
    if "tears" in extras:
        for x in (lx, rx):
            grid[ey + 2][x] = "L"
            grid[ey + 3][x] = "L"
    if "gloom" in extras:  # おでこに縦線 (どんより)
        for y in (ey - 2, ey - 1):
            for x in range(len(grid[y])):
                if grid[y][x] == "S" and x % 2:
                    grid[y][x] = "Q"
    colors = {**PALETTE, "Q": "#6A6AA8", **ch["colors"]}
    return pixels_to_image(["".join(r) for r in grid], colors, flip)


def pixels_to_image(rows, colors=PALETTE, flip=False):
    img = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != ".":
                img.putpixel((x, y), rgba(colors[c]))
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


def scaled(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def load_font():
    for p in FONT_CANDIDATES:
        if p.exists():
            return ImageFont.truetype(str(p), 16)
    raise SystemExit("ドット絵フォント (unifont_jp.otf) が見つかりません。fonts/ に置いてください。")


def pixel_text(text, color, shadow, upto=None):
    """16px のドットフォントで文字を描き、影付きの 1 倍画像を返す。

    upto を指定すると先頭から upto 文字だけ描く (1 文字ずつ表示するアニメ用)。
    配置は全文を描いたときと同じなので、途中でも文字の位置がずれない。
    """
    font = load_font()
    lines = text.split("\n")
    widths = [int(font.getlength(line)) for line in lines]
    img = Image.new("RGBA", (max(widths) + 2, 17 * len(lines) + 1), (0, 0, 0, 0))
    remaining = len(text.replace("\n", "")) if upto is None else upto
    for i, line in enumerate(lines):
        x = (img.width - 2 - widths[i]) // 2
        line, remaining = line[:max(0, remaining)], remaining - len(line)
        if not line:
            continue
        for off, col in (((1, 1), shadow), ((0, 0), color)):
            mask = Image.new("L", img.size, 0)
            md = ImageDraw.Draw(mask)
            for bold in (0, 1):  # 横に 1 ドットずらして重ね、太字にする
                md.text((x + off[0] + bold, i * 17 + off[1]), line, font=font, fill=255)
            mask = mask.point(lambda v: 255 if v >= 128 else 0)  # ドットをくっきりさせる
            img.paste(Image.new("RGBA", img.size, rgba(col)), (0, 0), mask)
    return img


def draw_window(img, style, box=None):
    """RPG 風のメッセージウィンドウ (青いグラデーション + 白枠) を描く。"""
    x0, y0, x1, y1 = box or WINDOW
    d = ImageDraw.Draw(img)
    top, bottom = rgba(style.get("top", "#3B4FD8")), rgba(style.get("bottom", "#141A6B"))
    # 角を 1 ドット欠いた外枠 (輪郭 → 白 → 輪郭 → 中身)
    layers = [("#1B1B2F", 0), ("#FFFFFF", 1), ("#1B1B2F", 2)]
    for color, i in layers:
        o = i * PX
        d.rectangle([x0 + o + PX, y0 + o, x1 - o - PX, y1 - o], fill=rgba(color))
        d.rectangle([x0 + o, y0 + o + PX, x1 - o, y1 - o - PX], fill=rgba(color))
    o = 3 * PX
    steps = (y1 - y0 - 2 * o) // PX
    for i in range(steps):
        t = i / max(1, steps - 1)
        c = tuple(round(top[k] + (bottom[k] - top[k]) * t) for k in range(3)) + (255,)
        y = y0 + o + i * PX
        d.rectangle([x0 + o, y, x1 - o, min(y + PX - 1, y1 - o)], fill=c)


def draw_panel(img, panel, style):
    """キャラの右側に、ステータス (ゲージ付き) かコマンド選択のミニウィンドウを描く。"""
    color, shadow = style.get("text", "#FFFFFF"), style.get("shadow", "#0A0D3A")
    k = 2
    rows = []
    if panel["type"] == "status":
        for r in panel["rows"]:  # 1 行目に名前、2 行目に数値 (右寄せ)、その下にゲージ
            value = f"{r['value']}/{r['max']}" if r.get("show_max", True) else str(r["value"])
            rows.append(("text", scaled(pixel_text(r["label"], color, shadow), k), None))
            rows.append(("gauge", scaled(pixel_text(value, color, shadow), k), r))
    else:  # menu
        for i, opt in enumerate(panel["options"]):  # カーソル (▶) は三角形で別に描く
            rows.append(("menu", scaled(pixel_text(opt, color, shadow), k), i == panel.get("cursor", 0)))
    bar_h = 14
    heights = [im.height + (bar_h + 6 if kind == "gauge" else 0) for kind, im, _ in rows]
    gap = 2 if panel["type"] == "status" else 6
    pad = PANEL_PAD
    cur_w = 14 if panel["type"] == "menu" else 0
    pw = max(im.width for _, im, _ in rows) + pad * 2 + cur_w
    pw = max(pw, panel.get("min_width", PANEL_MIN_W if panel["type"] == "status" else 0))
    ph = sum(heights) + gap * (len(rows) - 1) + pad * 2
    x1 = W - 10
    x0 = x1 - pw
    y0 = max(10, (WINDOW[1] - ph) // 2 + panel.get("dy", 0))
    draw_window(img, style, (x0, y0, x1, y0 + ph))
    d = ImageDraw.Draw(img)
    y = y0 + pad
    for (kind, im, r), h in zip(rows, heights):
        tx = {"text": x0 + pad, "menu": x0 + pad + cur_w}.get(kind, x1 - pad - im.width)
        img.alpha_composite(im, (tx, y))
        if kind == "menu" and r:
            cy = y + im.height // 2
            d.polygon([(x0 + pad, cy - 7), (x0 + pad + 8, cy), (x0 + pad, cy + 7)], fill=rgba(color))
        if kind == "gauge":
            by = y + im.height + 2
            bx0, bx1 = x0 + pad, x1 - pad
            d.rectangle([bx0, by, bx1, by + bar_h], fill=rgba("#FFFFFF"))
            d.rectangle([bx0 + 2, by + 2, bx1 - 2, by + bar_h - 2], fill=rgba("#1B1B2F"))
            ratio = max(0.0, min(1.0, r["value"] / r["max"]))
            fill_w = round((bx1 - bx0 - 4) * ratio)
            if r["value"] > 0:
                fill_w = max(fill_w, 4)  # 少しでも残っていたら見えるように
            if fill_w:
                d.rectangle([bx0 + 2, by + 2, bx0 + 2 + fill_w - 1, by + bar_h - 2],
                            fill=rgba(r.get("color", "#4CD964")))
        y += h + gap


def render(item, cfg):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    style = cfg.get("window", {})
    draw_window(img, style)

    # 文字 (ウィンドウ内に収まる最大の整数倍で拡大)
    x0, y0, x1, y1 = WINDOW
    inner_w, inner_h = x1 - x0 - 6 * PX - 8, y1 - y0 - 6 * PX - 8
    text = pixel_text(item["text"], style.get("text", "#FFFFFF"), style.get("shadow", "#0A0D3A"),
                      item.get("_chars"))
    k = max(1, min(inner_w // text.width, inner_h // text.height, 4))
    text = scaled(text, k)
    img.alpha_composite(text, ((x0 + x1 - text.width) // 2, (y0 + y1 - text.height) // 2 + 2))
    if item.get("_arrow"):  # 文字送りの ▼ マーク
        ax, ay = x1 - 3 * PX - 18, y1 - 3 * PX - 12
        ImageDraw.Draw(img).polygon([(ax, ay), (ax + 12, ay), (ax + 6, ay + 7)], fill=rgba("#FFFFFF"))

    # キャラクター (ウィンドウの上に立たせる)
    sp = sprite_image(item["chara"], item.get("expression", "normal"), item.get("flip", False))
    if item.get("pose") == "down":  # 倒れている (頭が左)
        sp = sp.rotate(90, expand=True)
    sp = scaled(sp, SPRITE_SCALE)
    sx = {"left": SPRITE_X, "center": (W - sp.width) // 2,
          "right": W - sp.width - SPRITE_X}[item.get("pos", "left")]
    sy = y0 - sp.height + 4 * PX
    sy = max(sy, 10)
    sx += item.get("_dx", 0)
    sy += item.get("_dy", 0)
    img.alpha_composite(sp, (sx, sy))

    # エフェクト
    for eff in item.get("effects", []):
        name = eff["name"] if isinstance(eff, dict) else eff
        if isinstance(eff, dict) and eff.get("hidden"):
            continue
        e = scaled(pixels_to_image(EFFECTS[name]), eff.get("scale", EFFECT_SCALE) if isinstance(eff, dict)
                   else EFFECT_SCALE)
        if name == "grass":
            ex, ey = x1 - e.width - 20, y0 - e.height + PX
        elif name == "crown":
            ex, ey = sx + (sp.width - e.width) // 2, max(10, sy - e.height + 8)
        else:
            ex, ey = sx + sp.width + 8, sy + 8
        if isinstance(eff, dict):
            ex += eff.get("dx", 0)
            ey += eff.get("dy", 0)
        img.alpha_composite(e, (ex, ey))

    if item.get("panel"):
        draw_panel(img, item["panel"], style)
    return img


def fit_square(img, size, margin):
    """透明部分を切り落として、指定サイズの中央に整数倍のドットのまま収める。"""
    img = img.crop(img.getbbox())
    k = max(1, min((size[0] - margin * 2) // img.width, (size[1] - margin * 2) // img.height))
    img = scaled(img, k) if k > 1 else img
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return canvas


def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = cfg_path.parent / cfg.get("output", "output_pixel")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    for i, item in enumerate(cfg["stamps"], 1):
        render(item, cfg).save(out / f"{i:02d}.png", optimize=True)
        print(f"  {i:02d}.png  {CHARACTERS[item['chara']]['name']:<3} {item['text']!r}")

    # メイン画像: 4 人を 2 人ずつ 2 段に並べる / タブ画像: マスコット
    party = [sprite_image(c, cfg.get("main_expression", "smile")) for c in cfg.get("main_party", ["yuu", "mira", "kai", "mofu"])]
    cols = 2 if len(party) > 2 else len(party)
    rows = -(-len(party) // cols)
    cw, chh = max(p.width for p in party) + 1, max(p.height for p in party) + 1
    group = Image.new("RGBA", (cw * cols, chh * rows), (0, 0, 0, 0))
    for i, p in enumerate(party):
        group.alpha_composite(p, ((i % cols) * cw, (i // cols) * chh + chh - 1 - p.height))
    fit_square(group, MAIN_SIZE, 10).save(out / "main.png", optimize=True)
    fit_square(sprite_image(cfg.get("tab_chara", "mofu"), cfg.get("tab_expression", "happy")), TAB_SIZE, 4).save(out / "tab.png", optimize=True)

    make_preview(out, len(cfg["stamps"]), cfg_path.parent / cfg.get("preview", "preview_pixel.png"))
    stamps, problems = check_dir(out)
    zip_path = cfg_path.parent / f"{cfg.get('name', 'pixel_stamp')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in stamps + [out / "main.png", out / "tab.png"]:
            z.write(p, p.name)
    report(problems)
    print(f"\n✅ 出力: {out}/  提出用 ZIP: {zip_path}")


def main():
    ap = argparse.ArgumentParser(description="ドット絵 RPG 風 LINE スタンプジェネレーター")
    ap.add_argument("-c", "--config", default="pixel_stamps.json")
    build(ap.parse_args().config)


if __name__ == "__main__":
    main()
