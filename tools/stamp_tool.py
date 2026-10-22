#!/usr/bin/env python3
"""LINEスタンプ用ツール。

  anim   : コマ割りされた1枚の画像(スプライトシート) → APNG(申請用) + GIF(プレビュー)
  extras : 1コマ目などから メイン画像(240x240) / タブ画像(96x74) を作成
  check  : 画像がLINEクリエイターズマーケットの規定を満たすか検査

Canva無料プランは透過PNGを書き出せないため、背景は単色(既定: 四隅の色を自動検出)で
塗ってもらい、このツールで透過に変換する。
"""
import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence

# LINE Creators Market 規定 (アニメーションスタンプ)
ANIM_MAX_W, ANIM_MAX_H, ANIM_MIN_SIDE = 320, 270, 270
ANIM_MIN_FRAMES, ANIM_MAX_FRAMES = 5, 20
ANIM_MAX_SECONDS = 4
ANIM_MAX_BYTES = 300 * 1000  # 「300KB」を厳しめに10進で解釈
# 静止画スタンプ
STATIC_MAX_W, STATIC_MAX_H = 370, 320
STATIC_MAX_BYTES = 1000 * 1000
MAIN_SIZE, TAB_SIZE = (240, 240), (96, 74)


def split_sheet(sheet, cols, rows, gutter):
    w = (sheet.width - gutter * (cols - 1)) // cols
    h = (sheet.height - gutter * (rows - 1)) // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            x, y = c * (w + gutter), r * (h + gutter)
            frames.append(sheet.crop((x, y, x + w, y + h)))
    return frames


def detect_key_color(img):
    px = img.convert("RGB")
    corners = [px.getpixel(p) for p in
               [(0, 0), (img.width - 1, 0), (0, img.height - 1), (img.width - 1, img.height - 1)]]
    return max(set(corners), key=corners.count)


