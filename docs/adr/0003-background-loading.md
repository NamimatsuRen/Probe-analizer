# ADR 0003: 読込をバックグラウンド化しgeneration IDで結果を保護する

- Status: Accepted
- Date: 2026-07-23

## Context

大規模フォルダの走査や600,000点の波形読込をGUIスレッドで行うと、画面が停止する。また、
フォルダや系列を素早く切り替えたとき、古い処理結果が後から表示される競合が起こる。
Level 2の2系列読込・時間軸整合・Sweep分割も同じ問題を持つ。

## Decision

- フォルダ走査、波形読込、Sweep分割はQt thread poolで実行する。
- 処理種別ごとに単調増加するgeneration IDを付ける。
- 現在のgenerationと一致しない結果は破棄する。
- キャンセルは停止フラグを使う協調的キャンセルとする。
- series／role変更時はSweep taskをキャンセルし、そのgenerationを即時無効化する。
- Sweepの失敗・キャンセル状態はフォルダ読込状態から分離する。

## Consequences

- GUIは読込中も応答できる。
- フォルダ切替後に古い波形が混ざらない。
- series切替後に古いSweep集合が混ざらない。
- Sweepだけをキャンセルしても、folder catalogとRaw表示は利用できる。
- 1回のOSファイル読込自体は途中で即時停止できない場合があるが、結果は反映されない。
