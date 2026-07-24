# Folder and data contract

## 入力境界

アプリが受け取る入力は**フォルダパス**だけである。解析対象を列挙するJSONファイルは必須にしない。

## 系列の認識

1. 選択フォルダ以下の `.hdr` を再帰的に探す。
2. 同じディレクトリ・同じbasenameについて、次の優先順で波形を探す。
   1. `.wvf`
   2. `.dat`
   3. `.dat.gz`
3. ヘッダーと波形がそろった組を1系列とする。
4. 波形がない、またはヘッダーが壊れている系列は問題一覧へ残し、正常系列の閲覧は継続する。

## ID

- `series_id`: 選択フォルダから見たヘッダーの相対パスから拡張子を除いた値。
- `shot_id`: ヘッダーが選択フォルダ直下なら選択フォルダ名。それ以外は相対親パス。
- `channel_id`: basename。

例:

```text
root = /data
header = /data/20211221/107845_032/3_3_01.hdr

series_id = 20211221/107845_032/3_3_01
shot_id   = 20211221/107845_032
channel_id = 3_3_01
```

相対パスを使うことで、日付をまたいで同じshot名が存在しても衝突しない。

## ヘッダー

Level 1で使用する必須項目:

- `BlockSize`
- `VResolution`
- `VOffset`
- `HResolution`

任意項目:

- `HOffset`（省略時0）
- `DataOffset`（省略時0）
- `Endian`（省略時Ltl）
- `VDataType`（省略時IS2）
- `VUnit`
- `HUnit`
- `TraceName`
- `Date`
- `Time`
- `Model`

Level 1の対応データ型は符号付き16 bit整数（`IS2` / `I16` / `INT16`）。

## 変換

波形の整数値を `r[n]` とすると、表示値は

```text
y[n] = VResolution × r[n] + VOffset
t[n] = (n + 1 + HOffset) × HResolution
```

で計算する。

Level 1は装置固有の電流倍率・電圧倍率を適用しない。チャンネル役割と倍率の決定はLevel 2の責務とする。

時間軸は旧`pantaADC.readDat(..., samplingtime=True)`と結果比較できるよう、1始まりかつ`HOffset`をsample offsetとして扱う。Yokogawa形式上の`HOffset`の厳密な意味は別Issueで検証し、変更する場合は既存結果との差分を明示する。

## Level 2の物理信号変換

フォルダから読み込んだRaw系列を `x_raw` とすると、役割割当後の物理量は次で得る。

```text
x_physical = x_raw × scale × sign
```

変換はRaw配列を上書きしない。旧コードを再現する設定は次の通りだが、入力の既定値には
せず、利用者が選択したseriesへ明示的に割り当てる。

| role | scale | sign | output unit |
|---|---:|---:|---|
| current | 1 / 20 | +1 または -1 | A |
| sweep_voltage | 100 | +1 | V |

役割未割当は有効な状態である。フォルダ読込とRaw表示は、役割設定やJSONファイルがなくても
完了できなければならない。

## 役割設定の保存

役割設定は選択測定フォルダの入力データではない。次の値を、OSが管理するアプリ設定へ
folder pathとshot IDの組み合わせごとに保存する。

- currentのseries ID、scale、sign、output unit
- sweep voltageのseries ID、scale、sign、output unit

測定フォルダへJSON、設定ファイル、隠しファイルを作らない。設定が存在しない状態、
一方だけ割り当てた状態、両方未割当へ戻した状態はいずれも有効とする。

保存済みseries IDが現在のcatalogに存在しない場合は、そのroleを未割当へ戻す。
設定の読込・保存失敗はRawデータの読込失敗として扱わず、画面上の非致命的な警告とする。

## 時間軸の整合

掃引電圧の時刻を基準軸とする。

1. currentとsweep voltageの共通時間範囲を求める。
2. 共通範囲内にあるsweep voltage点だけを残す。
3. 時刻配列が完全一致する場合はcurrentをそのまま使用する。
4. 一致しない場合はcurrentを線形補間する。
5. 共通範囲外への外挿は行わない。

非有限値、単調増加でない時刻、共通範囲なし、点数不足はそれぞれ異なる型付きエラーとする。
Raw時系列上の表示位置へ戻せるよう、整合後の先頭が元のsweep voltage配列の何番目かも保持する。

## legacy Sweep分割

`points_per_cycle = N` は偶数とし、1 Sweepは `N / 2` 点とする。対象sample範囲は
半開区間 `[sample_start, sample_stop)` で明示する。

旧 `sweep_sort` と同じ境界を次の手順で再現する。

1. 対象範囲の先頭 `N` 点からsweep voltage最小点のoffset `s` を求める。
2. 先頭から `s` 点、末尾から `N - s` 点を除く。
3. 残りを `N / 2` 点ごとに区切る。
4. 取得順の偶数番をup、奇数番をdownとする。

残り点数が `N / 2` で割り切れない場合、端数を黙って捨てず
`misaligned_window` として停止する。down Sweepは保存時には取得順を維持し、
解析時だけ配列を反転して電圧昇順にする。

## Sweep分割の画面入力

旧JSONにあった分割条件は、測定フォルダの入力契約へ含めない。画面の「Sweep分割」タブで
次を明示する。

- `points_per_cycle`: 1周期のsample点数。2以上の偶数。
- `sample_start`: 対象半開区間の先頭。既定値0。
- `sample_stop`: 対象半開区間の末尾。「末尾まで使う」場合は未指定。

実行時点のrole割当と上記パラメータを不変なrequestとしてbackground taskへ渡す。
実行後にseriesまたはroleが変わった場合、旧requestの結果はgeneration不一致として破棄する。
キャンセルはcatalogやRaw表示を消さず、同じ条件で再実行できる状態へ戻す。

## 失敗状態

| 状態 | 意味 | 利用者の次の操作 |
|---|---|---|
| empty | 対応する組が0件 | 親フォルダまたは別フォルダを選ぶ |
| partial | 正常系列と不正系列が混在 | 正常系列を確認し、詳細tooltipで不正ファイルを見る |
| error | フォルダ自体を開けない | パス・アクセス権を確認する |
| cancelled | 利用者が停止 | 同じフォルダを再読込するか別フォルダを選ぶ |

Sweep分割の`error`と`cancelled`はフォルダ読込状態とは別に管理する。したがって、分割条件が
不正でも正常なRaw閲覧は継続できる。
