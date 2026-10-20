# set01 デザイン一覧

Canva: 「LINEスタンプ制作作業キャンバス」 https://www.canva.com/d/tgzwRgieXp-Pxai (編集用URL)

| No | Canvaページ | キャラ(Canva書き出し) | セリフ(透過PNG) | 合成したシート |
|---|---|---|---|---|
| 01 | 3ページ目「01 承知しました」 | 01_chara.png | 01_text.png | 01_sheet.png |

- キャラは `tools/inko.py` が作った図形を Canva の edit-design で描いたもの。
- セリフは Canva の API でフォントを指定できないため、`tools/inko.py --text-png` で M PLUS Rounded 1c から作った透過PNG。
  今はローカルで合成している(Canva へのアップロードには www.canva.com への通信許可が必要)。
