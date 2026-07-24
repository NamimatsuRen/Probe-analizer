# Probe Analizer

プローブ測定データを、フォルダから直接選んで確認・解析するデスクトップアプリです。

現在は開発ロードマップの **Level 1** です。選択したフォルダ以下から測定データを自動検出し、shot／系列の一覧とRaw波形を表示できます。

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

## Level 1で意図的に行わないこと

- currentチャンネルとsweep voltageチャンネルの自動決定
- 電流の `1/20`、スイープ電圧の `×100` など装置固有の換算
- Sweep分割
- 平滑化、微分、浮遊電位・プラズマ電位・温度フィット

これらは、フォルダから見つけた系列に「current」「sweep voltage」などの役割を割り当てるLevel 2以降で追加します。Level 1では、`.hdr` に記録された分解能・オフセット・単位だけを適用します。

## Level 2（domain foundation）

Level 2のGUIへ進む前段として、次の純粋な計算機能を実装しています。

- basenameに依存しないcurrent / sweep voltageの役割モデル
- 旧コードの`current × 1/20`、`sweep voltage × 100`、電流符号を再現できる明示変換
- 異なる開始時刻・sampling間隔を扱う時間軸整合（外挿なし）
- source境界と取得方向を保持する`Sweep`モデル
- 旧`sweep_sort`互換の半周期分割と型付きエラー

役割や倍率の入力にJSONファイルは要求しません。現時点では計算境界とテストまでで、
役割割当画面・Sweep Browser・I–V表示は後続の小さな変更として接続します。

## 設計資料

- [アーキテクチャ](docs/architecture.md)
- [フォルダ・データ契約](docs/data-contract.md)
- [GitHub Issue投入用バックログ](docs/github-issue-backlog.md)
- [Level 1実データ確認・性能測定](docs/benchmarks/level1-2026-07-23.md)
- [ADR: フォルダ起点の入力](docs/adr/0002-folder-first-input.md)
