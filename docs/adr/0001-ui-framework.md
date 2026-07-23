# ADR 0001: PySide6 + PyQtGraphを使用する

- Status: Accepted
- Date: 2026-07-23

## Context

既存アプリはQt系GUIであり、測定波形をズーム・パンしながら確認する。長い波形を対話的に扱う必要がある。

## Decision

GUIへPySide6、プロットへPyQtGraphを使用する。domain、application、analysisは両ライブラリをimportしない。

## Consequences

- 既存の操作感と移行しやすい。
- バックグラウンド処理はQtのthread poolへ接続できる。
- GUIテストはoffscreen platformで実行する。
- 配布方法はLevel 8で別途決める。
