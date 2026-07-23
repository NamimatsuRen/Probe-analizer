# GitHub Issue backlog

Notion「段階的GUI開発計画｜Level 1–2で土台を確立する」を、GitHubへ投入できる大きさへ分解したバックログ。

## 状態

- `implemented-local`: 現在のブランチで実装済み。PR merge時にcloseする。
- `next`: このブランチまたは直後に着手する。
- `backlog`: 依存Issueの完了後に着手する。
- GitHub Issue番号は連携再認証後に付与する。ここでは安定したローカルIDを使う。

## 推奨label

- 種別: `type: epic`, `type: task`, `type: bug`, `type: docs`, `type: test`
- Level: `level: 0` ～ `level: 8`
- 領域: `area: domain`, `area: reader`, `area: ui`, `area: performance`, `area: quality`
- 優先度: `priority: p0`, `priority: p1`, `priority: p2`
- 状態補助: `blocked`, `needs-data`, `needs-usability-test`

---

## Milestone: Level 0 — 開発基盤

### P0-01 `[Epic] Level 0: 1コマンドで起動・検証できる開発基盤`

- Status: `implemented-local`
- Labels: `type: epic`, `level: 0`, `priority: p0`
- 目的: 新規環境でセットアップ、起動、全確認を同じ手順で再現できる。
- 受入条件:
  - `uv sync --extra dev` が成功する。
  - `python -m probe_app` の入口がある。
  - test/lint/type checkのコマンドがREADMEにある。
  - P0-02～P0-07が完了する。

### P0-02 `[Task] src layoutとアプリentry pointを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 0`, `area: domain`, `priority: p0`
- Scope: `pyproject.toml`、`src/probe_app`、`__main__.py`、console script。
- 受入条件:
  - editable install後に`python -m probe_app`でentry pointへ到達する。
  - package外の相対importに依存しない。

### P0-03 `[Task] uvによる依存・開発ツール管理を固定する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 0`, `area: quality`, `priority: p0`
- Scope: runtime依存、dev依存、Python下限、`uv.lock`。
- 受入条件:
  - PySide6、PyQtGraph、NumPyをruntime依存として宣言する。
  - pytest、pytest-qt、ruff、mypyをdev依存として宣言する。
  - lockfileから再現可能にinstallできる。

### P0-04 `[Task] GitHub Actionsでtest/lint/type checkを実行する`

- Status: `implemented-local`（remote実行はPR後）
- Labels: `type: task`, `level: 0`, `area: quality`, `priority: p0`
- Depends on: P0-03
- 受入条件:
  - pull requestとmain pushで起動する。
  - GUI startup testをoffscreenで実行する。
  - 最小権限`contents: read`で動く。
  - 依存をlockfileからinstallする。

### P0-05 `[Task] 例外境界とアプリログを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 0`, `area: quality`, `priority: p1`
- 受入条件:
  - 未処理例外をログへ記録する。
  - 利用者には内部tracebackではなくログ場所を案内する。
  - readerの失敗原因をログから追える。

### P0-06 `[Test] 小・圧縮・破損データfixtureを作る`

- Status: `implemented-local`
- Labels: `type: test`, `level: 0`, `area: quality`, `priority: p0`
- 受入条件:
  - little/big endianを生成できる。
  - `.dat`と`.dat.gz`を生成できる。
  - 欠損・短い波形・不完全ヘッダーを再現できる。
  - 実験データそのものをrepositoryへ入れない。

### P0-07 `[Docs] architecture・data contract・ADRを記録する`

- Status: `implemented-local`
- Labels: `type: docs`, `level: 0`, `priority: p1`
- 受入条件:
  - 層の責務と依存方向が説明されている。
  - JSONを入力境界にしない決定がADRにある。
  - background loadingと競合防止がADRにある。
  - Level 1の単位変換範囲が明記されている。

### P0-08 `[Release] Level 0基盤版をtagする`

- Status: `backlog`
- Labels: `type: task`, `level: 0`, `priority: p1`
- Depends on: P0-01, PR merge
- 受入条件:
  - main上のCIがgreen。
  - `level-0` tagとrelease noteがある。
  - 起動・検証手順がrelease noteから辿れる。

---

## Milestone: Level 1 — フォルダからRaw波形を表示

### L1-01 `[Epic] Level 1: フォルダを選択してRawデータを表示する`

