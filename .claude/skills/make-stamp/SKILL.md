---
name: make-stamp
description: LINEスタンプ制作チーム(調査2人→デザイン→アニメ化→チェック→申請文)を順に動かして1セット作る。「スタンプを作って」「/make-stamp テーマ」で使う。
---
# LINEスタンプ制作の進め方

引数: セット名(英小文字、例 `neko-keigo`)と、あればテーマ・個数(既定8個)。
作業フォルダは `work/<セット名>/`。各担当には必ずこのフォルダのパスを伝える。

1. **調査(並行)**: `researcher-character` と `researcher-text` を同時に起動する。
2. **企画・デザイン**: 2つのレポートができたら `canva-designer` を起動する。
   - Canvaは無料プラン。1スタンプ1枚(4×2コマ, 1280×540, 背景 #00FF00)を守らせる。
   - Canvaのデザインを作る前に `plan.md` をユーザーに見せて、進めてよいか確認する。
3. **アニメ化**: `gif-maker` を起動し `design/*_sheet.png` を APNG + GIF にする。
4. **チェック**: `quality-checker` を起動する。
   - 「要修正」なら指摘ごとに `canva-designer` か `gif-maker` に戻して直し、再チェック(最大3周)。
   - 3周しても合格しない場合はユーザーに相談する。
5. **申請文**: 合格したら `application-writer` を起動する。
6. ユーザーへの報告: 合格したスタンプのGIF、`application.md` の要点、残った課題。
   LINE Creators Market への実際の申請はユーザーが行う(自動では申請しない)。
