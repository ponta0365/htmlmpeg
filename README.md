# htmlmpeg

ローカル環境で FFmpeg を使い、動画・音声・画像をブラウザUIから圧縮するためのデスクトップ向けWebアプリです。

## 特徴

- ブラウザから操作するローカル専用UI
- Python + Flask ベースのバックエンド
- FFmpeg / FFprobe を subprocess で実行
- 動画・音声・画像の種別ごとにプリセットを切り替え
- フォルダ一括処理、再帰走査、進捗表示、停止処理に対応
- プリセット保存、既定設定、設定の書き出し/読み込みに対応
- 既存ファイルの上書き可否をジョブ側とプリセット側で同期

## 必要環境

- Windows 11 を推奨
- Python 3.x
- `ffmpeg.exe` / `ffprobe.exe`

## 起動方法

### Python で起動

```powershell
pip install -r requirements.txt
python app.py
```

### PowerShell スクリプトで起動

```powershell
./start.ps1
```

### 配布 EXE を作成

```powershell
./build_exe.ps1
```

## FFmpeg の配置

アプリ内の設定で `ffmpeg.exe` と `ffprobe.exe` が入ったフォルダを指定できます。

- 同じフォルダに 2 つの実行ファイルを置く
- もしくは PATH に通す
- 未設定時は PATH を順に検索します

## 主な使い方

1. 圧縮対象を `動画 / 音声 / 画像` から選ぶ
2. 入力ファイルまたはフォルダを指定する
3. プリセットを選ぶ
4. 保存先を指定する
5. 必要に応じて `サブフォルダを含める` / `元フォルダ構造を維持` / `上書き` を切り替える
6. `開始` を押す

## 主要機能

- 入力ファイルの対象スキャン
- ffprobe によるメディア情報取得
- FFmpeg コマンドのテンプレート生成
- 進捗とログのポーリング表示
- 停止要求の送信
- 処理履歴の参照
- 設定のエクスポート / インポート

## プリセット

内蔵プリセットは `presets/` にあります。

- `video_default.json`
- `audio_default.json`
- `image_default.json`

ユーザープリセットや設定ファイルはローカルデータとして扱います。

## テスト

```powershell
python -m unittest discover -s tests
```

## ディレクトリ構成

- `app.py` - Flask アプリ本体
- `core/` - スキャン、検証、コマンド生成、ジョブ管理
- `templates/` - HTML テンプレート
- `static/` - JavaScript / CSS
- `presets/` - 内蔵プリセット
- `tests/` - 単体テスト / 結合テスト

## 備考

- ローカル限定運用を前提にしています
- `temp/`、`build/`、`dist/`、ログ類は生成物です
- `overwrite` 設定はジョブ側とプリセット側で同期します
