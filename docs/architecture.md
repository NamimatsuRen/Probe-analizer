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
- taskのcallbackはgeneration一致時だけ`AppState`へ適用する。
- 分割の失敗・キャンセル後もcatalog、Raw表示、役割設定は維持する。

### Sweep選択とLevel 3解析境界

- Sweep選択IDの正規ソースは`AppState.selected_sweep_id`とする。
- folder、shot/role、seriesの上位選択が変わると、Sweep結果と選択を同時に無効化する。
- 選択済み`Sweep`をRaw highlight、I–V、平滑化・微分へ渡し、各表示が別のIDを持たないようにする。
- I–Vを上部の主表示、Raw波形を下部タブの補助表示とし、I–Vは設定・一覧操作中も維持する。
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
