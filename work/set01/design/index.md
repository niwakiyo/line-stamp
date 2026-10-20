# set01 デザイン一覧

Canva: 「LINEスタンプ制作作業キャンバス」 https://www.canva.com/d/tgzwRgieXp-Pxai (編集用URL)

キャラもセリフも Canva のページ上にあり、各ページをそのまま書き出したものが `0N_sheet.png`(1280x540、4x2コマ、緑背景)。

| No | Canvaページ | セリフ(透過PNG・Canvaにアップロード済み) | 書き出したシート | 完成品 |
|---|---|---|---|---|
| 01 | 3ページ目「01 承知しました」 | 01_text.png | 01_sheet.png | ../anim/01.png |
| 02 | 4ページ目「02 ありがとうございます」 | 02_text.png | 02_sheet.png | ../anim/02.png |
| 03 | 5ページ目「03 お疲れさまです」 | 03_text.png | 03_sheet.png | ../anim/03.png |
| 04 | 6ページ目「04 よろしくお願いします」 | 04_text.png | 04_sheet.png | ../anim/04.png |
| 05 | 7ページ目「05 了解です！」 | 05_text.png | 05_sheet.png | ../anim/05.png |
| 06 | 8ページ目「06 すみません」 | 06_text.png | 06_sheet.png | ../anim/06.png |
| 07 | 9ページ目「07 おはようございます」 | 07_text.png | 07_sheet.png | ../anim/07.png |
| 08 | 10ページ目「08 おやすみなさい」 | 08_text.png | 08_sheet.png | ../anim/08.png |

- キャラは `tools/inko.py` が作った図形を Canva の edit-design で描いたもの。
- セリフは Canva の API でフォントを指定できないため、`tools/inko.py --text-png` で M PLUS Rounded 1c から作った透過PNGを
  Canva にアップロードし、ページ全面(1280x540)に重ねている。
- 01_chara.png は初期の合成方式の名残(現在は未使用)。
- 品質チェックの経緯は `../qa.md`(修正3回で全8種合格)。
