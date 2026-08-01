# Architecture

## 目的

各Levelで「起動できる・操作できる・検証できる」アプリを保ち、解析機能を縦方向に追加する。

```text
利用者の操作
  ↓
application/use_cases
  ↓
domain models ← infrastructure/readers
  ↓
application/state
  ↓
ui/widgets
  ↓
画面上の結果
```

## 依存方向

- `domain`: GUIとファイル形式を知らない。
- `application`: domainと、ユースケースに必要な境界だけを知る。
- `infrastructure`: フォルダ、PANTA/Yokogawaファイルなど外部形式を解釈する。
- `ui`: applicationを呼び出し、domainの結果を表示する。
- `analysis`: GUI非依存の平滑化・微分と、Level 4以降の解析を保持する。PySide6をimportしない。

## Level 1の主要コンポーネント

| コンポーネント | 責務 |
|---|---|
| `FolderScanner` | 選択フォルダ以下のヘッダーと波形を組み合わせ、軽量カタログを作る |
| `PantaHeader` | Yokogawa ASCIIヘッダーを検証し、型付き値へ変換する |
| `PantaRawReader` | 必要になった1系列だけを読み、物理値と時間軸へ変換する |
| `OpenFolder` | フォルダを開く操作のユースケース |
| `AppState` | idle/loading/ready/empty/partial/cancelled/errorを一元管理する |
| `FolderScanTask` | フォルダ走査をGUIスレッドの外で実行する |
| `SeriesLoadTask` | 選択系列の読込をGUIスレッドの外で実行する |
| `SplitSweeps` | 割り当て済み2系列を読み、時間軸整合からSweep分割まで実行する |
| `SweepSplitTask` | `SplitSweeps`をGUIスレッドの外で実行する |
| `SweepSplitPanel` | JSONに代わる明示パラメータ、実行、キャンセル、結果状態を表示する |
| `MainWindow` | 操作イベントと状態・表示を接続する |

## メモリ方針

- フォルダ選択時は波形本体を読まず、descriptorだけ作る。
- 波形は選択された1系列だけ読む。
- 新しい系列を選んでも、古いバックグラウンド結果はgeneration IDで破棄する。
- プロットには最大50,000点を渡し、各区間の最小値・最大値を残す。
- 全系列の巨大なNumPy配列をアプリ状態へ保持しない。

## 非同期処理

Qtのthread poolを使用する。フォルダ走査、Raw系列読込、Sweep分割は別々のgeneration IDで
保護する。キャンセルは協調的であり、処理へ停止フラグを渡す。ファイル読込やNumPy演算を
途中で完全に強制停止できない場合も、キャンセルまたは系列切替後に返った旧generationの
結果は状態・画面へ反映しない。

Sweep分割のアプリ状態はフォルダ読込状態から分け、`idle / ready / running / succeeded /
cancelled / error`として保持する。これにより分割失敗やキャンセルが、正常に読み込めている
Rawカタログを消さない。

## Level 2で確立した境界

Level 2では次を追加した。

1. フォルダから見つけた系列へ `current` / `sweep_voltage` の役割を割り当てる。
2. 役割と装置固有倍率を、JSON入力ではなく画面操作と保存可能な設定として扱う。
3. 2系列を時間軸上で整合させ、Sweepへ分割する。
4. Raw時系列の選択区間とI–Vプロットを連動させる。

### Level 2 domain foundation

Level 2の計算境界はGUIから独立させる。

```text
RawSeries
  └─ SeriesRoleAssignments.prepare()
       └─ PhysicalSignal (current[A] / sweep_voltage[V])
            └─ align_current_and_voltage()
                 └─ AlignedSignals
                      └─ split_legacy_sweeps()
                           └─ tuple[Sweep, ...]
```

- `SeriesRoleAssignments` はフォルダ走査結果へ後から役割を与える。basenameから役割を推測しない。
- 装置倍率と符号は `SignalTransform` に明示し、header-calibrated Raw配列を変更しない。
- 電流は手動時間補正を反映して掃引電圧の時間軸へ補間する。正値は後ろのcurrentを参照し、
  共通時間範囲外へは外挿しない。
