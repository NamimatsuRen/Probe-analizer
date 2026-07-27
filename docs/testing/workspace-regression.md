# 4ワークスペース状態同期・無再計算テスト

- Date: 2026-07-27
- Related: GitHub #93, #101
- Priority: P0

## 1. 固定する境界

「データ確認」「解析」「サマリー」「Export」の最上位タブ切替は、`QTabWidget`の表示変更だけと
する。次を開始してはならない。

- folder scan
- Raw series load
- Sweep split
- Savitzky–Golay前処理
- `V_f` / `Phi`、飽和域、`T_i` fit
- Summary不足値の補完計算
- Export renderer

計算開始はフォルダ選択、Sweep分割実行、前処理再計算、将来のfit実行など、明示操作へ限定する。

## 2. 正規状態と同期

| 状態 | 正規ソース | 表示先 |
|---|---|---|
| folder / shot / series / role | `AppState` | 左共有領域、Data |
| 選択Sweep | `AppState.selected_sweep_id` | Data I–V、Raw highlight、Analysis、Summary drill-down |
| Summary scope | `SummaryScope` | Summary |
| Export対象 | `ExportSelection` | Export |
| 解析結果 | `AnalysisResultStore` + `AnalysisInputRevision` | Analysis、Summary、Export |

Summaryで行を選ぶ場合だけ共有Sweep selectionを更新する。Summaryの集約scopeとExportの複数選択を
単一Sweep selectionへ押し戻さない。

## 3. invalidation表

| 変更 | 無効になるもの | 維持するもの |
|---|---|---|
| folder | catalog以下、全解析結果をstale | 過去recordの監査情報 |
| series / role / scale / sign | Sweep以下、全解析結果をstale | folder catalog |
| split範囲 / 周期 / 時間補正を実行 | Sweep以下、全解析結果をstale | Raw全波形 |
| SG設定を再計算 | preprocessing以降の新Revision | Sweep分割、Raw |
| `V_f` / `Phi`候補 | potential以降 | preprocessing |
| saturation fit範囲 | saturation以降 | preprocessing、potential |
| `K`戦略 | temperature以降 | 前段結果 |
| タブ切替 | なし | 全状態 |

`SweepAnalysisRecord.mark_stale_from()`は変更工程とその下流だけをstaleにする。別generationまたは
別Revisionの遅延結果は`put_if_current()`で破棄する。

## 4. 結果状態

未選択、未分割、未解析、running、valid、review、bad、error、stale、excludedを表示で区別する。
複数方式の一部だけ成功した場合は、成功方式を保持して`partial_success`とし、失敗方式を黙って
消さない。

- Summary既定集計: current revisionのvalid/reviewだけ
- Export初期選択: current revisionのvalid/reviewだけ
- stale/error/excluded: 行を残し、理由を表示
- Export renderer: Level 8まで未構築

## 5. 自動テスト

### offscreen workspace regression

`tests/e2e/test_workspace_regression.py`で次を固定する。

- 100回のタブ切替でthread-pool start 0回
- 100回のタブ切替で`preprocess_sweep` 0回
- generation、task、`AppState` identityが不変
- 4ワークスペースで選択Sweepが一致
- 未解析SweepはExport候補に残るが初期check 0
- 1,000 SweepのSummary/Export projectionが2.5秒以内
- 100回切替が1秒以内
- Python追跡メモリの正方向差分が2 MiB未満
- 未選択時に解析配列とExport rendererを作らない

### domain / application regression

- `tests/unit/test_analysis_result.py`: downstream invalidation、partial success、旧Revision破棄
- `tests/unit/test_app_state.py`: folder/role/series/Sweep reset chain
- `tests/unit/test_summary.py`: stale/excludedを保持し既定集計から除外
- `tests/unit/test_export.py`: stale/error/excludedを保持し初期選択から除外
- `tests/e2e/test_level1_window.py`: Level 1–3操作、遅延Sweep結果の破棄

## 6. 現在の測定

2026-07-27、macOS arm64、Qt offscreen、Python 3.13のローカル環境で測定した。

| シナリオ | 実測 | Gate |
|---|---:|---:|
| 100回切替＋memory監視test全体 | 0.26 s | 1.0 s未満 |
| 1,000 Sweep Summary/Export表示test全体 | 0.06 s | 2.5 s未満 |
| 共有Sweep同期test全体 | 0.04 s | worker 0回 |
| 100回切替のworker / 前処理 | 0 / 0回 | 0 / 0回 |

pytestの1 test call全体時間であり、純粋なタブイベントだけより広い測定である。CIでは絶対時間より、
意図しない計算開始0回を優先する。

## 7. lazy constructionの現段階

最上位workspaceのshell widgetは起動時に構築する。一方、重いデータとrendererは必要になるまで
作らない。

- Data/Analysis plotはSweep未選択時に配列を保持しない。
- 前処理配列は明示再計算後の選択Sweep 1件だけ保持する。
- Summary/Export projectionは数値波形配列を複製しない。
- Export専用rendererはLevel 8まで構築しない。

Level 7で複数shot集約が重くなった場合、shell自体ではなく集約projectionとplot seriesを
初回表示時に遅延作成する。タブ切替を計算トリガーにはしない。

## 8. macOS手動確認

READMEの「macOSでの4ワークスペース手動回帰」に従い、実データ、Activity Monitor、
20往復／100回切替で画面・メモリ・再計算の有無を確認する。
