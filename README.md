# line-stamp

LINEスタンプを「調査 → デザイン → アニメ化 → チェック → 申請文」の流れで作る、Claude Code のエージェントチームです。

## チーム

| 担当 | エージェント | やること | 出力 |
|---|---|---|---|
| 調査A | `researcher-character` | 売れているスタンプ・キャラ・絵柄・動き | `research/character.md` |
| 調査B | `researcher-text` | 売れているセリフ・フォント・配色 | `research/text.md` |
| デザイン | `canva-designer` | 企画を作り、ChatGPT/Gemini/Canvaでコマ割り画像を作成 | `plan.md`, `design/NN_sheet.png` |
| アニメ化 | `gif-maker` | コマ割り画像を切り分け・透過し、APNG(申請用)とGIF(確認用)にする | `anim/NN.png`, `anim/NN.gif`, `main.png`, `tab.png` |
| チェック | `quality-checker` | 規定・見た目・審査基準・売れるかを判定、差し戻し | `review.md` |
| 申請文 | `application-writer` | タイトル・説明文・タグなど申請用の文章 | `application.md` |

ファイルはすべて `work/<セット名>/` の下に作られます。

## 使い方

Claude Code で:

```
/make-stamp neko-keigo 敬語で話すゆるい猫、8個
```

## Canva無料プランへの対策

- **1スタンプ = 1枚の画像**。中に 4列×2行 = 8コマ(1コマ 320×270、全体 1280×540)を描いてもらい、
  `tools/stamp_tool.py` で切り分けてアニメにします。Canvaで作るデザインは何枚にも増えません。
- 無料プランは透過PNGを書き出せないので、背景を **#00FF00 単色** にしておき、ツール側で透過にします。

## ChatGPT / Gemini 連携

環境変数を設定すると、デザイン担当が画像生成に使います(どちらもなければCanvaだけで作ります)。

- `OPENAI_API_KEY` … ChatGPT(gpt-image-1)
- `GEMINI_API_KEY` … Gemini(gemini-2.5-flash-image)

クラウド環境の場合は、環境設定の「環境変数」に登録してください。

## ツール

```bash
# コマ割り画像 → APNG(申請用) + GIF(確認用)
python3 tools/stamp_tool.py anim work/neko/design/01_sheet.png -o work/neko/anim/01.png
# メイン画像(240x240)・タブ画像(96x74)
python3 tools/stamp_tool.py extras work/neko/anim/01.png -o work/neko/anim/
# LINEの規定チェック
python3 tools/stamp_tool.py check work/neko/anim/[0-9]*.png
# ChatGPT/Geminiで画像生成
python3 tools/gen_image.py --provider auto --prompt "..." -o work/neko/design/01_gen.png
```

必要なもの: Python 3 と Pillow(`pip install pillow`)。

## 注意

- LINEのアニメーションスタンプは **GIFではなくAPNG** で申請します(GIFは確認用)。
- アニメ規定: 最大 320×270px(縦横どちらかが270px以上)、5〜20コマ、再生は最大4秒、1ファイル300KB以下、背景透過。
- 実際の申請(LINE Creators Market への登録)は自分で行ってください。