- `Sweep.time_s`はSweep電圧基準を維持し、適用済み補正は`Sweep.current_time_offset_s`へ保持する。
  current Raw上の対応範囲は`Sweep.current_time_range_s`から表示する。
- `Sweep` のsource境界は半開区間 `[start, stop)` とする。
- `Sweep` 配列はRaw上の位置を失わないよう取得順で保持する。
- 解析用の電圧昇順配列は `Sweep.iv_voltage_v` / `iv_current_a` から取得する。
- 分割条件の不備は空配列にせず、型付きの失敗理由として返す。

### 役割設定の保存境界

役割割当UIは、選択中Raw系列とは別の `SeriesRoleAssignments` として状態管理する。

```text
RoleAssignmentPanel
  └─ AppState.set_role_assignments()
       └─ RoleAssignmentStore (application port)
            └─ QSettingsRoleAssignmentStore (infrastructure)
```

- currentとsweep voltageは同じshot内の異なるseriesだけを選択できる。
- 既定の追加倍率は旧コード互換値を表示するが、役割を選ぶまでは適用しない。
- 保存keyは正規化したfolder pathとshot IDのhashで分離する。
- 保存先はOSのアプリ設定であり、測定フォルダへJSONやsidecarを作らない。
- 保存設定内のseriesが現在のfolderに存在しなければ、そのroleだけ未割当へ戻す。
- 読込・保存エラーは役割パネル内へ表示し、Raw閲覧は継続する。
- 一括適用は、source shotで選んだ各roleの`channel_id`を対象shot内で照合する。`series_id`を
  そのままコピーしない。
- 適用scopeは現在のshot、catalog順で現在以降、catalog内の全shotの3種類とする。
- roleごとのchannelが欠落または重複する対象shotは、部分保存せずshot全体をスキップする。
  これにより既存の保存設定を誤って上書きしない。

この接続後も、役割を設定せずフォルダを選ぶだけでLevel 1のRaw閲覧ができる性質は変わらない。

### Sweep分割の垂直接続

```text
SweepSplitPanel
  └─ SweepSplitRequest
       └─ SweepSplitTask (Qt thread pool)
            └─ SplitSweeps
                 ├─ PantaRawReader × 2
                 ├─ SeriesRoleAssignments.prepare()
                 ├─ align_current_and_voltage()
                 └─ split_legacy_sweeps()
                      └─ SweepSplitResult
                           └─ AppState.apply_sweep_result()
```

- 入力はcatalog内のdescriptor、保存済み役割、画面で指定した分割条件とcurrent時間補正だけで
  構成する。
- JSON設定やbasename規則を処理開始条件にしない。
- seriesまたはroleが変わると、保持中のSweepと進行中taskを無効化する。
- 完全なrole設定を選択・復元したときは、既定ONの自動分割を400 msのdebounce後に開始する。
  対象shotが切り替わった場合は待機中の処理を破棄する。
- 一括適用は対象shotの設定を保存するが、背景で全shotの巨大配列を同時に読み込まない。
  そのshotを表示した時点で保存設定を復元し、自動分割する。
- 周期点数、sample範囲、current時間補正の編集中は自動分割しない。利用者が明示的に
  再分割するため、連続入力でreader・補間・分割を繰り返さない。
- taskのcallbackはgeneration一致時だけ`AppState`へ適用する。
- 分割の失敗・キャンセル後もcatalog、Raw表示、役割設定は維持する。

### Sweep選択とLevel 3解析境界

- Sweep選択IDの正規ソースは`AppState.selected_sweep_id`とする。
- folder、shot/role、seriesの上位選択が変わると、Sweep結果と選択を同時に無効化する。
- 選択済み`Sweep`をRaw highlight、I–V、平滑化・微分へ渡し、各表示が別のIDを持たないようにする。
- I–Vを上部の主表示とする。下部は水平分割し、左2/3のRaw波形を常時表示、右1/3のタブへ
  Sweep分割・一覧・平滑化/微分・Raw情報を配置する。
