# Level 3 review — 2026-07-24

## 完成形

利用者は選択中SweepのRaw I–VとFiltered I–Vを重ねて確認し、同じ電圧軸の`dI/dV`を
下段で確認できる。SG窓・次数を変更しても、フォルダ読込、2系列読込、時間軸整合、
Sweep分割は再実行されない。

## Gate

- [x] 既定値はlegacy互換の窓501点・3次
- [x] 短いSweepでは安全な奇数窓へ自動調整
- [x] Raw／Filtered／`dI/dV`の単位と線種を分離
- [x] 前／次Sweep操作と解析結果が同期
- [x] 上位選択変更で古い解析結果を消去
- [x] 点数不足・方向不整合を非致命的エラーとして表示
- [x] 三次多項式golden test
- [x] analysis層はPySide6・pyqtgraph非依存
- [x] 10,000点・窓501の中央値2.181 ms
- [x] pytest 83件、ruff、mypy成功

## 意図的な非ゴール

- `V_f`、`Phi`候補
- 飽和域fit
- `T_i`最適化
- shot内全Sweepの一括前処理
- 前処理設定のproject export

これらはLevel 4以降で、今回の`PreprocessedSweep`を入力として追加する。
