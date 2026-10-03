# line-stamp

LINE Creators Market に提出できる **LINEスタンプ画像を自動生成** するツールです。

## ドット絵 RPG 風スタンプ (pixel_stamps.py)

16bit 時代の RPG 風オリジナルキャラ 4 人 (剣士ユウ・魔法使いミラ・シーフのカイ・マスコットのもふ) と、
メッセージウィンドウ風の吹き出しで、流行りの言葉スタンプ 16 枚を作ります。

![pixel preview](preview_pixel.png)

```bash
pip install -r requirements.txt
python3 pixel_stamps.py          # pixel_stamps.json から生成
```

→ `output_pixel/` に 01〜16.png・main.png・tab.png、提出用 `pixel_party_stamp.zip`、確認用 `preview_pixel.png` ができます。

### pixel_stamps.json の書き方

```json
{ "chara": "kai", "text": "草", "expression": "happy", "effects": ["grass"], "pos": "left" }
```

- **`chara`**: `yuu` (剣士) / `mira` (魔法使い) / `kai` (シーフ) / `mofu` (マスコット)
- **`expression`**: `normal` `smile` `happy` `wink` `calm` `sleep` `angry` `sad` `love` `kira` `surprised`
- **`effects`**: `exclaim` `question` `exclaim_q` `heart` `hearts` `sparkle` `sparkles` `sweat` `zzz` `anger` `note` `crown` `grass`
  - 位置や大きさを変えたいときは `{"name": "heart", "dx": 10, "dy": -5, "scale": 8}`
- **`pos`**: キャラの位置 `left` / `center` / `right`、**`flip`**: `true` で左右反転
- `window` で吹き出しの色 (上下のグラデーション・文字・影) を変えられます
- キャラのドット絵や表情・エフェクトは `sprites.py` に文字で描いてあるので、直接編集して増やせます

### フォント

文字は GNU Unifont (ドット絵フォント) の `unifont_jp.otf` で描きます。
Linux では `fonts-unifont` パッケージで入ります。Mac / Windows では
<https://unifoundry.com/unifont/> から `unifont_jp-*.otf` をダウンロードし、
`fonts/unifont_jp.otf` という名前で置いてください。

## イラスト + 文字のスタンプ (make_stamps.py)

`stamps.json` に「セリフ」と「表情」を書くだけで、丸いキャラのスタンプや、自作イラストに文字を入れたスタンプを作ります。

![preview](preview.png)

```bash
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

### stamps.json の書き方

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
3. 「スタンプ画像」タブで、生成した ZIP (`pixel_party_stamp.zip` など) を「ZIPファイルでアップロード」
4. 販売価格・エリアなどを設定して「リクエスト」→ 審査 (通常数日〜) → 承認後にリリース

## 審査で気をつけること

- 他人の著作物・キャラクター・有名人・ロゴなどを使わない
- 文字だけ・同じ絵の使い回しが多いとリジェクトされやすい (表情やポーズを変える)
- 日常会話で使いやすいセリフ (あいさつ・お礼・返事・感情) を中心にするのがおすすめ
- 既存のゲーム・アニメのキャラクターや、それとそっくりな絵は使えません (このリポジトリのキャラはすべてオリジナルです)