- Status: `next`
- Labels: `type: epic`, `level: 1`, `priority: p0`
- 目的: JSONを作らず、対象フォルダから意図した系列を選び、Raw波形とデータ状態を誤認なく確認する。
- 受入条件:
  - L1-02～L1-25が完了する。
  - L1-26～L1-29の実データ・性能・利用確認でP0問題がない。
  - Level 2の機能を含めない。

### L1-02 `[Task] RawSeriesDescriptorとRawSeriesを定義する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: domain`, `priority: p0`
- 受入条件:
  - series/shot/channel ID、元ファイル、点数、単位を持つ。
  - 時間軸と値配列が1次元かつ同じ長さであることを検証する。
  - GUI型をimportしない。

### L1-03 `[Task] Yokogawa/PANTA ASCIIヘッダーを型付きで解析する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p0`
- 受入条件:
  - BlockSize、VResolution、VOffset、HResolutionを必須検証する。
  - HOffset、DataOffset、Endian、VDataType、単位、日時を読む。
  - 欠損・不正数値へ対象ファイル付きエラーを返す。

### L1-04 `[Task] .hdrと波形ファイルのpair検出を実装する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p0`
- Depends on: L1-03
- 受入条件:
  - 同一ディレクトリ・同一basenameだけを組にする。
  - 優先順は`.wvf`、`.dat`、`.dat.gz`。
  - 拡張子の大文字小文字差を許容する。
  - 対応波形なしを問題一覧へ残す。

### L1-05 `[Task] 選択フォルダ以下を再帰走査してcatalogを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p0`
- Depends on: L1-02, L1-04
- 受入条件:
  - 1 shotフォルダと複数shotの親フォルダを扱う。
  - IDは選択rootからの相対パスで一意になる。
  - 安定した並び順になる。
  - フォルダ選択時に波形本体を読まない。

### L1-06 `[Task] 壊れた系列を隔離しpartial状態を返す`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p0`
- Depends on: L1-05
- 受入条件:
  - 1ファイルの不備で正常系列を失わない。
  - pathと理由を`ScanProblem`へ残す。
  - 0件、部分成功、完全成功を区別できる。

### L1-07 `[Task] .dat/.wvfの16 bit波形readerを実装する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p0`
- Depends on: L1-03
- 受入条件:
  - headerのdata offsetとblock sizeを使用する。
  - `y = resolution × raw + offset`を適用する。
  - 旧reader互換の`t = (n + 1 + HOffset) × HResolution`を作る。
  - 期待点数不足を黙って切り詰めない。

### L1-08 `[Task] .dat.gz波形readerを実装する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p1`
- Depends on: L1-07
- 受入条件:
  - 非圧縮と同じcalibration結果になる。
  - 全展開した一時ファイルを作らない。
  - 短いgzip payloadをエラーにする。

### L1-09 `[Task] endianとVDataTypeを検証する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: reader`, `priority: p0`
- Depends on: L1-07
- 受入条件:
  - little/big endianのIS2を正しく読む。
  - 未対応型は誤読せず明示エラーにする。
  - endianごとの自動テストがある。

### L1-10 `[Task] OpenFolder use caseをJSON非依存で作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: domain`, `priority: p0`
- Depends on: L1-05
- 受入条件:
  - 入力は`Path`とキャンセル関数だけ。
  - config JSONのpath、basename、measurement一覧を要求しない。
  - GUIなしのintegration testから呼べる。

### L1-11 `[Task] アプリ状態を1か所へ集約する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: domain`, `priority: p0`
- 受入条件:
  - idle/loading/ready/empty/partial/cancelled/errorを持つ。
  - folder、catalog、selected seriesの正規ソースが1つ。
  - 未知seriesの選択を拒否する。

### L1-12 `[Task] フォルダ走査をGUIスレッド外で実行する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-10
- 受入条件:
  - Qt thread poolを使う。
  - 成功、失敗、キャンセルを別signalで返す。
  - UI部品をworkerから更新しない。

### L1-13 `[Task] 選択系列の波形読込をGUIスレッド外で実行する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-07
- 受入条件:
  - catalog作成時ではなく系列選択時に読む。
  - 読込中もwindow event loopが動く。
  - 失敗しても別系列を選べる。

