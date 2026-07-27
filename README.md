# Probe Analizer

プローブ測定データを、フォルダから直接選んで確認・解析するデスクトップアプリです。

開発ロードマップの **Level 7（現在shotのサマリー）** まで実装済みです。フォルダからRaw波形を確認し、同一shotの
current／sweep voltageを割り当て、Sweep分割、Raw対応表示、I–V確認、平滑化・微分比較、
`V_f`・`Phi`・飽和域・`T_i`の段階解析、Sweep推移と方式別平均の確認まで実行できます。

## 現在できること

- JSON設定ファイルではなく、測定データを含む**フォルダ**を選択
- 選択フォルダ以下の `.hdr` を再帰的に探索
- 同名の `.wvf`、`.dat`、`.dat.gz` を自動で組み合わせ
- shot／系列のツリー表示
- 選択系列のRaw波形、単位、点数、時間範囲、信号範囲を表示
- 大きな波形を表示用に間引き、ピーク形状を保持
- 読込中・空フォルダ・一部失敗・致命的失敗・キャンセルを区別
- フォルダ再読込と直近フォルダの記憶
- 読込処理をバックグラウンドで実行し、古い結果の混入を防止
- 同一shot内の系列をcurrent／sweep voltageへ明示的に割当
- current／sweep voltageごとの倍率・符号を設定
- 役割設定を測定フォルダへ書き込まず、アプリ設定として保存・復元
- 選択したchannel対応を、現在／現在以降／すべてのshotフォルダへ一括適用
- 対応channelがないshotは既存設定を保持したまま理由付きでスキップ
- JSONに代わる画面入力で、1周期の点数、対象sample範囲、current時間補正を指定
- I–V解析範囲の既定値を旧処理と同じ`[200000, 500000)`に限定し、Raw波形は全時間範囲を表示
- 時間補正の変更中はRawハイライトだけを即時プレビューし、重い再解析は実行ボタンで確定
- 割り当てた2系列の読込・時間軸整合・Sweep分割をバックグラウンド実行
- 役割が揃ったshotを開いたときは既定でSweep分割を自動実行
- 分割処理のキャンセルと、系列切替後に返った古い結果の破棄
- 分割したSweep数と、currentの時間軸補間有無を画面で確認
- Sweep一覧で番号、方向、時間、点数、電圧範囲を確認
- Raw軸・時間範囲・Sweep一覧・除外区間の画面時刻をmsへ統一
- I–Vを主表示、Raw波形を下部左2/3へ常時表示し、選択Sweepの対応を同時確認
- 下部右1/3でSweep分割・一覧・平滑化/微分を切り替えてもRaw波形を維持
- 選択SweepのRaw時系列区間をorange highlightで表示
- 選択SweepのI–Vを電圧昇順で常時表示し、取得始点・終点を区別
- ツールバーまたは`Alt+Left` / `Alt+Right`で前後Sweepへ移動
- 周期合わせ・短い端数などの未分割区間をsample範囲と理由付きで表示
- 選択Sweepを既定のSavitzky–Golay窓501点・3次で自動的に前処理
- 指定窓がSweepより長い場合、利用可能な最大奇数窓へ安全に調整
- 大きなI–V領域でRawとFilteredを重ね、下段に`dI/dV`を独立表示
- SG窓・多項式次数を画面で変更し、Sweep分割をやり直さず再計算
- 非等間隔電圧の近似誤差を画面で警告
- 起動時の「データ確認」と、数値処理を行う「解析」を最上位タブで分離
- 解析タブで選択Sweep、解析Revision、前処理の未実行・完了・要確認・staleを表示
- `V_f`のゼロ交差、`Phi`のlog交点／`dI/dV`ピーク候補を根拠付きで表示・選択
- イオン／電子飽和域をロバスト直線fitし、`I_sat,i`、`I_sat,e`、`R`、`K`を算出
- 選択した`Phi`と飽和パラメータからPANTAモデルの`T_i`を有界最適化
- `T_i`目的関数、選択最小値、境界解、固定パラメータの品質警告を表示
- 候補・範囲を編集しても自動再計算せず、解析ボタンを押したときだけLevel 4–6を実行
- 「現在のshotを一括解析」で同じSG・Fit範囲を全Sweepへ明示適用し、バックグラウンドで順次解析
- 一括解析のキャンセル後も、完了済みSweepの結果を保持
- 最上位タブを切り替えただけでは前処理やSweep分割を再実行しない
- サマリーで現在shotの全Sweepを1行ずつ表示し、未実行・実行中・有効・要確認・不適・
  エラー・再計算必要・除外を区別