- Raw波形と右側操作タブを別widget階層に置き、設定・一覧の切替中も選択SweepのRaw highlightを
  維持する。
- Raw highlightは表示中系列がcurrentなら補正後のcurrent参照時刻、sweep voltageまたは
  その他の系列ならSweep電圧基準時刻を使う。I–Vと選択情報には適用済み補正値を明示する。
- current時間補正の`valueChanged`はRaw highlightの表示座標だけを更新する。未適用プレビュー中は
  `AppState.sweeps`、I–V、前処理結果、background task generationを変更しない。
- 補正値は「今すぐ分割／再分割」で初めてrequestへ取り込み、成功後にプレビューを適用済みへ移す。
- I–Vの既定対象はsample半開区間`[200000, 500000)`、Raw表示はreaderが返した全時間範囲とする。
- domainの時間単位は秒を維持し、Raw軸・metadata・Sweep一覧・除外区間・説明文はUI境界でmsへ変換する。
- `analysis`は`domain`だけに依存し、PySide6・pyqtgraph・readerをimportしない。
- Level 3の数値処理は`analysis`へ追加し、`ui`側panelから選択済み`Sweep`を渡す。

詳細なGate結果は
[Level 2基盤レビュー](reviews/level2-foundation-2026-07-24.md)に記録する。

## Level 3で追加した境界

```text
AppState.selected_sweep_id
  └─ Sweep
       └─ preprocess_sweep()                  analysis（GUI非依存）
            └─ PreprocessedSweep
                 ├─ SweepIVPlot               Raw / Filtered / dI/dV
                 └─ PreprocessingPanel        設定・実使用窓・警告
```

- `SavitzkyGolaySettings`は利用者が指定した窓と次数だけを保持する。
- `safe_savgol_window()`は実データ点数から実際に使う奇数窓を決める。
- `PreprocessedSweep`は同じ電圧軸上のRaw、Filtered、`dI/dV`と、計算条件を保持する。
- 設定変更は選択済み`Sweep`だけを同期計算し、reader・時間軸整合・Sweep分割を呼び直さない。
- folder、role、seriesの変更で`AppState.selected_sweep_id`が消えると、前処理結果も同時に消す。
- 10,000点・窓501の実測中央値は2.181 msであり、GUIスレッド内計算でも200 ms目標に十分な
  余裕がある。点数・窓が大幅に増える場合はbackground化を再評価する。
- architecture testで`domain`と`analysis`からPySide6・pyqtgraphへの依存がないことを固定する。

## Level 4以降のワークスペース情報設計

Level 4–8の機能をLevel 2の小タブへ追加し続けず、右側メイン領域を次の4ワークスペースへ
分ける。詳細な決定理由と状態表は
[ADR 0004](adr/0004-workspace-information-architecture.md)を参照する。

```text
共有コンテキスト（左側）
  Folder / Shot / Series / 系列役割
             │
             └─ AppState.selected_sweep_id（単一Sweep選択の正規ソース）

右側の最上位ワークスペース
  ├─ データ確認  Raw全波形 / Raw I–V / Sweep分割・一覧・Raw情報
  ├─ 解析        前処理 / V_f・Phi / saturation / T_i / quality
  ├─ サマリー    shot・複数shot・位置の比較、除外、drill-down
  └─ Export      論文図preview、vector/raster、CSV、manifest
```

- 起動時は「データ確認」を開く。
- データ確認にはFiltered、`dI/dV`、fit結果を表示しない。
- タブ切替は計算トリガーにしない。計算は明示操作からだけ開始する。
- Data/Analysisは選択Sweepを扱う。Summary/Exportの集約scopeは別の型として扱う。
- Summaryの点から解析へ移動するときだけ、対象Sweepを共有selectionへ設定する。
- stale/error/excluded/partial-successを結果なしとして黙って落とさない。
- current revisionと一致しない結果は既定のSummary集計とExport対象から除外する。

