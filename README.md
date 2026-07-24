# Probe Analizer

プローブ測定データを、フォルダから直接選んで確認・解析するデスクトップアプリです。

開発ロードマップの **Level 2** まで実装済みです。フォルダからRaw波形を確認し、同一shotの
current／sweep voltageを割り当て、Sweep分割、Raw対応表示、I–V確認まで実行できます。

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
- JSONに代わる画面入力で、1周期の点数と対象sample範囲を指定
- 割り当てた2系列の読込・時間軸整合・Sweep分割をバックグラウンド実行
- 分割処理のキャンセルと、系列切替後に返った古い結果の破棄
- 分割したSweep数と、currentの時間軸補間有無を画面で確認
- Sweep一覧で番号、方向、時間、点数、電圧範囲を確認
- 選択SweepのRaw時系列区間をorange highlightで表示
- 選択SweepのI–Vを電圧昇順で表示し、取得始点・終点を区別
- ツールバーまたは`Alt+Left` / `Alt+Right`で前後Sweepへ移動
- 周期合わせ・短い端数などの未分割区間をsample範囲と理由付きで表示
- Level 3解析をreader変更なしで追加するpreview接続

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

## 現段階で意図的に行わないこと

- currentチャンネルとsweep voltageチャンネルの自動決定
- 平滑化、微分、浮遊電位・プラズマ電位・温度フィット

current／sweep voltageは自動決定せず、利用者が画面から指定します。Rawプロットには`.hdr`の
分解能・オフセットだけを適用し、追加倍率は後続のSweep解析で使用します。

## Level 2（domain foundation）

Level 2のGUIへ進む前段として、次の純粋な計算機能を実装しています。

- basenameに依存しないcurrent / sweep voltageの役割モデル
- 旧コードの`current × 1/20`、`sweep voltage × 100`、電流符号を再現できる明示変換
- 異なる開始時刻・sampling間隔を扱う時間軸整合（外挿なし）
- source境界と取得方向を保持する`Sweep`モデル
- 旧`sweep_sort`互換の半周期分割と型付きエラー
- 同一shot内のcurrent／sweep voltage役割割当UI
- フォルダ・shot別の役割／倍率／符号の保存と復元

役割や倍率の入力にJSONファイルは要求しません。設定は測定フォルダではなくOSのアプリ設定へ
保存します。Sweep分割は「Sweep分割」タブから実行でき、結果は「Sweep一覧」と「I–V」で
確認できます。上位のfolder／shot／seriesを変更すると、古いSweep選択と表示は同時に消去されます。

## 設計資料

- [アーキテクチャ](docs/architecture.md)
- [フォルダ・データ契約](docs/data-contract.md)
- [GitHub Issue投入用バックログ](docs/github-issue-backlog.md)
- [Level 1実データ確認・性能測定](docs/benchmarks/level1-2026-07-23.md)
- [Level 2 golden Sweep仕様](docs/testing/level2-golden-sweep.md)
- [Level 2性能測定](docs/benchmarks/level2-2026-07-24.md)
- [Level 2利用テスト](docs/usability/level2-sweep-2026-07-24.md)
- [Level 2基盤レビュー](docs/reviews/level2-foundation-2026-07-24.md)
- [ADR: フォルダ起点の入力](docs/adr/0002-folder-first-input.md)
