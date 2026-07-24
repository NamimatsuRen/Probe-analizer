# Level 2 golden Sweep仕様

## 目的

旧`Sweep_sort`互換境界が将来の改修で変わったことを、sample単位で検出する。

## Golden case

```text
1周期: [0, 1, 2, 3, 4, 3, 2, 1]
points_per_cycle: 8
入力: 3周期
source offset: 100
```

期待値:

| Sweep | source半開区間 | 方向 |
|---:|---|---|
| 1 | `[100, 104)` | up |
| 2 | `[104, 108)` | down |
| 3 | `[108, 112)` | up |
| 4 | `[112, 116)` | down |

- 許容境界誤差: **0 sample**
- down Sweepの保存順: 取得順
- down SweepのI–V表示順: 電圧昇順へ反転
- 末尾`[116, 124)`は周期合わせによる除外区間として記録する

## 異常・端数case

最初の最小電圧が周期内offset 2にあり、完全Sweep後に2点余るcaseでは、次を別々に保持する。

- 先頭の周期合わせ区間
- valid Sweep
- `incomplete_sweep`の端数区間
- 末尾の周期合わせ区間

厳格APIは`incomplete_sweep`を`misaligned_window`として拒否する。GUIが使う診断APIは完全Sweepを
返しながら、端数を理由付き除外区間として表示する。

## 自動テスト

- `tests/unit/test_sweep_splitter.py`
- `tests/integration/test_split_sweeps.py`
- `tests/e2e/test_level1_window.py`