解析ワークスペースは3案を代表タスクで比較し、2026-07-27の利用者確認で、
段階レール・中央キャンバス・右インスペクタを骨格にする推奨構成を採用した。
通常時は工程を順に確認し、必要時だけ中央プロットの大表示と4方式比較へ切り替える。

Level 3–6の解析ワークスペースでは次を実装済みとする。

- 選択Sweepと解析Revision/statusを固定位置へ表示する。
- 左の工程で前処理から品質までの現在地を表示する。
- 中央でRaw/Filtered I–Vと`dI/dV`を表示する。
- 右のインスペクタでSG設定、電位探索範囲、飽和域、`T_i`探索条件を変更する。
- `V_f`と`Phi`の候補を保持し、選択候補の根拠を数値結果・プロットへ反映する。
- 飽和域のロバストfit、`I_sat,i/e`、`R`、`K`を同じRevisionへ記録する。
- PANTAモデルの`T_i` fitと目的関数を表示する。
- 候補や設定の編集、タブ切替では計算せず、明示ボタンからだけ再計算する。
- 工程の未実行、要確認、不適、エラー、staleを別状態として扱う。

### Level 4–6の解析境界

```text
PreprocessedSweep + AnalysisSettings
  └─ estimate_potentials()
       ├─ zero-crossing candidates
       ├─ robust log-fit intersection
       └─ dI/dV peak candidates
            └─ fit_saturation_regions()
                 ├─ ion/electron robust fits
                 └─ I_sat,i/e / R / K
                      └─ fit_panta_temperature()
                           ├─ bounded one-variable optimization
                           └─ objective grid / quality
                                └─ CompleteAnalysisResult
```

- `analysis`層はNumPy・SciPyとdomain型だけに依存し、PySide6・pyqtgraph・readerを知らない。
- 各工程は失敗理由を型付き結果として返し、後段が未確定の場合も空値を正常値として保存しない。
- `AnalysisSettings.as_revision_settings()`は範囲・候補・探索条件を安定した順序へ正規化し、
  同一設定のRevision IDを再現可能にする。
- UIは`CompleteAnalysisResult`をI–V overlay、目的関数、`AnalysisResultStore`へ投影する。
- `V_f`候補変更はpotential以降、飽和域変更はsaturation以降、`T_i`条件変更はtemperature以降の
  再計算を必要とする。現段階では安全側に倒し、Level 4–6の明示実行でまとめて更新する。
- SummaryとExportは保存済み結果を読むだけで、この解析パイプラインを呼び出さない。

比較した3案、代表タスク、採用した組み合わせは
[解析ワークスペース UXプロトタイプ比較](usability/analysis-workspace-prototypes-2026-07-27.md)
に記録する。

### サマリーワークスペースの読取境界

サマリーは`AnalysisResultStore`を読み取るprojectionであり、解析処理の呼び出し元にはしない。

```text
AppState.sweeps + AnalysisResultStore + current AnalysisInputRevision
  └─ build_summary_snapshot()                 application query（副作用なし）
       └─ SummarySnapshot
            ├─ scope / 集計分母 / 方式別統計
            ├─ 全Sweepの状態行
            └─ 4方式のPhi・T_i・K・plot点
                 └─ SummaryWorkspace
                      ├─ 状態件数
                      ├─ T_i / Phi推移・平均
                      ├─ Sweep一覧
                      └─ 解析へのdrill-down
```

- `SummaryScope`はData/Analysisの単一Sweep選択と別の型で保持する。
- 現段階のscopeは読み込んだ現在shot。複数shotと位置は位置metadata契約の確定後に追加する。
- 全Sweepを1行ずつprojectionし、未実行・失敗・stale・除外を暗黙に落とさない。
- 前処理だけ完了し`T_i`工程が未実行のrecordは、サマリーでは「未実行」とする。
- 既定集計はcurrent revisionと一致する`valid` / `review`だけを分母候補にする。
- `T_i`の既定採用範囲は`0 < T_i < 5 eV`、`Phi`は有限値。方式別状態も
  `valid` / `review`である値だけを統計へ使う。
