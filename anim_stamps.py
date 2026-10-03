#!/usr/bin/env python3
"""動くドット絵 LINE スタンプ (アニメーションスタンプ) ジェネレーター.

pixel_stamps.py と同じ部品 (キャラ・ウィンドウ・ステータス・メニュー) を使い、
スタンプごとに選んだ「動き」で APNG を作る。

LINE アニメーションスタンプの仕様:
  - 320x270px 以内 (縦横どちらかは 270px 以上)、APNG、背景透過、1 個 300KB 以下
  - 1 個 5〜20 フレーム、ループ 1〜4 回、再生時間 (ループ込み) は 1/2/3/4 秒のいずれか
  - 1 フレーム目が静止画 (一覧・サムネイル) として表示される → 1 フレーム目は完成形にする
  - 個数は 8 / 16 / 24 個、メイン画像 240x240 も APNG、タブ画像 96x74 は静止画 PNG

使い方:
    python3 anim_stamps.py                    # anim_stamps.json から生成
    python3 anim_stamps.py -c other.json
"""

import argparse
import copy
import json
import math
import zipfile
from pathlib import Path

from PIL import Image

import pixel_stamps as ps
from make_stamps import MAIN_SIZE, TAB_SIZE

ANIM_SIZE = (320, 270)
ANIM_COUNTS = (8, 16, 24)
ANIM_MAX_BYTES = 300 * 1024
U = 7  # キャラ 1 ドットぶんの移動量 (sprite_scale と同じ)

ps.set_layout(ANIM_SIZE, window=(10, 150, 310, 260), sprite_scale=U, sprite_x=26,
              panel_min_w=150, effect_scale=5, panel_pad=14)


# --- 共通の小道具 ------------------------------------------------------------
def state(item, **kw):
    """item をコピーし、エフェクトを辞書形式にそろえてから kw を上書きした「1 コマの状態」を返す。"""
    s = copy.deepcopy(item)
    s["effects"] = [e if isinstance(e, dict) else {"name": e} for e in s.get("effects", [])]
    s.update(kw)
    return s


def move_effects(s, dx=0, dy=0, hidden=None, scale=None):
    for e in s["effects"]:
        e["dx"] = e.get("dx", 0) + dx
        e["dy"] = e.get("dy", 0) + dy
        if hidden is not None:
            e["hidden"] = hidden
        if scale is not None:
            e["scale"] = scale
    return s


def split(total, n):
    """total ミリ秒を n コマに、合計がぴったり total になるよう配る。"""
    base = total // n
    return [base + (1 if i < total - base * n else 0) for i in range(n)]


# --- 動きの種類 --------------------------------------------------------------
# どれも (コマの状態のリスト, 各コマの表示時間ms, ループ回数) を返す。
# 1 コマ目は「完成形」(= item そのもの) にしてある。

def anim_bob(item, p):
    """エフェクトがふわふわ上下する。body=breath で体もゆっくり上下 (寝息)。"""
    n, frames = 8, []
    for i in range(n):
        s = move_effects(state(item), dy=round(-U * math.sin(2 * math.pi * i / n)))
        if p.get("body") == "breath" and i >= n // 2:
            s["_dy"] = U
        frames.append(s)
    return frames, split(1000, n), p.get("loops", 3)


def anim_shake(item, p):
    """キャラがぶるぶる震える。pulse=true でエフェクトが点滅。"""
    dxs = [0, -U, U, -U, U, -U, U, 0, 0, 0]
    frames = []
    for i, dx in enumerate(dxs):
        s = state(item, _dx=dx)
        if p.get("pulse"):
            move_effects(s, hidden=(i % 2 == 1 and i < 7))
        frames.append(s)
    return frames, split(1000, len(dxs)), p.get("loops", 2)


def anim_hop(item, p):
    """ぴょんと跳ねる。heart=true でエフェクトがドキドキ拡大。"""
    dys = [0, -U, -2 * U, -3 * U, -2 * U, -U, 0, 0]
    frames = []
    for i, dy in enumerate(dys):
        s = move_effects(state(item, _dy=dy), dy=dy)
        if p.get("heart"):
            move_effects(s, scale=6 if i in (2, 3, 4) else 5)
        frames.append(s)
    return frames, split(1000, len(dys)), p.get("loops", 3)


