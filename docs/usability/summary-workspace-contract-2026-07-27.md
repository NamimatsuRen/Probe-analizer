# サマリーワークスペース状態・集計契約

Status: Issue #99 の最初の垂直スライスを実装

## 目的

サマリーは値が得られたSweepだけを並べる結果表ではない。解析の進捗、失敗、古いRevision、
手動除外を含め、shot全体の状態を誤認なく確認し、元のSweepへ戻るための入口とする。

## 現在のscope

- `SummaryScopeKind.CURRENT_SHOT`
- 読み込んだ現在shotの全Sweep
- current revisionのみを既定集計対象とする
- Data/Analysisの単一Sweep選択とは別のscopeとして型定義する

複数shotと位置集計は、位置metadataとLevel 4–6の解析値が揃うLevel 7で追加する。画面のscope欄には
この段階追加を明記し、未実装機能を利用可能に見せない。

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
将来平均値を追加するときは、さらに各方式で有限な`T_i`を持つ行だけを方式別分母とし、その件数を
併記する。

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

## 現在の画面

- 上部: scope、current revision条件、既定集計の分子・分母
- 状態バー: 8状態の件数
- 左: 全Sweepの時間、状態、4方式の値取得数、Revision、理由
- 右: 選択Sweepの4方式比較と「解析で確認」
- 下部: 集計条件と非再計算方針

## 次の段階

- Level 4–6で得た`Phi`、`T_i`、`K`、品質理由を同じcontractへ格納
- 方式ごとの推移プロット
- 大規模shot向け段階読込と表示用downsampling
- 複数shot scope
- 位置metadataがある場合だけ位置依存scope
- 除外・復元操作と監査履歴

除外・復元は解析値の品質状態と混同しない。操作を追加する際は、誰が・いつ・なぜ変更したかを
保存できる契約を先に定義する。
