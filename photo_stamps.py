"""画像生成 AI などで作った写真風の絵を、LINE の静止画スタンプにする。

photos/01.png 〜 24.png (無地の白い背景) を置いて実行すると、背景を透明にし、
大きさをそろえ、上にセリフを縁取り文字で入れて、提出用 ZIP を作る。

    python3 photo_stamps.py   # → output_tennis/ と tennis_stamp.zip
"""
import argparse
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from make_stamps import MAIN_SIZE, TAB_SIZE, MARGIN

SIZE = (370, 320)
FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
TEXT_COLOR, TEXT_INK = "#1F3A8A", "#FFFFFF"


def remove_background(img, tol=38):
    """四すみとつながっている、背景に近い色の部分を透明にする。"""
    img = img.convert("RGB").convert("RGBA")
    w, h = img.size
    marker = (255, 0, 255, 0)
    work = img.copy()
    for x in range(0, w, 8):
        for y in (0, h - 1):
            if work.getpixel((x, y)) != marker:
                ImageDraw.floodfill(work, (x, y), marker, thresh=tol)
    for y in range(0, h, 8):
        for x in (0, w - 1):
            if work.getpixel((x, y)) != marker:
                ImageDraw.floodfill(work, (x, y), marker, thresh=tol)
    mask = work.getchannel("A").filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))  # ふちの白残りを消す
    img.putalpha(mask)
    return img


def text_image(text, size=46):
    font = ImageFont.truetype(FONT, size)
    l, t, r, b = font.getbbox(text)
    pad = 8
    img = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad - l, pad - t), text, font=font, fill=TEXT_COLOR, stroke_width=7, stroke_fill=TEXT_INK)
    d.text((pad - l, pad - t), text, font=font, fill=TEXT_COLOR, stroke_width=1, stroke_fill=TEXT_COLOR)
    return img


def fit(img, box):
    k = min(box[0] / img.width, box[1] / img.height)
    return img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)


def make_stamp(src, text):
    person = remove_background(Image.open(src))
    person = person.crop(person.getchannel("A").getbbox())
    canvas = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    inner = (SIZE[0] - MARGIN * 2, SIZE[1] - MARGIN * 2)
    t = fit(text_image(text), (inner[0], 70)) if text else None
    th = t.height - 6 if t else 0
    p = fit(person, (inner[0], inner[1] - th))
    canvas.alpha_composite(p, ((SIZE[0] - p.width) // 2, SIZE[1] - MARGIN - p.height))
    if t:
        canvas.alpha_composite(t, ((SIZE[0] - t.width) // 2, MARGIN))
    return canvas, person


def square(img, size, margin):
    img = fit(img, (size[0] - margin * 2, size[1] - margin * 2))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return canvas


def build(cfg_path):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    src_dir, out = cfg_path.parent / cfg["input"], cfg_path.parent / cfg["output"]
    out.mkdir(parents=True, exist_ok=True)
    missing = [s["file"] for s in cfg["stamps"] if not (src_dir / s["file"]).exists()]
    if missing:
        raise SystemExit(f"{src_dir}/ に画像がありません: {', '.join(missing)}")
    first = None
    for i, s in enumerate(cfg["stamps"], 1):
        stamp, person = make_stamp(src_dir / s["file"], s["text"])
        stamp.save(out / f"{i:02d}.png")
        first = first or person
        print(f"  {i:02d}.png  {s['text']}")
    square(first, MAIN_SIZE, MARGIN).save(out / "main.png")
    square(first, TAB_SIZE, 2).save(out / "tab.png")
    zip_path = cfg_path.parent / f"{cfg['name']}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.glob("[0-9][0-9].png")) + [out / "main.png", out / "tab.png"]:
            z.write(p, p.name)
    print(f"\n✅ 出力: {out}/  提出用 ZIP: {zip_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="写真風の静止画スタンプ")
    ap.add_argument("-c", "--config", default="tennis_stamps.json")
    build(ap.parse_args().config)