def anim_blink(item, p):
    """ときどきまばたき (目を閉じる)。エフェクトはゆっくり上下。"""
    n, frames = 10, []
    for i in range(n):
        s = move_effects(state(item), dy=-U // 2 if i % 4 >= 2 else 0)
        if i in p.get("at", [6]):
            s["expression"] = p.get("blink", "calm")
        frames.append(s)
    return frames, split(2000, n), p.get("loops", 2)


def anim_drain(item, p):
    """ステータスのゲージが満タンから最終値まで減っていく。"""
    row = item["panel"]["rows"][0]
    start, end = p.get("from", row["max"]), row["value"]
    steps = 10
    frames, ms = [state(item)], [200]
    for i in range(steps + 1):
        t = i / steps
        v = round(start + (end - start) * (1 - (1 - t) ** 2))  # 最初は速く、最後はゆっくり
        s = state(item, _dx=(U if i % 2 else 0) if i < steps else 0)
        s["panel"]["rows"][0]["value"] = v
        if i < steps:
            s["expression"] = p.get("from_expression", "normal")
        frames.append(s)
        ms.append(140)
    rest = 3000 - sum(ms)
    for d in split(rest, 3):
        frames.append(state(item))
        ms.append(d)
    return frames, ms, 1


def anim_cursor(item, p):
    """コマンド選択のカーソルが迷ってから、最後の選択肢に決まる。"""
    final = item["panel"].get("cursor", 0)
    other = p.get("from", 0 if final else 1)
    frames = [state(item)]
    for i in range(6):  # 迷っている間はカーソルが点滅
        s = state(item, expression=p.get("from_expression", item.get("expression", "normal")))
        s["panel"]["cursor"] = other if i % 2 == 0 else -1
        frames.append(s)
    for i in range(6):
        s = state(item, _dx=[U, -U, 0, 0, 0, 0][i])
        frames.append(s)
    return frames, split(3000, len(frames)), 1


def anim_fall(item, p):
    """立っていたキャラがよろけて倒れる (item は pose=down の完成形)。"""
    frames = [state(item)]
    stand = dict(pose=None, expression=p.get("from_expression", "tired"))
    for dx in (0, U, -U, U, 0):
        frames.append(move_effects(state(item, _dx=dx, **stand), hidden=True))
    frames.append(move_effects(state(item, _dy=-2 * U), hidden=True))
    frames.append(move_effects(state(item), hidden=True))
    for i in range(6):
        frames.append(move_effects(state(item), dy=round(-U * math.sin(math.pi * i / 3))))
    ms = [200] + [150] * 5 + [100, 200] + split(3000 - 200 - 750 - 300, 6)
    return frames, ms, 1


def anim_soul(item, p):
    """魂がふわーっと抜けていく。"""
    n, frames = 10, [state(item)]
    for i in range(1, n):
        s = move_effects(state(item), dy=round(5 * U - 6 * U * i / (n - 1)),
                         dx=round(U * math.sin(math.pi * i / 3)))
        frames.append(s)
    return frames, split(2000, n), p.get("loops", 2)


def anim_drip(item, p):
    """汗がたらーっと流れる。"""
    dys = [0, 2, 4, 6, 8, 10, -4, -2]
    frames = [move_effects(state(item), dy=d) for d in dys]
    return frames, split(1000, len(dys)), p.get("loops", 3)


def anim_type(item, p):
    """RPG のメッセージのように 1 文字ずつ表示し、最後に ▼ が点滅する。"""
    n = len(item["text"].replace("\n", ""))
    frames, ms = [state(item, _arrow=True)], [100]
    typing = min(n, 12)
    for i in range(1, typing + 1):
        frames.append(state(item, _chars=math.ceil(n * i / typing)))
        ms.append(100)
    holds = max(1, min(6, 20 - len(frames)))
    for i, d in enumerate(split(p.get("seconds", 3) * 1000 - sum(ms), holds)):
        frames.append(state(item, _arrow=(i % 2 == 0)))
        ms.append(d)
    return frames, ms, 1


ANIMS = {
    "bob": anim_bob, "shake": anim_shake, "hop": anim_hop, "blink": anim_blink,
    "drain": anim_drain, "cursor": anim_cursor, "fall": anim_fall, "soul": anim_soul,
    "drip": anim_drip, "type": anim_type,
}


# --- 書き出しとチェック ------------------------------------------------------
def save_apng(images, durations, loops, path):
    images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=loops,
                   disposal=1, blend=0, optimize=True)


def apng_info(path):
    im = Image.open(path)
    durations = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        durations.append(im.info.get("duration", 0))
    return {"size": im.size, "frames": len(durations), "ms": round(sum(durations)),
            "loops": im.info.get("loop", 0), "bytes": Path(path).stat().st_size,
            "mode": im.mode}


def check_anim(path, kind):
    info = apng_info(path)
    errors = []
    w, h = info["size"]
    if kind == "stamp":
        if w > ANIM_SIZE[0] or h > ANIM_SIZE[1] or not (w >= 270 or h >= 270):
            errors.append(f"サイズ {w}x{h}: 320x270 以内で、縦横どちらかが 270px 以上必要")
    elif (w, h) != MAIN_SIZE:
        errors.append(f"サイズ {w}x{h}: メイン画像は 240x240")
    if not 5 <= info["frames"] <= 20:
        errors.append(f"フレーム数 {info['frames']}: 5〜20 にしてください")
    if not 1 <= info["loops"] <= 4:
        errors.append(f"ループ回数 {info['loops']}: 1〜4 回にしてください")
    total = info["ms"] * max(1, info["loops"])
    if total not in (1000, 2000, 3000, 4000):
        errors.append(f"再生時間 {total}ms: ループ込みで 1/2/3/4 秒ちょうどにしてください")
    if info["bytes"] > ANIM_MAX_BYTES:
        errors.append(f"容量 {info['bytes'] // 1024}KB: 300KB 以下にしてください")
    if info["mode"] not in ("RGBA", "P"):
        errors.append("背景透過になっていません")
    return info, errors