- 対象外だが有限な値は灰色の点として残し、値の存在と不採用を区別する。
- 別Revisionしか存在しないSweepは「再計算必要」として表示し、既定集計には入れない。
- 4方式の安定IDをdomainで定義し、未実装の方式も空欄ではなく「未実行」と表示する。
- 行選択は共有`selected_sweep_id`へ反映し、「解析で確認」で解析タブへ移動する。
- タブ表示・行選択・drill-downはreader、前処理、fitを実行しない。
- current-shotの一括解析は解析ワークスペースの明示ボタンから`AnalysisBatchTask`を起動する。
  完了済みrecordを`AnalysisResultStore`へ順次追加し、Summaryはread-only projectionを再表示する。

詳細は
[サマリーワークスペース状態・集計契約](usability/summary-workspace-contract-2026-07-27.md)
に記録する。

### Exportワークスペースの読取境界

ExportはSummaryと同じread-only projectionを入力にし、単一Sweepの共有selectionとは別の
`ExportSelection`を持つ。表示や図styleの変更を解析処理の呼び出し元にしない。

```text
SummarySnapshot
  └─ build_export_candidates()               application query（副作用なし）
       └─ ExportCandidateSnapshot
            ├─ current revision・valid/reviewを初期選択
            └─ stale/error/excludedを警告付きで保持
                 └─ ExportWorkspace          明示preview・bundle出力

ExportSelection + FigureSpec + Provenance
  └─ ExportManifest（canonical JSON / deterministic ID）
       └─ PaperRenderer（画面widget非依存）
            └─ SVG / PDF / PNG / source CSV / manifest
```

- `ExportSelection`はfolder、shot、位置、Sweep、方式、Raw/Filtered、除外採用を明示する。
- `FigureSpec`は図種、panel、軸、単位、legend、error bar、論文presetを保持する。
- `ExportManifest`はRevision、解析設定、version、採用点、除外理由を保存する。
- project保存とfigure bundle出力は別の責務にする。
- rendererは画面のplotを画像化せず、manifestとsource tableから独立に描画する。
- previewはボタンによる明示更新とし、選択やstyle変更のたびに重い描画を開始しない。
- bundleは一時directoryで全成果物を完成してから移動し、同名出力を暗黙に上書きしない。

### 複数shot・project・監査の境界

```text
AnalysisResultStore
  └─ AnalysisCatalog（shotごとのscalar SummaryRowのみ）
       ├─ loaded-shot summary
       └─ explicit ProbePosition aggregate

AppState + roles + split + catalog + records + metadata + audit
  └─ ProjectDocument schema 1
       └─ ProjectFileStore（temp + fsync + atomic replace）
```

- `ProbePosition`は値とmm／cm／mの単位を持ち、shot名やfolder名から推測しない。
- 複数shot集計は各shot内平均を作った後、shotを等重みで平均する。
- `AnalysisCatalog`とprojectにはRaw配列を保存せず、Revisionとscalar resultだけを保持する。
- project schema 0は1へ移行し、未知の将来schemaは推測せず読込を拒否する。
- 元Rawは外部参照であり、移動時は利用者が新folderを選んで全folder identityを再リンクする。
- 除外、復元、metadata、project保存／読込、Exportはappend-onlyの`AuditTrail`へ記録する。

詳細は
[Export論文図ビルダー仕様](usability/export-figure-builder-spec-2026-07-27.md)
に記録する。

### 4ワークスペースの回帰Gate

- 100回の最上位タブ切替でworker、前処理、fitの開始を0回にする。
- 共有Sweepの正規ソースを`AppState.selected_sweep_id`に限定する。
- folder、role、split、preprocessing、fitの変更ごとに下流だけをstaleにする。
- generation / Revisionが一致しない遅延結果を状態へ反映しない。
- Summary/Exportでstale、error、excludedを黙って落とさず、既定対象からだけ外す。
- 未使用時は解析配列とExport rendererを構築しない。

状態表、性能Gate、macOS手動手順は
[4ワークスペース状態同期・無再計算テスト](testing/workspace-regression.md)
に記録する。
