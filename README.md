# line-stamp

LINE Creators Market に提出できる **LINEスタンプ画像を自動生成** するツールです。
`stamps.json` に「セリフ」と「表情」を書くだけで、仕様どおりのスタンプ画像・メイン画像・タブ画像と、提出用 ZIP を作ります。

![preview](preview.png)

## 使い方

```bash
pip install -r requirements.txt
python3 make_stamps.py
```

生成されるもの:

| ファイル | 内容 |
| --- | --- |
| `output/01.png` 〜 | スタンプ画像 (最大 370×320px・偶数px・背景透過・余白 10px) |
| `output/main.png` | メイン画像 (240×240px) |
| `output/tab.png` | トークルームタブ画像 (96×74px) |
| `mochi_stamp.zip` | 上記をまとめた提出用 ZIP |
| `preview.png` | 確認用の一覧画像 (LINE のトーク背景風) |

生成後に自動で仕様チェック (サイズ・偶数px・透過・1MB 以下・枚数) を行います。
手持ちの画像フォルダだけをチェックしたいときは:

```bash
python3 make_stamps.py --check path/to/folder
```

## stamps.json の書き方

```json
{
  "name": "mochi_stamp",          // ZIP のファイル名
  "main_stamp": 2,                // メイン/タブ画像に使うスタンプ番号
  "font": null,                   // 日本語フォントのパス (null なら自動で探す)
  "character": { "body": "#FFF4E0", "outline": "#4A3B32", "cheek": "#FFB3B3" },
  "text_style": { "color": "#FF7A45", "stroke": "#FFFFFF" },
  "stamps": [
    { "text": "おはよう", "expression": "smile" },
    { "text": "ありがとう!", "expression": "happy", "text_style": { "color": "#FF5C8A" } },
    { "text": "よろしく", "image": "art/yoroshiku.png" }
  ]
}
```

※ JSON にはコメントを書けないので、実際のファイルでは `//` 以降は消してください。

- **`expression`** (内蔵キャラの表情): `smile` `happy` `love` `wink` `surprised` `sad` `angry` `sleepy` `think`
- **`image`**: 自分で描いたイラスト (背景透過 PNG) を使う場合はパスを指定。キャラの代わりにその画像が配置され、セリフが下に入ります
- **`text`**: 空にするとイラストのみのスタンプになります。改行は `\n`
- スタンプの枚数は **8 / 16 / 24 / 32 / 40 枚** のいずれかにする必要があります

## 申請までの流れ

1. [LINE Creators Market](https://creator.line.me/ja/) にログインし、クリエイター登録
2. 「新規登録」→「スタンプ」を選び、タイトル・説明文 (日本語/英語) を入力
3. 「スタンプ画像」タブで、生成した `mochi_stamp.zip` を「ZIPファイルでアップロード」
4. 販売価格・エリアなどを設定して「リクエスト」→ 審査 (通常数日〜) → 承認後にリリース

## 審査で気をつけること

- 他人の著作物・キャラクター・有名人・ロゴなどを使わない
- 文字だけ・同じ絵の使い回しが多いとリジェクトされやすい (表情やポーズを変える)
- 日常会話で使いやすいセリフ (あいさつ・お礼・返事・感情) を中心にするのがおすすめ
