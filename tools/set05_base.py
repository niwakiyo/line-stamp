#!/usr/bin/env python3
"""set05 の下絵: set04 の絵(キャラ・背景・小物・雪やキラキラ)を、文字だけ抜いて書き出す。

  python3 tools/set05_base.py            # 24個すべて → work/set05/base/NN.png(透明の背景のシート)

- 絵の縮小・移動は set04 と同じ(work/set05/fit_set04.json)。雪やキラキラは set04 と同じ場所(文字をよける計算もそのまま)。
- カードは、紙と絵(雪・電球・キャラなど)だけ。set04 のペンの文字は書かない。
  飾りの出方(書き終わりでぽんと出る)も set04 と同じコマにする。カードの位置は base/cards.json に書く。
"""
import json
import math
import sys
import tempfile
from pathlib import Path

from PIL import Image

import inko
import soft
import xmas
import xmas2

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work/set05/base"
CW, CH = 320, 270
CARD_INFO = {}


def card_frames_picture(paper, pos, lines, cols, scene, n=20):
    """set04 の card_frames と同じコマ割り(t と飾りの出方)で、紙と絵だけを描く。"""
    W, H = paper.size
    px, py = pos
    tx0, ty0, tw, rows = lines
    chars = xmas2.card_text(rows, px + tx0, py + ty0, tw, cols)
    N = len(chars)
    per = max(1, math.ceil(N / 13))
    sched = [(0, 1.0), (1, 0.0)]
    shown, t = 0, 1
    while shown < N:
        t += 1
        shown = min(N, shown + per)
        sched.append((t, 0.0))
    t += 1
    sched.append((t, 1.25))
    while len(sched) < n:
        t += 1
        sched.append((t, 1.0))
    sched = sched[:n]
    pop = [k for t, k in sched].index(1.25) if 1.25 in [k for t, k in sched] else n
    CARD_INFO["last"] = dict(paper=(px, py, W, H), text=(px + tx0, py + ty0, tw), pop=pop)
    frames = []
    for t, k in sched:
        im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        im.alpha_composite(paper, (px, py))
        scene(im, t, k)
        frames.append(im)
    return frames


xmas2.card_frames = card_frames_picture


def strip(frames):
    for fr in frames:
        fr["words"] = []
    return frames


def cells_of(frames, use_fit, fit):
    with tempfile.TemporaryDirectory() as tmp:
        soft.chara_png(frames, f"{tmp}/c.png")
        soft.text_png(frames, f"{tmp}/t.png")  # 雪・キラキラなど(文字はない)
        chara = Image.open(f"{tmp}/c.png").convert("RGBA")
        text = Image.open(f"{tmp}/t.png").convert("RGBA")
    cells = []
    for i, fr in enumerate(frames):
        x0, y0 = (i % 4) * CW, (i // 4) * CH
        cell = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        if use_fit:
            if fr.get("back"):
                fr["back"](cell)
            if not fr.get("nochar"):
                cell.alpha_composite(chara.crop((x0, y0, x0 + CW, y0 + CH)))
            if fr.get("front"):
                fr["front"](cell)
            cell.alpha_composite(text.crop((x0, y0, x0 + CW, y0 + CH)))
        else:  # 01・05 は set04 と同じく、キャラと印をそのまま重ねる
            cell.alpha_composite(chara.crop((x0, y0, x0 + CW, y0 + CH)))
            cell.alpha_composite(text.crop((x0, y0, x0 + CW, y0 + CH)))
        cells.append(cell)
    if use_fit:
        xmas2.FIT_FIXED = tuple(fit)
        cells = xmas2.fit_all(cells)
    return cells


def save_sheet(cells, path, cols):
    rows = math.ceil(len(cells) / cols)
    sheet = Image.new("RGBA", (CW * cols, CH * rows), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        sheet.alpha_composite(c, ((i % cols) * CW, (i // cols) * CH))
    sheet.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fits = json.load(open(ROOT / "work/set05/fit_set04.json"))
    want = sys.argv[1:] or [f"{k:02d}" for k in range(1, 25)]
    info = json.load(open(OUT / "cards.json")) if (OUT / "cards.json").exists() else {}
    for n in want:
        if n in xmas2.CARDS:
            cells = xmas2.CARDS[n]()
            info[n] = CARD_INFO["last"]
            xmas2.FIT_FIXED = tuple(fits[n])
            cells = xmas2.fit_all(cells)
            save_sheet(cells, OUT / f"{n}.png", 5)
        elif n in xmas.STAMPS:
            save_sheet(cells_of(strip(xmas.STAMPS[n]), False, None), OUT / f"{n}.png", 4)
        else:
            save_sheet(cells_of(strip(xmas2.STAMPS[n]), True, fits[n]), OUT / f"{n}.png", 4)
        print("下絵:", n, file=sys.stderr)
    json.dump(info, open(OUT / "cards.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
