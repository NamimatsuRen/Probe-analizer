# サマリーワークスペース状態・集計契約

Status: Level 7 current-shot垂直スライス（推移・平均）を実装

## 目的

サマリーは値が得られたSweepだけを並べる結果表ではない。解析の進捗、失敗、古いRevision、
手動除外を含め、shot全体の状態を誤認なく確認し、元のSweepへ戻るための入口とする。

## 現在のscope

- `SummaryScopeKind.CURRENT_SHOT`
- 読み込んだ現在shotの全Sweep
- current revisionのみを既定集計対象とする
- Data/Analysisの単一Sweep選択とは別のscopeとして型定義する

現在shot内のSweep推移と方式別平均までをこの段階の完成範囲とする。複数shotと位置依存集計は、
shotとプローブ位置を結ぶmetadata契約を定義した後に追加する。画面のscope欄にはこの段階追加を
明記し、未実装機能を利用可能に見せない。

## 状態の扱い

各Sweepを必ず1行表示し、次の8状態を件数付きで区別する。

| 状態 | 意味 | 既定集計 |
|---|---|---|
| `not_run` | Phi/T_i工程が未実行。前処理だけ完了した場合も含む | 対象外 |
| `running` | 明示操作で解析中 | 対象外 |
| `valid` | current revisionで利用可能 | 対象 |
| `review` | 利用可能だが確認事項あり | 対象 |
| `bad` | 品質条件を満たさない | 対象外 |
| `error` | 数値計算に失敗 | 対象外 |
| `stale` | 現在設定と異なるRevision | 対象外 |
| `excluded` | 利用者が理由付きで除外 | 対象外 |

既定集計の表示は`対象Sweep数 / scope内全Sweep数`とし、分母条件を画面上に固定表示する。
方式別の平均は、上記に加えて次の条件を満たす値だけを使い、採用数を必ず併記する。

- `T_i`: 有限かつ`0 < T_i < 5 eV`
- `Phi`: 有限値
- 各値を生成した方式自身の状態が`valid`または`review`

標準偏差は採用数が2以上の場合に標本標準偏差を表示し、1点だけの場合は値なしとする。

## 4方式の安定ID

| ID | 表示 |
|---|---|
| `filtered_log_intersection` | Filtered / log交点 |
| `filtered_derivative_peak` | Filtered / dI/dV |
| `raw_log_intersection` | Raw / log交点 |
| `raw_multiscale_derivative` | Raw / 多窓dI/dV |

`Phi [V]`、`T_i [eV]`、`K [V⁻¹]`を方式別に保持する。まだ計算していない方式は0や空文字へ
変換せず、`not_run`と値なしを別々に保持する。`K`は値だけでなくshot中央値か個別値かを
`k_source`で表示する。

## 操作

1. サマリー行を選択すると、Data/Analysisと共有する`selected_sweep_id`を更新する。
2. 「解析で確認」で同じSweepを保持したまま解析ワークスペースへ移動する。
3. 表示、scope変更、行選択、drill-downでは解析を開始しない。
4. 再計算は解析ワークスペースの明示ボタンからだけ行う。

## 一括解析

サマリーを開いても不足値を自動計算しない。現在shotの結果を揃える場合は解析ワークスペースで
「現在のshotを一括解析」を明示的に押す。

- 現在のSG設定、電位探索範囲、飽和域範囲、`T_i`範囲を全Sweepへ適用する。
- 手動で選んだ`V_f`/`Phi`候補IDは別Sweepに存在する保証がないため、Sweepごとに自動選択する。
- GUIスレッド外で1 Sweepずつ処理し、進捗と処理中Sweepを表示する。
- キャンセル時は新しいSweepの開始を止め、完了済みrecordは破棄しない。
- Summary表示・タブ切替・点選択は一括解析の開始条件にしない。

## 現在の画面

- 上部: scope、current revision条件、既定集計の分子・分母
- 状態バー: 8状態の件数
- 「推移・平均」: `T_i`と`Phi`のSweep推移、4方式の平均・標準偏差・採用数
- 色付きの丸: 方式別集計に採用される値
- 灰色の×: 値は存在するが、古いRevision、品質状態、除外、`T_i`上限などで対象外の値
- 「Sweep一覧・詳細」左: 全Sweepの時間、状態、4方式の値取得数、Revision、理由
- 「Sweep一覧・詳細」右: 選択Sweepの4方式比較と「解析で確認」
- 下部: 集計条件と非再計算方針

## 次の段階

- 大規模shot向け段階読込と表示用downsampling
- 複数shot scope
- 位置metadataがある場合だけ位置依存scope
- 除外・復元操作と監査履歴

除外・復元は解析値の品質状態と混同しない。操作を追加する際は、誰が・いつ・なぜ変更したかを
保存できる契約を先に定義する。