def make_preview_gif(stamp_frames, dest, cols=4, tick=50):
    """全スタンプを並べて同時に動かす確認用 GIF (提出物ではない)。"""
    cell = (ANIM_SIZE[0] + 16, ANIM_SIZE[1] + 16)
    rows = math.ceil(len(stamp_frames) / cols)
    longest = max(sum(ms) * loops for _, ms, loops in stamp_frames)
    sheets = []
    for t in range(0, longest, tick * 2):
        sheet = Image.new("RGB", (cell[0] * cols, cell[1] * rows), (140, 171, 216))
        for n, (imgs, ms, loops) in enumerate(stamp_frames):
            local = t % sum(ms)
            if t >= sum(ms) * loops:  # 再生が終わったら 1 フレーム目で止まる (LINE と同じ)
                idx = 0
            else:
                acc, idx = 0, 0
                for idx, d in enumerate(ms):
                    acc += d
                    if local < acc:
                        break
            x, y = (n % cols) * cell[0] + 8, (n // cols) * cell[1] + 8
            sheet.paste(imgs[idx], (x, y), imgs[idx])
        sheets.append(sheet)
    sheets[0].save(dest, save_all=True, append_images=sheets[1:], duration=tick * 2, loop=0)


def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = cfg_path.parent / cfg.get("output", "output_anim")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    style_cfg = {"window": cfg.get("window", {})}

    problems, all_frames = [], []
    stamps = cfg["stamps"]
    if len(stamps) not in ANIM_COUNTS:
        problems.append(f"スタンプ数 {len(stamps)}: アニメーションは {ANIM_COUNTS} 個のいずれか")
    for i, item in enumerate(stamps, 1):
        anim = item.get("anim", {"type": "bob"})
        states, ms, loops = ANIMS[anim["type"]](item, anim)
        imgs = [ps.render(s, style_cfg) for s in states]
        path = out / f"{i:02d}.png"
        save_apng(imgs, ms, loops, path)
        all_frames.append((imgs, ms, loops))
        info, errs = check_anim(path, "stamp")
        problems += [f"{path.name}: {e}" for e in errs]
        print(f"  {path.name}  {anim['type']:<6} {info['frames']:>2}f {info['ms'] * info['loops']:>4}ms "
              f"{info['bytes'] // 1024:>3}KB  {item['text']!r}")

    # メイン画像 (240x240 APNG): キャラがまばたき / タブ画像 (静止画)
    chara = cfg.get("main_chara", "yusha")
    expr = cfg.get("main_expression", "tired")
    seq = [expr] * 6 + [cfg.get("main_blink", "calm")] + [expr] * 3
    sprites = [ps.sprite_image(chara, e) for e in seq]
    k = min((MAIN_SIZE[0] - 20) // sprites[0].width, (MAIN_SIZE[1] - 20) // sprites[0].height)
    mains = []
    for j, sp in enumerate(sprites):
        big = ps.scaled(sp, k)
        canvas = Image.new("RGBA", MAIN_SIZE, (0, 0, 0, 0))
        bob = k if j in (2, 3, 7, 8) else 0
        canvas.alpha_composite(big, ((MAIN_SIZE[0] - big.width) // 2, (MAIN_SIZE[1] - big.height) // 2 + bob - k // 2))
        mains.append(canvas)
    save_apng(mains, split(2000, len(mains)), 2, out / "main.png")
    problems += [f"main.png: {e}" for e in check_anim(out / "main.png", "main")[1]]
    ps.fit_square(ps.sprite_image(chara, cfg.get("tab_expression", expr)), TAB_SIZE, 4).save(out / "tab.png")

    make_preview_gif(all_frames, cfg_path.parent / cfg.get("preview", "preview_anim.gif"))
    zip_path = cfg_path.parent / f"{cfg.get('name', 'anim_stamp')}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.glob("[0-9][0-9].png")) + [out / "main.png", out / "tab.png"]:
            z.write(p, p.name)

    if problems:
        print("\n❌ 仕様チェックで問題が見つかりました:")
        for p in problems:
            print("  -", p)
    else:
        print("\n✔ 仕様チェック OK (サイズ・フレーム数・再生時間・ループ・300KB以下・個数)")
    print(f"\n✅ 出力: {out}/  提出用 ZIP: {zip_path}")


def main():
    ap = argparse.ArgumentParser(description="動くドット絵 LINE スタンプジェネレーター")
    ap.add_argument("-c", "--config", default="anim_stamps.json")
    build(ap.parse_args().config)


if __name__ == "__main__":
    main()
