# Export論文図ビルダー仕様

- Date: 2026-07-27
- Related: GitHub #93, #100
- Status: Level 8実装前の操作・データ契約

## 1. 目的と境界

Exportは解析済み結果から論文用の図を構成する場所であり、前処理、`V_f`、`Phi`、飽和域、
`T_i`、品質判定を実行・変更しない。画面を開く、対象を選ぶ、styleを変える、previewする、
ファイルを保存する、という操作は`AnalysisResultStore`を書き換えない。

保存機能は次の2系統に分ける。

| 系統 | 目的 | 内容 |
|---|---|---|
| analysis session保存 | 解析作業を再開する | 選択、入力Revision、解析設定、候補、採否、結果、品質、除外 |
| figure bundle出力 | 論文図を再生成する | SVG/PDF/PNG、source CSV、manifest |

figure bundleはsessionの代わりではない。逆にsession保存だけでは、論文の軸範囲、色、panel構成、
採用点を固定できない。

## 2. 3つの具体的な論文図ケース

### ケースA: 1 SweepのI–Vとfit根拠

- 対象: 1 shot、1 Sweep、RawまたはFiltered、採用した1–2方式
- panel A: I–V、採用点、`V_f`、`Phi`、飽和域fit、PANTA model
- panel B: `dI/dV`または目的関数
- 必須根拠: Sweep source sample範囲、時間補正、SG設定、fit範囲、採用候補、Revision
- 主成果物: SVG/PDF。PNGは投稿確認用、CSVは描画した線・点をlong形式で保存

このケースから、単一Sweep選択、Raw/Filtered、fit根拠、取得点とmodel線を区別するstyle、
panel間で共有するRevisionが必要になる。

### ケースB: 同一shot内の`T_i` / `Phi`推移

- 対象: 1 shot、複数Sweep、最大4方式
- panel A: Sweep No.に対する`T_i`
- panel B: Sweep No.に対する`Phi`
- 要確認は輪郭またはmarkerを変え、除外は灰色の参考点として任意表示
- stale/errorは初期選択しないが、件数と理由を警告に残す
- 主成果物: PDF/SVG、採用値CSV、品質・除外理由を含むmanifest

このケースから、単一Sweepの共有選択と別の`ExportSelection`、方式比較、採用／除外状態、
欠損値を線で補間しない規則が必要になる。

### ケースC: 位置依存とshot比較

- 対象: 複数shot、位置、採用方式
- panel A: 位置に対する`T_i`
- panel B: 位置に対する`Phi`または`K`
- 誤差量が保存されている場合だけerror barを描く
- 誤差量がない点はmarkerだけ描き、`0`のerror barを捏造しない
- 主成果物: double-column PDF/SVG、集約前の点と集約後の値を分けたCSV

このケースから、位置scope、集約値の分母、誤差の由来、複数shotと複数方式の表示上限が必要になる。

## 3. 対象選択

`ExportSelection`はData/Analysisの`selected_sweep_id`から独立させ、次を明示する。

- folder identity
- shot、位置、Sweep
- 方式
- Raw / Filtered
- 除外結果を含めるか
- current revisionだけに限定するか

初期選択は`current revision`と一致する`valid` / `review`だけとする。次の結果は一覧から消さないが、
初期選択しない。

| 状態 | 初期選択 | 表示 |
|---|---:|---|
| valid / review + current revision | する | 通常表示 |
| not run / running | しない | 未確定理由 |
| stale | しない | 再計算理由 |
| bad / error | しない | 品質・失敗理由 |
| excluded | しない | 除外理由 |

利用者が除外結果を明示的に採用する場合、manifestへその事実と除外理由を残す。

## 4. Figure recipe

図種はI–V、fit、Sweep推移、位置依存、方式比較を安定IDで保持する。各panelは次を持つ。

- panel IDと図種
- title
- X/Y軸名、単位、linear/log、手動範囲
- legend表示
- error bar表示
- 系列ごとの色、線種、marker、線幅
- figureの物理サイズ、dpi、panel preset

自由配置canvasではなく、論文1段、論文2段、2 panel、4 panelのtemplate-firstとする。任意配置は
同じ図の再現性と操作の単純さが確認できてから追加する。

1 figureあたりの既定上限は4 panel、12系列、4方式とする。超える場合は自動で詰め込まず、
図を分ける案内を表示する。

## 5. Renderer方針

画面上のQt/Matplotlib plotをそのまま画像保存せず、manifestとsource dataを入力にする
専用Export rendererを設ける。

```text
AnalysisResultStore（read only）
  └─ ExportSelection
       └─ source table + ExportManifest
            └─ dedicated paper renderer
                 ├─ SVG / PDF
                 └─ PNG
```

理由は、画面用の間引き、highlight、暗黙の軸autoscale、widgetサイズを論文図へ混入させないため。
同じmanifestとsource table、renderer version、code versionから同じ図を再生成できることを
回帰testで固定する。

## 6. 出力bundle

1回の出力を同じbasenameのbundleにする。

```text
107844_001_ti_trend.svg
107844_001_ti_trend.pdf
107844_001_ti_trend.png
107844_001_ti_trend.csv
107844_001_ti_trend.manifest.json
```

- SVG/PDF: 投稿・編集用vector
- PNG: 指定dpiの確認・投稿用raster
- CSV: 図に実際に使用した点と線。状態、方式、単位、panel IDを含む
- manifest: selection、figure recipe、provenance、成果物名

basenameにpath separatorを許可しない。既存bundleと同名の場合は、暗黙に上書きも自動連番化も
せず、対象ファイルを列挙して確認する。途中失敗時は完成済みbundleとして扱わない。

## 7. Manifestと再現性

manifestは少なくとも次を保存する。

- 入力identityと各Sweep ID
- Analysis Revision key
- 解析設定
- algorithm version、analysis schema version、code version
- 採用点ID
- 除外を含めた場合の理由
- figure/panel/axis/style/error bar設定
- renderer versionとmanifest schema version
- 出力artifact一覧

時刻やランダム値を再現recipe本体へ混ぜない。同一recipeをcanonical JSONへ変換したhashを
`manifest_id`とし、同じ入力が同じIDになることを単体testで保証する。作成時刻が必要なら、
再現recipeとは別の監査metadataとして保存する。

## 8. 現在のUI shell

Issue #100では次を実装する。

- Exportをplaceholderではなく独立workspaceにする
- 図種と論文presetを選べる骨格
- current revisionのvalid/reviewだけを初期check
- stale/error/excluded/not-runを理由付きで残す
- SVG/PDF/PNG/CSV/manifest bundleを固定表示
- rendererを構築せず、出力ボタンをLevel 8まで無効にする

これにより、Export画面を開いてもreader、前処理、fit、rendererは起動しない。

## 9. Level 8受入条件

- ケースA–Cを同じmanifest契約で表現できる
- vector/raster/source/manifestのbundleを作成できる
- stale・除外・品質警告が消えない
- error barがないデータを0誤差として描かない
- Export操作が解析値とRevisionを変更しない
- 同じmanifestとsource dataから同じ図を再生成できる
- analysis session保存とfigure bundle出力が別操作である
- overwrite確認と部分失敗時の扱いが自動testされる