### L1-14 `[Task] キャンセルと古い結果の混入防止を実装する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-12, L1-13
- 受入条件:
  - フォルダ走査と系列読込へ停止フラグを渡す。
  - generation IDが現在要求と違う結果を破棄する。
  - フォルダ切替後に旧波形を表示しない。
  - window close時に処理へcancelを通知する。

### L1-15 `[Task] フォルダ選択・再読込・直近フォルダを実装する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- 受入条件:
  - file選択ではなくdirectory選択dialogを使う。
  - 選択中folderが常に見える。
  - 再読込が同じfolderを走査する。
  - 次回dialogは直近folderから始まる。

### L1-16 `[Task] shot/series Data Browserを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-02, L1-05
- 受入条件:
  - shotを親、seriesを子として表示する。
  - channel、点数、単位が一覧で分かる。
  - 現在seriesが1つだけ選択される。
  - 空catalogで古い項目が残らない。

### L1-17 `[Task] Raw Plotを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-13
- 受入条件:
  - timeを横軸、header-calibrated signalを縦軸にする。
  - 軸名と単位を表示する。
  - zoom/pan/auto rangeができる。
  - series切替時にタイトルが更新される。

### L1-18 `[Task] 大規模波形の表示用min/max downsamplingを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: performance`, `priority: p0`
- Depends on: L1-17
- 受入条件:
  - 50,000点以内へ減らす。
  - 先頭・末尾を残す。
  - 狭いspikeを残す。
  - fitting用データを書き換えず表示にだけ使う。

### L1-19 `[Task] 選択系列のmetadata panelを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p1`
- 受入条件:
  - series、shot、元ファイル、点数、日時、形式を表示する。
  - 読込後に時間・信号範囲を表示する。
  - 未読込と欠損値を`—`で区別する。

### L1-20 `[Task] 読込・空・部分失敗・エラーstatus panelを作る`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-06, L1-11
- 受入条件:
  - loading中だけ進捗表示を出す。
  - emptyとerrorを同じ文言にしない。
  - partialの件数と詳細を確認できる。
  - エラー文に次の操作を含める。

### L1-21 `[Task] folder切替・reload時のstate resetを保証する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: ui`, `priority: p0`
- Depends on: L1-14, L1-15
- 受入条件:
  - browser、plot、metadataを先にclearする。
  - 下位選択を無効化する。
  - old catalog/seriesが一瞬表示されない。

### L1-22 `[Task] fatal errorを利用者向け説明とlogへ分離する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: quality`, `priority: p1`
- 受入条件:
  - 画面は原因の要約と次の行動を示す。
  - tracebackはlogへ残す。
  - 1系列のfailureでアプリを終了しない。

### L1-23 `[Test] header/scanner/reader/state/downsamplingのunit test`

- Status: `implemented-local`
- Labels: `type: test`, `level: 1`, `area: quality`, `priority: p0`
- 受入条件:
  - 正常・missing pair・broken header・truncated dataを含む。
  - endianとgzipを含む。
  - state transitionとspike保持を含む。

### L1-24 `[Test] folder→catalog→waveform integration test`

- Status: `implemented-local`
- Labels: `type: test`, `level: 1`, `area: quality`, `priority: p0`
- Depends on: L1-10
- 受入条件:
  - nested folderからseriesを選びcalibrated値まで確認する。
  - JSON fixtureを入力に使わない。

### L1-25 `[Test] Level 1 window startup test`

- Status: `implemented-local`
- Labels: `type: test`, `level: 1`, `area: quality`, `priority: p0`
- 受入条件:
  - headless環境でwindowを生成できる。
  - toolbar、browser、plot、statusを含むcentral widgetがある。
  - CIで実行される。

### L1-26 `[Test] 既存PANTA実データでfolder scanと1系列読込を確認する`

- Status: `implemented-local`
- Labels: `type: test`, `level: 1`, `area: reader`, `needs-data`, `priority: p0`
- Depends on: L1-05, L1-07
- 受入条件:
  - 旧JSONを渡さず`data/raw/<date>`を選ぶ。
  - 認識series数が`.hdr + waveform` pair数と一致する。
  - 600,000点系列の先頭・末尾・単位が旧readerと説明可能な差に収まる。
  - 実データをcommitしない。

### L1-27 `[Perf] small/medium folderのscan・first plot時間を計測する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: performance`, `priority: p1`
- Depends on: L1-26
- 受入条件:
  - fixture規模と測定環境を記録する。
  - folder scan、1系列read、downsamplingを分けて測る。
  - Level 1 KPIとの距離をissueへ記録する。