def parse_color(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def key_out(img, color, tol):
    """単色背景を透過にする。tol は RGB 各成分の許容差。"""
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    masks = [band.point(lambda v, c=c: 255 if abs(v - c) <= tol else 0)
             for band, c in zip((r, g, b), color)]
    bg = ImageChops.multiply(ImageChops.multiply(masks[0], masks[1]), masks[2])
    alpha = ImageChops.darker(a, ImageChops.invert(bg))
    if color[1] > max(color[0], color[2]):
        # グリーンバックの色かぶり除去: 輪郭のなじみ部分に残る緑を G<=max(R,B) に抑える
        g = ImageChops.darker(g, ImageChops.lighter(r, b))
    img = Image.merge("RGBA", (r, g, b, alpha))
    return img


def fit(img, max_w, max_h, min_side=0):
    """縦横比を保って max_w x max_h に収め、透明で余白を付ける。"""
    scale = min(max_w / img.width, max_h / img.height)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    cw, ch = max_w, max_h
    if min_side and max(nw, nh) >= min_side:
        cw, ch = nw, nh  # すでに規定を満たすなら余白なし
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(img, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


def encode_apng(frames, duration_ms, loops, colors=None):
    out = []
    for f in frames:
        out.append(f.quantize(colors, method=Image.Quantize.FASTOCTREE).convert("RGBA") if colors else f)
    buf = io.BytesIO()
    out[0].save(buf, format="PNG", save_all=True, append_images=out[1:],
                duration=duration_ms, loop=loops, disposal=1, blend=0, optimize=True)
    return buf.getvalue()


def cmd_anim(a):
    sheet = Image.open(a.sheet)
    frames = split_sheet(sheet, a.cols, a.rows, a.gutter)
    if a.frames:
        frames = frames[:a.frames]
    if not ANIM_MIN_FRAMES <= len(frames) <= ANIM_MAX_FRAMES:
        sys.exit(f"コマ数 {len(frames)} は規定外です({ANIM_MIN_FRAMES}〜{ANIM_MAX_FRAMES})")
    if a.key != "none":
        color = detect_key_color(frames[0]) if a.key == "auto" else parse_color(a.key)
        print(f"背景色 #{color[0]:02x}{color[1]:02x}{color[2]:02x} を透過にします (許容差 {a.tol})")
        frames = [key_out(f, color, a.tol) for f in frames]
    frames = [fit(f.convert("RGBA"), ANIM_MAX_W, ANIM_MAX_H, ANIM_MIN_SIDE) for f in frames]

    # 1ループの再生時間は整数秒にそろえる(ループ数 x 再生時間 <= 4秒)
    if a.seconds * a.loops > ANIM_MAX_SECONDS:
        sys.exit(f"再生時間 {a.seconds}秒 x {a.loops}ループ が {ANIM_MAX_SECONDS}秒を超えます")
    # 割り切れないときはコマごとに 1ms ずつ配って、合計をちょうど整数秒にする
    total_ms, n = a.seconds * 1000, len(frames)
    duration = [total_ms // n + (1 if i < total_ms % n else 0) for i in range(n)]

    data = encode_apng(frames, duration, a.loops)
    for colors in (256, 128, 64, 32):
        if len(data) <= ANIM_MAX_BYTES:
            break
        print(f"{len(data) // 1024}KB > 300KB のため {colors}色に減色します")
        data = encode_apng(frames, duration, a.loops, colors)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    gif = out.with_suffix(".gif")
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=duration,
                   loop=0, disposal=2, transparency=0)
    print(f"APNG(申請用): {out} ({len(data) // 1024}KB, {len(frames)}コマ, 約{total_ms // n}ms/コマ)")
    print(f"GIF(確認用) : {gif}")
    return check_file(out, "anim")


def cmd_extras(a):
    img = Image.open(a.image)
    img = next(ImageSequence.Iterator(img)).convert("RGBA")
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    def trim(im):
        return im.crop(im.getbbox() or (0, 0, im.width, im.height))

    def padded(im, w, h, pad):
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        inner = fit(im, w - pad * 2, h - pad * 2)
        canvas.paste(inner, (pad, pad))
        return canvas

    padded(trim(img), *MAIN_SIZE, a.pad).save(out / "main.png", optimize=True)
    # タブは小さいので文字を外し、キャラだけを大きく入れる
    tab_src = trim(img.crop((0, a.tab_top, img.width, img.height))) if a.tab_top else trim(img)
    padded(tab_src, *TAB_SIZE, 2).save(out / "tab.png", optimize=True)
    print(f"メイン画像: {out / 'main.png'}\nタブ画像  : {out / 'tab.png'}")


def check_file(path, kind):
    path = Path(path)
    img = Image.open(path)
    problems = []
    size = path.stat().st_size
    if kind == "anim":
        n = getattr(img, "n_frames", 1)
        total = sum(f.info.get("duration", 0) for f in ImageSequence.Iterator(img))
        loops = img.info.get("loop", 0)
        if img.format != "PNG" or n < 2:
            problems.append("APNG(アニメーションPNG)ではありません")
        if img.width > ANIM_MAX_W or img.height > ANIM_MAX_H:
            problems.append(f"サイズ {img.size} が最大 {ANIM_MAX_W}x{ANIM_MAX_H} を超えています")
        if max(img.size) < ANIM_MIN_SIDE:
            problems.append(f"縦横どちらかが {ANIM_MIN_SIDE}px 以上必要です")
        if not ANIM_MIN_FRAMES <= n <= ANIM_MAX_FRAMES:
            problems.append(f"コマ数 {n} が規定外です({ANIM_MIN_FRAMES}〜{ANIM_MAX_FRAMES})")
        if loops == 0 or total * loops > ANIM_MAX_SECONDS * 1000:
            problems.append(f"再生時間 {total}ms x {loops or '無限'}ループ が {ANIM_MAX_SECONDS}秒以内ではありません")
        if size > ANIM_MAX_BYTES:
            problems.append(f"ファイルサイズ {size // 1024}KB が300KBを超えています")
        print(f"{path}: {img.size[0]}x{img.size[1]}, {n}コマ, {total}ms x {loops}ループ, {size // 1024}KB")
    else:
        if img.width > STATIC_MAX_W or img.height > STATIC_MAX_H:
            problems.append(f"サイズ {img.size} が最大 {STATIC_MAX_W}x{STATIC_MAX_H} を超えています")
        if img.width % 2 or img.height % 2:
            problems.append("縦横のピクセル数は偶数にしてください")
        if size > STATIC_MAX_BYTES:
            problems.append("ファイルサイズが1MBを超えています")
        print(f"{path}: {img.size[0]}x{img.size[1]}, {size // 1024}KB")
    first = next(ImageSequence.Iterator(img)).convert("RGBA")
    if first.getextrema()[3][0] == 255:
        problems.append("背景が透過されていません")
    for p in problems:
        print(f"  NG: {p}")
    if not problems:
        print("  OK: LINEの規定を満たしています")
    return 1 if problems else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("anim", help="スプライトシート → APNG + GIF")
    s.add_argument("sheet")
    s.add_argument("-o", "--out", required=True, help="出力APNGのパス (例: work/neko/anim/01.png)")
    s.add_argument("--cols", type=int, default=4)
    s.add_argument("--rows", type=int, default=2)
    s.add_argument("--gutter", type=int, default=0, help="コマ間の隙間(px)")
    s.add_argument("--frames", type=int, help="使うコマ数(空きコマがある場合)")
    s.add_argument("--seconds", type=int, default=1, choices=[1, 2, 3, 4], help="1ループの再生時間")
    s.add_argument("--loops", type=int, default=2, choices=[1, 2, 3, 4])
    s.add_argument("--key", default="auto", help="透過にする背景色 auto / #RRGGBB / none")
    s.add_argument("--tol", type=int, default=24, help="背景色の許容差")
    s.set_defaults(func=cmd_anim)

    s = sub.add_parser("extras", help="メイン画像/タブ画像を作成")
    s.add_argument("image")
    s.add_argument("-o", "--outdir", required=True)
    s.add_argument("--pad", type=int, default=8, help="メイン画像の余白(px)")
    s.add_argument("--tab-top", type=int, default=0, help="タブ画像はこのy座標より下(キャラ部分)だけを使う")
    s.set_defaults(func=cmd_extras)

    s = sub.add_parser("check", help="規定チェック")
    s.add_argument("files", nargs="+")
    s.add_argument("--kind", choices=["anim", "static"], default="anim")
    s.set_defaults(func=lambda a: max(check_file(f, a.kind) for f in a.files))

    a = p.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
