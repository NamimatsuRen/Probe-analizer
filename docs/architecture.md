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
- `analysis`: Level 3以降に追加する。PySide6をimportしない。

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
| `MainWindow` | 操作イベントと状態・表示を接続する |

## メモリ方針

- フォルダ選択時は波形本体を読まず、descriptorだけ作る。
- 波形は選択された1系列だけ読む。
- 新しい系列を選んでも、古いバックグラウンド結果はgeneration IDで破棄する。
- プロットには最大50,000点を渡し、各区間の最小値・最大値を残す。
- 全系列の巨大なNumPy配列をアプリ状態へ保持しない。

## 非同期処理

Qtのthread poolを使用する。キャンセルは協調的であり、処理へ停止フラグを渡す。ファイル読込中に完全な強制停止は行わないが、キャンセル後に返った結果は画面へ反映しない。

## 次の境界

Level 2では次を追加する。

1. フォルダから見つけた系列へ `current` / `sweep_voltage` の役割を割り当てる。
2. 役割と装置固有倍率を、JSON入力ではなく画面操作と保存可能な設定として扱う。
3. 2系列を時間軸上で整合させ、Sweepへ分割する。
4. Raw時系列の選択区間とI–Vプロットを連動させる。
