# set01 デザイン一覧 v2(ふわふわ版)

Canva: 「LINEスタンプ制作作業キャンバス」 https://www.canva.com/d/tgzwRgieXp-Pxai (編集用URL)

v1(`../design/`、3〜10ページ)に対するユーザーの指摘「セリフが画像と別々で弱い」「絵の縁が固い」を受けて作り直したもの。
各ページは 1280x810、4x3=12コマ、緑背景(#00FF00)。そのまま書き出したものが `0N_sheet.png`。

| No | Canvaページ | セリフ(透過PNG・Canvaにアップロード済み) | 書き出したシート | 完成品 |
|---|---|---|---|---|
| 01 | 11ページ目「v2 01 承知しました」 | 01_text.png | 01_sheet.png | ../anim/01.png |
| 02 | 12ページ目「v2 02 ありがとうございます」 | 02_text.png | 02_sheet.png | ../anim/02.png |
| 03 | 13ページ目「v2 03 お疲れさまです」 | 03_text.png | 03_sheet.png | ../anim/03.png |
| 04 | 14ページ目「v2 04 よろしくお願いします」 | 04_text.png | 04_sheet.png | ../anim/04.png |
| 05 | 15ページ目「v2 05 了解です！」 | 05_text.png | 05_sheet.png | ../anim/05.png |
| 06 | 16ページ目「v2 06 すみません」 | 06_text.png | 06_sheet.png | ../anim/06.png |
| 07 | 17ページ目「v2 07 おはようございます」 | 07_text.png | 07_sheet.png | ../anim/07.png |
| 08 | 18ページ目「v2 08 おやすみなさい」 | 08_text.png | 08_sheet.png | ../anim/08.png |

- キャラは `tools/soft.py`(`tools/inko.py` の形をゆるく・ふわふわに直したもの)が作った図形を Canva の edit-design で描いた。
  12コマ分の同じ部品を1つの図形にまとめているので、1ページあたり図形11〜12個+セリフ画像1枚。
- セリフは Yusei Magic(手書き風、OFL)で `tools/soft.py NN --text-png` が作った透過PNGをページ全面に重ねている。
  キーワード(例: よろしく)はコーラル、続き(例: お願いします)は茶色で2段に分け、1文字ずつ出る・ポンと弾む・波打つ・震えるなどの出し方をつけた。
- `0N_preview.png` は Canva に描く前のローカル確認用。
- アニメ化: `python3 tools/stamp_tool.py anim design2/0N_sheet.png -o anim/0N.png --cols 4 --rows 3 --seconds 2 --loops 2 --key auto --tol 24`
- 一覧: `../preview/v2_overview.png`(各スタンプの1コマ目と6コマ目)
