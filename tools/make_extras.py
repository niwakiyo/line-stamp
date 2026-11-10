#!/usr/bin/env python3
"""申請用のメイン画像(APNG 240x240)とタブ画像(96x74, キャラだけ)を作る。

  python3 tools/make_extras.py --main anim/05.png --tab anim/07.png --tab-clear 0,0,320,92 0,0,140,270 -o submit/
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence

from stamp_tool import encode_apng_palette


def fit(img, w, h, pad):
    img = img.copy()
    img.thumbnail((w - 2 * pad, h - 2 * pad), Image.LANCZOS)
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    c.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True, help="メイン画像にするスタンプの APNG")
    ap.add_argument("--tab", required=True, help="タブ画像にするスタンプの APNG(1コマ目を使う)")
    ap.add_argument("--tab-clear", nargs="*", default=[], help="タブで消す四角 x0,y0,x1,y1(セリフなど)")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    src = Image.open(a.main)
    frames, durs = [], []
    for f in ImageSequence.Iterator(src):
        frames.append(f.convert("RGBA"))
        durs.append(int(f.info.get("duration", 100)))
    box = None
    for f in frames:
        b = f.getbbox()
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    mains = []
    for f in frames:
        m = fit(f.crop(box), 240, 240, 8)
        m.putalpha(m.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
        mains.append(m)
    data = encode_apng_palette(mains, durs, src.info.get("loop", 2))
    (out / "main.png").write_bytes(data)
    print(f"メイン画像: {out / 'main.png'}({len(data) // 1024}KB, {len(mains)}コマ)")

    t = Image.open(a.tab)
    t.seek(0)
    f = t.convert("RGBA")
    for r in a.tab_clear:
        ImageDraw.Draw(f).rectangle(tuple(int(v) for v in r.split(",")), fill=(0, 0, 0, 0))
    c = f.crop(f.getbbox())
    c.thumbnail((92, 70), Image.LANCZOS)
    tab = Image.new("RGBA", (96, 74), (0, 0, 0, 0))
    tab.paste(c, ((96 - c.width) // 2, (74 - c.height) // 2))
    tab.save(out / "tab.png", optimize=True)
    print(f"タブ画像  : {out / 'tab.png'}")


if __name__ == "__main__":
    main()
