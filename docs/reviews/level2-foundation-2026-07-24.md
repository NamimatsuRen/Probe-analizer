# Level 2基盤レビュー

レビュー日: 2026-07-24

## Gate結果

| Gate | 結果 | 証拠 |
|---|---|---|
| `domain` / `analysis`がGUI非依存 | 合格 | AST境界テストでPySide6・pyqtgraph importを禁止 |
| selectionの正規ソースが1つ | 合格 | `AppState.selected_sweep_id`とreset chainの単体テスト |
| Level 1–2 E2E成功率 | 合格 | 全E2E成功 |
| Level 3 panel差込 | 合格 | `AnalysisPreviewPanel`をreader変更なしで追加 |
| Sweep切替200 ms | 合格 | 10,000点×40 Sweep、p95 2.358 ms |
| golden境界 | 合格 | 0 sample誤差 |
| 異常・未分割区間 | 合格 | 型付き除外理由と別枠UI表示 |

## 依存方向

```text
ui -> application state/use case -> domain
ui -> analysis -> domain
infrastructure readers -> domain
```

- `analysis/preprocessing/sweep_preview.py`は`Sweep`だけを入力に取る。
- `AnalysisPreviewPanel`追加にあたり`infrastructure/readers`は変更していない。
- file readerはフォルダ起点のままで、JSON設定を入力に戻していない。

## Selection reset規則

正規ソースは`AppState`である。

```text
folder変更
  -> catalog / shot / series / Sweepを無効化
shotまたはrole変更
  -> Sweep結果と選択を無効化
series変更
  -> Sweep結果と選択を無効化
Sweep分割成功
  -> 先頭Sweepを選択
Sweep選択
  -> Raw / I–V / analysis previewを同じIDへ更新
```

## Level 3への拡張性

Level 3は`analysis`配下へ純粋関数を追加し、選択済み`Sweep`を渡す。フォルダ走査、PANTA reader、
役割割当、Sweep分割を変更する必要はない。今回のpreviewは、この差込経路を最小構成で実証した。

## 残余リスク

- 外部利用者3〜5名による利用テストは未実施。内部ベースラインの制約として記録済み。
- 実験データ規模・GPU/画面backendが異なる環境では性能値を再測定する。
- `HOffset`の装置仕様上の厳密解釈は既存Research Issueの対象であり、Level 2の境界外。

## 判定

Level 2のコード・アーキテクチャ・自動品質Gateは通過。main CI成功後に安定版tagを付与できる。
