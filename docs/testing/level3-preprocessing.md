# Level 3 preprocessing numerical contract

## 対象

選択済み`Sweep`へSavitzky–Golay平滑化と一次微分を適用し、Raw／Filtered／`dI/dV`を
同じ電圧軸で比較する処理。

## 旧コードとの互換点

- 既定値は窓501点・3次。
- 窓はデータ点数以下の奇数へ調整する。
- 微分の`delta`は端点から求めた平均電圧刻み。
- down Sweepは電圧が増える解析順へ反転する。
- 微分はRaw電流へSG一次微分を直接適用する。

## Golden test

三次多項式

```text
I(V) = V³ + 2V² - 4V + 1
dI/dV = 3V² + 4V - 4
```

を101点の等間隔電圧へ与える。窓21点・3次で、平滑化後電流が元多項式へ`2e-11 A`以内、
微分が解析解へ`2e-10 A/V`以内で一致することを固定する。

このほか、次を自動確認する。

- 10点へ指定501点 → 実使用9点
- 偶数指定8点 → 実使用7点
- 点数不足時の説明可能なエラー
- down Sweepの電圧・電流反転
- 局所的な非単調刻みで警告を返す
- 結果配列の変更が元Sweep配列へ波及しない
- GUIへ渡したRaw／Filtered／`dI/dV`配列が計算結果と一致する
- SG設定変更がreaderやSweep分割を再実行しない

## 単位

| 値 | 単位 |
|---|---|
| voltage | V |
| raw current | A |
| filtered current | A |
| derivative | A/V |

プロットライブラリのSI prefix表示により、値の大きさに応じてmA、µAなどへ見た目だけが変わる。
計算配列の単位は常に上表のままである。