- サマリーで方式別の`T_i`・`Phi`をSweep番号に対してプロットし、採用値と対象外値を色分け
- `T_i`は`0 < T_i < 5 eV`、`Phi`は有限値という方式別条件で平均・標準偏差・採用数を表示
- サマリーの既定集計分母を`current revision`かつ有効／要確認に限定し、分子・分母を表示
- サマリーから対象Sweepを共有選択へ設定し、「解析で確認」で解析タブへ移動
- サマリー表示そのものではフィットや前処理を再計算しない
- Exportでcurrent revisionの有効／要確認だけを初期選択し、stale・失敗・除外も理由付きで表示
- Exportの図種、論文preset、SVG/PDF/PNG/CSV/manifest bundleと再現情報の契約を表示
- Exportを開く・対象やstyleを変える操作では解析値を変更・再計算しない

## 対応するフォルダ

フォルダは、1 shotだけを含んでいても、複数shotの親フォルダでも構いません。

```text
選択するフォルダ/
├── 20211221/
│   ├── 107845_032/
│   │   ├── 3_3_01.hdr
│   │   ├── 3_3_01.dat
│   │   ├── 3_3_02.hdr
│   │   └── 3_3_02.dat
│   └── 107845_035/
│       ├── 3_3_01.hdr
│       └── 3_3_01.dat.gz
└── ...
```

同じbasenameのヘッダーと波形ファイルを1系列として認識します。入力用JSONは使用しません。

## 起動

