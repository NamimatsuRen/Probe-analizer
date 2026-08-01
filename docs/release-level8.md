# Level 8 リリース・再現性手順

## 完成条件

- macOS arm64とWindows x64の配布物を同一tagから作る。
- 配布前に全テスト、lint、型検査を通す。
- `SHA256SUMS.txt`でダウンロード後の破損を検出できる。
- 保存したprojectを再度開き、Rawフォルダを移動した場合は明示的に再リンクできる。
- 論文図は図だけでなく、source CSVとcanonical manifestを同時に保存する。

## 配布物の作成

GitHub Actionsの`Release builds`を手動実行するか、`v0.8.0`形式のtagをpushする。
workflowはmacOS／Windowsで独立にテストした後、PyInstallerでアプリを生成する。成果物は
zipと`SHA256SUMS.txt`であり、コード署名・公証は別途行う。

ローカル確認では次を実行する。

```bash
uv sync --extra dev
uv pip install --python .venv "pyinstaller>=6.14,<7"
uv run --no-sync pyinstaller --noconfirm --clean packaging/probe-analizer.spec
```

## projectの保存と再開

1. 測定フォルダを開き、系列割当、Sweep分割、解析、除外、位置metadataを確定する。
2. 「projectを保存」で`*.probe-project.json`を明示保存する。
3. 後日「projectを開く」で結果、選択、metadata、監査履歴を復元する。
4. 元データの場所が変わった場合だけ、画面で新しいフォルダを選び再リンクする。

projectはRaw配列を複製せず、解析Revisionとスカラー結果を保存する。保存は一時ファイルを
fsyncしてから置換するため、書込み失敗時は直前のprojectを維持する。現行schemaは1で、
schema 0は読込時に1へ移行し、未知の将来schemaは推測せず拒否する。

## 論文図bundle

Exportタブで図種、候補、preset、成果物を選び、まず明示的にpreviewを更新する。「書き出す」で
SVG、PDF、PNG、source CSV、manifestから選択した成果物を一括生成する。同名出力は暗黙に
上書きせず、利用者が確認した場合だけ置換する。

manifestにはコードversion、project schema、解析Revision、採用Sweep、除外、図panel、軸、
単位、styleを記録する。source CSVとmanifestを保管することで、画面状態に依存せず同じ入力を
追跡できる。

## 公開前の手動Gate

1. 実データでフォルダ読込からI–V、解析、サマリー、Exportまで通す。
2. project保存後にアプリを終了し、再起動後に同じ結果と選択が戻ることを確認する。
3. Rawフォルダを一時的に移し、再リンク後もshot／Revisionが一致することを確認する。
4. SVG、PDF、PNGを開き、文字欠け、軸単位、凡例、error barを確認する。
5. CSVとmanifestの採用点が画面の対象と一致することを確認する。
6. 外部の利用者によるLevel 1／2／3の受入Issueは、実測完了まで閉じない。
