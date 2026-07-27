# ADR 0004: 4大ワークスペースと解析scope

- Status: Accepted
- Date: 2026-07-27
- Related: GitHub #93, #94, #95, #96, #97

## Context

Level 2–3では、選択SweepのI–Vを主表示にし、下段の小タブへSweep分割、Sweep一覧、
平滑化・微分、Raw情報を並べていた。この構造へLevel 4–8の`V_f`、`Phi`、飽和域fit、
`T_i`、品質、Summary、Exportを同じ粒度で追加すると、次の問題が起きる。

- データ取得の健全性確認と、解析値を確定する操作が同じ画面に混在する。
- Data/Analysisは単一Sweepを扱うが、Summary/Exportはshot、複数shot、位置を扱う。
- タブを開くことが計算開始の契機になると、不要な再計算と古い結果の競合が起きる。
- Summaryや論文図が、現在の入力・設定と一致しない結果を最新として扱う危険がある。
- 解析タブをLevel 4の画面だけで固定すると、Level 5–6の目的関数、部分成功、品質理由を
  追加するときに再設計が必要になる。

## Decision

右側のメイン領域を、次の4つの最上位ワークスペースへ分ける。

| ワークスペース | 主目的 | 既定scope | 変更してよいもの | 主な出力 |
|---|---|---|---|---|
| データ確認 | 入力系列、Sweep境界、Raw I–V形状の確認 | 選択Sweep | 系列役割、時間補正、分割条件、Sweep選択 | Raw全波形、Raw I–V、分割診断 |
| 解析 | 数値処理と候補・fitの採否決定 | 選択Sweep | 前処理、候補、fit範囲、手動override、品質 | `V_f`、`Phi`、飽和量、`T_i`、品質 |
| サマリー | 解析済み結果の比較・除外・追跡 | shot / 複数shot / 位置 | 表示scope、方式、除外状態 | 推移、集約値、有効数、除外理由 |
| Export | 論文図の構成と再現可能な出力 | 明示的に選んだ結果集合 | 図種、軸、style、panel構成 | SVG/PDF/PNG、CSV、manifest |

### Shared context

左側のFolder、Shot、Series、系列役割は4ワークスペースから参照する共有コンテキストとする。
単一Sweep選択の正規ソースは`AppState.selected_sweep_id`だけに置く。各widgetは独自の
selected IDを正規状態として保持せず、`AppState`から描画する。

Summary/Exportが使う集約scopeは単一Sweep選択へ上書きしない。将来の
`SummaryScope` / `ExportSelection`として別の型で表現する。Summary上の点から解析を確認する
場合だけ、その点のSweep IDを共有selectionへ設定して解析ワークスペースへ移動する。

### Navigation and computation

- 起動時は毎回「データ確認」を開く。前回開いていたタブは復元しない。
- 最上位タブの切替は表示切替だけであり、reader、Sweep分割、前処理、fitを開始しない。
- 計算は「実行」「再計算」などの明示操作、またはその操作から作られたapplication use case
  だけが開始する。
- 未使用ワークスペースの重いplotや集約データは、必要になるまで作らない方針を許容する。
- 非同期結果はgeneration/revisionが現在の入力と一致するときだけ状態へ反映する。

### Result readiness

各ワークスペースは次の状態を区別する。

| 状態 | データ確認 | 解析 | サマリー / Export |
|---|---|---|---|
| 未選択 | Folder/系列を選ぶ案内 | Sweep選択を促す | scopeを選べない理由を表示 |
| 未分割 | 分割条件と実行操作 | 分割が必要と表示 | 結果なしとして表示 |
| 未解析 | Raw確認可能 | 実行可能な工程を表示 | 未解析数を明示 |
| running | Rawを維持し進捗表示 | 対象工程を処理中表示 | 完了済み結果だけ表示 |
| valid/review/bad | Raw表示は変えない | 数値・理由・採否を表示 | 状態別に表示・集計 |
| partial success | Raw表示は変えない | 方式別の成功/失敗を表示 | 成功方式と欠損方式を明示 |
| stale | Raw表示は変えない | 再計算が必要な下流工程を表示 | 既定集計・Exportから除外 |
| error | Raw表示を可能な限り維持 | 原因と次の操作を表示 | エラー数を黙って落とさない |
| excluded | Raw確認可能 | 除外理由と復帰操作を表示 | 集計外だが点・行は残す |

## Analysis workspace gate

解析ワークスペースの詳細レイアウトは、このADRでは固定しない。GitHub #96で2〜3案を比較し、
次を満たす案を利用者が承認してからLevel 4–6の最終UIを実装する。

- 4方式の候補を比較できる。
- 現在の工程、採用値、未確定値が分かる。
- fit範囲変更の下流影響を実行前に分かる。
- 目的関数、固定パラメータ、部分成功、品質理由を表示できる。
- Raw/Filtered/log/微分を異なる単位のまま誤認なく比較できる。

## Consequences

### Positive

- 起動直後の画面はRawデータの確認だけに集中できる。
- 解析値を変える操作と、結果を見る・図を作る操作を分離できる。
- タブ切替による不要な全再計算を禁止できる。
- Summary/Exportが参照すべきrevisionを明示できる。
- Level 4–8を既存reader/Sweep domainへ影響させず追加できる。

### Cost

- 同じ選択Sweepを複数ワークスペースへ同期する描画処理が必要になる。
- 解析結果へrevision、stale、partial-successの状態契約が必要になる。
- Summary/Export用の集約scopeを単一selectionとは別に設計する必要がある。
- 解析タブはプロトタイプ検証のGateを通るまで最終実装できない。

## Rejected alternatives

### 小タブを追加し続ける

工程と目的が混在し、Level 6以降で一覧性を失うため採用しない。

### 4タブがそれぞれ独自にFolder/Sweepを選ぶ

表示対象の食い違いと状態重複が起きるため採用しない。

### Summary/Exportを開いたときに不足結果を自動計算する

長時間処理、古いworker結果、意図しない解析条件の採用につながるため採用しない。

### Export画面で解析パラメータも編集する

論文図の調整が解析結果を変える危険があるため採用しない。