### L1-28 `[Perf] medium folderのpeak RSSを計測する`

- Status: `implemented-local`
- Labels: `type: task`, `level: 1`, `area: performance`, `priority: p1`
- Depends on: L1-26
- 受入条件:
  - catalogのみ、1系列表示後、series切替後を分ける。
  - 全series配列を保持していないことを確認する。
  - 設定した上限と実測を記録する。

### L1-29 `[UX] 代表5タスクでLevel 1利用テストを行う`

- Status: `backlog`
- Labels: `type: task`, `level: 1`, `area: ui`, `needs-usability-test`, `priority: p0`
- Depends on: L1-26
- 受入条件:
  - 3～5人または最低1人の観察テストを行う。
  - folder選択、指定shot、指定series、error理解、reloadを課題にする。
  - 成功率、時間、迷った箇所を記録する。
  - P0問題があればLevel 2へ進まない。

### L1-30 `[Release] Level 1 Raw Browser安定版をtagする`

- Status: `backlog`
- Labels: `type: task`, `level: 1`, `priority: p1`
- Depends on: L1-01
- 受入条件:
  - Level 1受入条件がすべて確認済み。
  - main CIがgreen。
  - `level-1` tagとrelease noteを作る。
  - Level 2非ゴールがrelease noteにある。

### L1-31 `[Research] Yokogawa HOffsetの単位と時間原点を確認する`

- Status: `backlog`
- Labels: `type: docs`, `level: 1`, `area: reader`, `priority: p2`
- 目的: 旧readerの`(n + 1 + HOffset) × HResolution`と、ファイル形式仕様上の時間軸を区別する。
- 受入条件:
  - 使用DAQの公式仕様または既知信号から`HOffset`の単位を確認する。
  - 現行データで旧/仕様準拠の差を数値化する。
  - 変更する場合はmigration noteとgolden testを用意する。

---

## Milestone: Level 2 — Sweep分割と連動表示

### L2-01 `[Epic] Level 2: RawをSweepへ分割しI–Vとして確認する`

- Status: `backlog`
- Labels: `type: epic`, `level: 2`, `priority: p0`
- Depends on: L1-30
- 受入条件: L2-02～L2-20完了、Level 1回帰100%、基盤レビュー通過。

### L2-02 `[Task] series role(current/sweep voltage) domain modelを定義する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p0`
- 受入条件: basenameへ固定せずroleを割り当てられる。未割当を表現できる。

### L2-03 `[Task] currentとsweep voltageの役割割当UIを作る`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p0`
- Depends on: L2-02
- 受入条件: 同一shotのseriesから2役を選び、現在の割当が常に見える。

### L2-04 `[Task] チャンネルごとのscale・sign・単位変換を定義する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p0`
- Depends on: L2-02
- 受入条件: 旧`current × 1/20`、`sweep × 100`を明示設定として再現し、Raw値と混同しない。

### L2-05 `[Task] role/scale設定をfolder入力と分離して保存・復元する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p1`
- Depends on: L2-03, L2-04
- 受入条件: folder選択にJSON作成を要求しない。保存失敗でもRaw閲覧を妨げない。

### L2-06 `[Task] Sweep domain modelと不変条件を定義する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p0`
- 受入条件: source series、index境界、方向、time、voltage、currentを持つ。境界規則を明記する。

### L2-07 `[Task] current/sweepの時間軸整合規則を実装する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p0`
- Depends on: L2-04, L2-06
- 受入条件: sampling違い、開始offset違い、範囲外を明示的に扱う。

### L2-08 `[Task] legacy sweep分割を純粋関数として再現する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p0`
- Depends on: L2-06, L2-07
- 受入条件: GUIなしで入力2系列からSweep列を返す。パラメータと失敗理由が型付けされる。

### L2-09 `[Test] golden dataでSweep数・境界・方向を固定する`

- Status: `backlog`
- Labels: `type: test`, `level: 2`, `area: quality`, `priority: p0`
- Depends on: L2-08
- 受入条件: 代表shotの期待境界、許容sample誤差、上昇/下降を記録する。

