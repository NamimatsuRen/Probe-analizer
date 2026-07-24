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

## 失敗状態

| 状態 | 意味 | 利用者の次の操作 |
|---|---|---|
| empty | 対応する組が0件 | 親フォルダまたは別フォルダを選ぶ |
| partial | 正常系列と不正系列が混在 | 正常系列を確認し、詳細tooltipで不正ファイルを見る |
| error | フォルダ自体を開けない | パス・アクセス権を確認する |
| cancelled | 利用者が停止 | 同じフォルダを再読込するか別フォルダを選ぶ |
