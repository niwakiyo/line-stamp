#!/usr/bin/env python3
"""set05: set04(クリスマス)のアニメ・キャラ・背景はそのままで、セリフだけを入れかえた24個。

  python3 tools/set05.py 01 --png work/set05/design/01_sheet.png

変えるのはセリフ(文字・大きさ・行の分け方・置き方)と、セリフの書体だけ。
- 吹き出しのないセリフ: 太い丸ゴシック(M PLUS Rounded 1c ExtraBold)で強めの口調に合わせる
- カードの文字: ペンで書く手書きの書体のまま(カードらしさを残す)
絵・動き・小物・色・コマ数は set04 と同じ(xmas.py / xmas2.py をそのまま使う)。
"""
import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image

import winter

ROOT = Path(__file__).resolve().parent.parent
BOLD = ROOT / "assets/fonts/MPLUSRounded1c-ExtraBold.ttf"

# set04 のセリフ(1行目) → 新しいセリフ。(文字, 大きさ, 強調) の行、ほかに置き方を変えるときは typ・x0・y0
SPEECH = {
    "メリー": dict(lines=[("ちーっす!!", 40, True)]),
    "おつかれ": dict(lines=[("おつかれ", 34, True), ("ッス!", 34, True)]),
    "プレゼント": dict(lines=[("これ", 38, True), ("受け取れや", 29, True)], dx=-6, dy=4),
    "今年も": dict(lines=[("あざー", 44, True), ("っす!!", 40, True)]),
    "いい子に": dict(lines=[("なんか", 32, True), ("文句ある?", 32, True)]),
    "いって": dict(lines=[("ぶっちぎり", 38, True), ("だぜ!", 38, True)], dy=12),
    "今から": dict(lines=[("今から", 38, True), ("帰っから", 34, True)]),
    "飾りつけ": dict(lines=[("今それどころ", 30, True), ("じゃねぇ", 34, True)], dy=3),
    "キラキラ": dict(lines=[("エモすぎ…", 36, True)], dx=-8, dy=10),
    "楽しみ": dict(lines=[("テンション", 36, True), ("爆アゲ!!", 38, True)]),
    "かんぱい": dict(lines=[("優勝", 50, True), ("!!", 44, True)], x0=168, y0=33),
    "寒い": dict(lines=[("は?", 50, True), ("寒すぎて無理", 30, True)], dy=3),
    "雪だるま": dict(lines=[("ドヤァ!!", 44, True)], x0=50, y0=22),
    "Merry": dict(lines=[("りょ!!", 56, True)], dx=3),
    "メリクリ!": dict(lines=[("ウェーイ!!", 46, True)], dy=3),
}

# カード: set04 の文字(1行目) → 新しい文字。(文字, 大きさ) の行
CARD = {
    "Merry": [("マジ", 40), ("神対応", 32)],
    "Happy": [("それな", 46), ("わかりみ", 30)],
    "メリー": [("推せる", 42), ("尊い…", 30)],
    "よいお年を": [("あとは", 38), ("任せたぜ", 34)],
    "素敵な": [("ズッ友", 40), ("だょ", 36)],
    "楽しい": [("ぶっちゃけ", 32), ("余裕", 42), ("っしょ", 30)],
    "ホワイト": [("夜露死苦", 46), ("(よろしく)", 24)],
    "よい": [("ワンチャン", 36), ("ある", 36)],
    "ありがとう": [("あざまる", 38), ("水産", 42)],
}

_make = winter.make


def make_new(pal, lines, typ, poses, marks, m=winter.MID, x0=28, y0=24, **kw):
    new = SPEECH.get(lines[0][0])
    if new:
        lines = new["lines"]
        typ, x0, y0 = new.get("typ", typ), new.get("x0", x0) + new.get("dx", 0), new.get("y0", y0) + new.get("dy", 0)
    return _make(pal, lines, typ, poses, marks, m, x0, y0, **kw)


winter.make = make_new  # xmas・xmas2 を読む前に入れかえる(どちらも import のときに make を使う)

import xmas  # noqa: E402

xmas.SAY_FONT = BOLD
import inko  # noqa: E402
import newyear  # noqa: E402
import soft  # noqa: E402
import xmas2  # noqa: E402

_card_frames = xmas2.card_frames


def card_frames_new(paper, pos, lines, cols, scene, n=20):
    tx0, ty0, tw, rows = lines
    rows = CARD.get(rows[0][0], rows)
    return _card_frames(paper, pos, (tx0, ty0, tw, rows), cols, scene, n)


xmas2.card_frames = card_frames_new


def main():
    import json
    fits = json.load(open(ROOT / "work/set05/fit_set04.json"))  # set04 の縮小・移動(絵の位置を変えないため)
    stamps = dict(xmas.STAMPS)
    stamps.update(xmas2.STAMPS)
    ap = argparse.ArgumentParser()
    ap.add_argument("stamp", choices=sorted(list(stamps) + list(xmas2.CARDS)))
    ap.add_argument("--png", required=True)
    a = ap.parse_args()
    if a.stamp in fits:
        xmas2.FIT_FIXED = tuple(fits[a.stamp])
    if a.stamp in xmas2.CARDS:
        newyear.card_sheet(xmas2.fit_all(xmas2.CARDS[a.stamp]()), a.png)
    elif a.stamp in xmas.STAMPS:  # 01・05 は set04 と同じく xmas.py の書き出し方
        frames = xmas.STAMPS[a.stamp]
        with tempfile.TemporaryDirectory() as tmp:
            soft.chara_png(frames, f"{tmp}/c.png")
            soft.text_png(frames, f"{tmp}/t.png")
            sheet = Image.new("RGBA", (soft.CW * soft.COLS, soft.CH * soft.ROWS), inko.BG)
            sheet.alpha_composite(Image.open(f"{tmp}/c.png").convert("RGBA"))
            sheet.alpha_composite(Image.open(f"{tmp}/t.png").convert("RGBA"))
            sheet.convert("RGB").save(a.png)
    else:
        xmas2.render(xmas2.STAMPS[a.stamp], a.png)
    print(f"シート: {a.png}", file=sys.stderr)


if __name__ == "__main__":
    main()