### L2-10 `[Task] Sweep分割をbackground実行しcancel可能にする`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p0`
- Depends on: L2-08
- 受入条件: Level 1と同じgeneration保護を使用し、series切替後の旧結果を捨てる。

### L2-11 `[Task] Sweep Browserを作る`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p0`
- Depends on: L2-06
- 受入条件: 番号、方向、開始/終了time、点数、voltage範囲を表示する。

### L2-12 `[Task] Raw時系列上へ選択Sweep区間をhighlightする`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p0`
- Depends on: L2-11
- 受入条件: Browser選択と同時更新し、元seriesのどこか説明できる。

### L2-13 `[Task] 選択SweepのI–V plotを作る`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p0`
- Depends on: L2-07, L2-11
- 受入条件: voltage-current軸、単位、方向、元seriesを表示する。

### L2-14 `[Task] 前/次Sweep navigationを作る`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p1`
- Depends on: L2-11
- 受入条件: keyboard/buttonの規則が一致し、端で範囲外へ進まない。

### L2-15 `[Task] 短い・異常・未分割区間を理由付きで表示する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `priority: p0`
- Depends on: L2-08
- 受入条件: 異常データを黙って消さず、valid Sweepと区別する。

### L2-16 `[Task] 上位選択変更時の下位selection reset規則を実装する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: domain`, `priority: p0`
- 受入条件: folder→shot→series→Sweepの無効化規則を1か所でテストする。

### L2-17 `[Test] Raw highlightとI–Vの対応E2E test`

- Status: `backlog`
- Labels: `type: test`, `level: 2`, `area: quality`, `priority: p0`
- Depends on: L2-12, L2-13
- 受入条件: golden Sweep選択で表示区間とI–V配列が一致する。

### L2-18 `[Perf] Sweep切替200 ms目標を計測する`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: performance`, `priority: p1`
- Depends on: L2-13
- 受入条件: plot更新と再計算を分離計測し、目標未達の原因を記録する。

### L2-19 `[UX] Sweep対応理解の利用テストを行う`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `area: ui`, `needs-usability-test`, `priority: p0`
- Depends on: L2-17
- 受入条件: 指定Sweep到達、Raw上位置、方向の正答率を測る。

### L2-20 `[Review] Level 2基盤レビューと安定版tag`

- Status: `backlog`
- Labels: `type: task`, `level: 2`, `priority: p0`
- Depends on: L2-01
- 受入条件:
  - domain/analysisがPySide6をimportしない。
  - selectionの正規ソースが1つ。
  - Level 1–2 E2Eが100%成功。
  - Level 3の仮解析panelを1つ差し込み、既存readerを変更しない。

---

## Milestones: Level 3以降

以下のEpicは、Level 2基盤レビュー後に各々を同じ粒度へ分解する。

| ID | Issue title | 主な子Issue |
|---|---|---|
| L3-01 | `[Epic] Level 3: 平滑化・微分を比較表示する` | SG設定、Raw/Filtered契約、dI/dV、表示切替、golden test、性能 |
| L4-01 | `[Epic] Level 4: VfとPhi候補を根拠付きで選択する` | zero crossing、log fit、Fit1探索、filtered derivative、raw multiscale、候補UI、品質 |
| L5-01 | `[Epic] Level 5: 飽和域fitとIsat/R/Kを確認する` | ion/electron範囲、robust fit、外挿、R/K、範囲編集、再計算境界 |
| L6-01 | `[Epic] Level 6: Ti model fitと目的関数を確認する` | PANTA model、1D optimization、simple estimate、目的関数plot、境界解、品質 |
| L7-01 | `[Epic] Level 7: shot/sweep summaryと除外を扱う` | K shot中央値、4方式比較、手動除外、position summary、平均規則 |
| L8-01 | `[Epic] Level 8: 保存・Export・再現性・配布` | project format、analysis provenance、CSV/figure export、再現test、macOS/Windows配布 |

---

## GitHub投入順

1. P0-01、L1-01、L2-01をEpicとして作る。
2. P0-02～P0-08を作り、P0-01へtask listでリンクする。
3. L1-02～L1-30を作り、L1-01へtask listでリンクする。
4. 現在branchで実装済みのIssueはPRの`Closes`へ列挙し、mergeでcloseする。
5. L2-02以降はL1-29の利用テストを通過するまで着手しない。
6. L3以降はEpicだけ作成し、Level 2レビュー後に子Issueを追加する。