Python 3.12以上と [uv](https://docs.astral.sh/uv/) を使用します。

```bash
uv sync --extra dev
uv run python -m probe_app
```

画面左上の「フォルダを開く」から測定フォルダを選択してください。

## 検証

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

### macOSでの4ワークスペース手動回帰

1. アプリを起動し、最初に「データ確認」が開くことを確認する。
2. 実データフォルダを選び、current／sweep voltageを割り当ててSweep分割する。
3. 任意のSweepを選び、「データ確認」「解析」「サマリー」「Export」を20往復する。
4. タブ切替だけで読込中表示、Sweep再分割、前処理再計算が始まらないことを確認する。
5. 4タブで対象shotと選択Sweepが一致し、I–V・Raw highlightが変わらないことを確認する。
6. SG設定を変更した場合は「前処理を再計算」を押すまでI–V・サマリー・Export対象が
   変わらず、押した後だけ新しいRevisionになることを確認する。
7. stale、失敗、除外結果がサマリーから消えず、Exportでは初期checkされないことを確認する。
8. macOSの「アクティビティモニタ」でメモリを見ながらタブを100回切り替え、継続的な増加や
   UI停止がないことを確認する。

自動回帰では100回の切替についてworker開始0回、前処理呼出0回、1秒未満、Python追跡メモリ
増加2 MiB未満を基準にする。環境差で基準を外れた場合は、計算開始回数をP0として先に調べ、
時間・メモリ閾値は測定環境とともに記録して見直す。

## 現段階で意図的に行わないこと

- currentチャンネルとsweep voltageチャンネルの自動決定
- Raw側の多窓SG微分候補と4方式すべての`T_i`比較
- Level 4–6結果の全Sweep一括バッチ解析

current／sweep voltageは自動決定せず、利用者が画面から指定します。Rawプロットには`.hdr`の
分解能・オフセットだけを適用し、追加倍率は後続のSweep解析で使用します。

## Level 2（domain foundation）

Level 2のGUIへ進む前段として、次の純粋な計算機能を実装しています。

- basenameに依存しないcurrent / sweep voltageの役割モデル
- 旧コードの`current × 1/20`、`sweep voltage × 100`、電流符号を再現できる明示変換
- 異なる開始時刻・sampling間隔を扱う時間軸整合（外挿なし）
- データごとのcurrent／Sweep電圧時間差を手動補正（正値は後ろのcurrentを参照）
- current Raw表示時は、選択Sweepのハイライトを補正後のcurrent参照時刻へ移動
- I–V選択情報へ実際に適用したcurrent時間補正値を表示
- source境界と取得方向を保持する`Sweep`モデル
- 旧`sweep_sort`互換の半周期分割と型付きエラー
- 同一shot内のcurrent／sweep voltage役割割当UI
- フォルダ・shot別の役割／倍率／符号の保存と復元

役割や倍率の入力にJSONファイルは要求しません。設定は測定フォルダではなくOSのアプリ設定へ
保存します。current／sweep voltageを選んだ後、適用範囲を「現在のフォルダ（shot）のみ」
「このフォルダ以降」「すべてのフォルダ」から選べます。一括適用は同じchannel IDを各shot内で
照合し、見つからない／複数見つかるshotは既存設定を上書きせず理由を表示します。

役割が完全に設定されたshotは、開いた時点でSweep分割を自動実行します。自動実行は
「Sweep分割」タブで無効化できます。1周期の点数、sample範囲、current時間補正を変更した場合は、
編集中に重い処理を繰り返さないよう自動再計算せず、「今すぐ分割／再分割」で明示的に更新します。
I–Vは主領域、Raw波形は下部左側に常時表示されます。右側で「Sweep一覧」や
「平滑化・微分」を操作しながら、Raw上の対応位置を確認できます。上位の
folder／shot／seriesを変更すると、古いSweep選択と表示は同時に消去されます。

Sweep一覧の開始・終了時刻はSweep電圧基準です。current Rawを表示している場合、オレンジの
選択範囲は`current時間補正`を加えた実際のcurrent参照時刻へ移動します。たとえば+50 msでは、
電圧基準91.724–101.723 msのSweepに対し、current側141.724–151.723 msを強調表示します。
補正値を編集している間はオレンジ範囲だけを軽量に移動し、「未適用」と明示します。
I–V・Sweep一覧・平滑化/微分は変化せず、「今すぐ分割／再分割」を押した後にまとめて更新されます。

解析対象の既定sample半開区間は`[200000, 500000)`です。1 µs刻みの600,000点データでは
No.1がRaw上の約200 msから始まり、500 msより後のデータからI–Vを作りません。Rawプロットは
解析範囲で切らず、0–600 ms相当の全時間範囲を維持します。

## Level 3（平滑化・微分）

選択中の1 Sweepだけを`analysis`層へ渡し、readerやSweep分割を再実行せず次を計算します。

```text
Sweep.iv_voltage_v / iv_current_a
  └─ Savitzky–Golay平滑化
       ├─ Filtered current [A]
       └─ dI/dV [A/V]
```

既定値は旧コードと同じ窓501点・3次です。窓はSweep点数以下の有効な奇数へ自動調整します。
微分の電圧刻みは旧コード互換の端点平均
`(V[-1] - V[0]) / (N - 1)`です。局所刻みが平均から5%を超えて外れる場合は、等間隔近似を
確認するよう画面へ警告します。

## Level 4–6（V_f・Phi・飽和域・T_i model fit）

「解析」ワークスペースの右側インスペクタで、選択中の1 Sweepに対して次を明示的に実行します。

1. `V_f`: 隣接点の符号変化を線形補間し、複数候補を保持する。
2. `Phi`: Filtered電流の`log10(I)`を2領域でロバスト直線fitした交点と、正の`dI/dV`
   局所ピークを候補にする。
3. 飽和域: イオン側・電子側をロバスト直線fitし、`V_f`へ外挿して`I_sat,i/e`、`R`、`K`
   を求める。
4. `T_i`: 他のパラメータを固定したPANTAモデルを`Phi - 0.1 V`から`Phi`の範囲で評価し、
   `0.1–10 eV`の有界1変数最適化で残差平方和を最小化する。

既定範囲はlog Fit1が`10–15 V`、Fit2が`20–50 V`、イオン飽和域が`-35–-15 V`、
電子飽和域が`20–50 V`です。候補や範囲の変更だけでは再計算されません。
「V_f・Phi・飽和域・T_iを解析」を押したときだけ前処理から品質判定まで更新されます。
結果はI–V上の縦線・飽和直線・PANTA曲線と、右側の数値・`T_i`目的関数で確認できます。

`valid`は数値的に採用可能、`review`は境界解・一部方式失敗・簡易推定との差などを要確認、
`bad`は`R`または`K`が設定した物理範囲外、`error`は必要点不足などで工程を完了できない状態です。
最適化の成功だけで物理的妥当性を保証しないため、候補位置、fit線、目的関数を合わせて確認します。

## 設計資料

- [アーキテクチャ](docs/architecture.md)
- [フォルダ・データ契約](docs/data-contract.md)
- [GitHub Issue投入用バックログ](docs/github-issue-backlog.md)
- [Level 1実データ確認・性能測定](docs/benchmarks/level1-2026-07-23.md)
- [Level 2 golden Sweep仕様](docs/testing/level2-golden-sweep.md)
- [Level 2性能測定](docs/benchmarks/level2-2026-07-24.md)
- [Level 2利用テスト](docs/usability/level2-sweep-2026-07-24.md)
- [Level 2基盤レビュー](docs/reviews/level2-foundation-2026-07-24.md)
- [Level 3数値契約・golden test](docs/testing/level3-preprocessing.md)
- [Level 3性能測定](docs/benchmarks/level3-2026-07-24.md)
- [Level 3レビュー](docs/reviews/level3-preprocessing-2026-07-24.md)
- [Level 4–6解析契約・回帰テスト](docs/testing/level4-6-analysis.md)
- [サマリーワークスペース状態・集計契約](docs/usability/summary-workspace-contract-2026-07-27.md)
- [Export論文図ビルダー仕様](docs/usability/export-figure-builder-spec-2026-07-27.md)
- [4ワークスペース状態同期・無再計算テスト](docs/testing/workspace-regression.md)
- [ADR: フォルダ起点の入力](docs/adr/0002-folder-first-input.md)
