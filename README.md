# VS Code 設定共有ツール

## 📋 概要

仲間内でVS Codeの設定と拡張機能を共有するためのPythonツールです。

**バージョン**: 1.0.0
**対象OS**: Windows

---

## 💡 主な機能

### 1. エクスポート機能 (`vscode_export_profile.bat`➔`export_profile.py`)
- 現在のVS Code設定（settings.json）をプロファイルに保存
- インストール済み拡張機能リストをJSON形式で保存
- キーバインド設定やスニペットの保存（オプション）
- 拡張機能の説明ファイルとの整合性チェック

### 2. インポート/適用機能 (`vscode_setting.bat`➔`setting.py`)
- 複数のプロファイルから拡張機能を一覧化
- 共通プロファイル（`.project-common`）の自動適用
- 拡張機能の一括インストール
- 設定のマージ（オブジェクト、配列、プリミティブ型の適切な処理）
- SafePreset機能（テーマやフォントサイズなど外観設定の保護）
- マージレポートの自動生成

---

## 🔧 仕組みの全体像

```plain
│  プロジェクトリポジトリ
│
│  vscode/
│  ├── export_profile.py           ← エクスポートスクリプト (Python)
│  ├── setting.py                   ← インポート/適用スクリプト (Python)
│  ├── vscode-extensions-explain.json  ← 拡張機能の説明
│  └── profiles/
│      ├── .project-common/   ← チーム共通（必須）
│      ├── suzuki-taro/             ← 個人プロファイル例
│      └── yamada-hanako/           ← 個人プロファイル例
│
├─ vscode_setting.bat           ← 設定を適用（Pythonを呼び出し）
└─ vscode_export_profile.bat    ← 設定をエクスポート（Pythonを呼び出し）
```

---

## 📦 セットアップ

### 前提条件
- ✅ **VS Code**がインストールされていること
- ✅ **VS Code CLI** (`code` コマンド) がPATHに含まれていること

### VS Code CLI確認
```cmd
code --version
# バージョン情報が表示されればOK
```

VS Code CLIが見つからない場合：
1. 環境変数PATHにVS Codeのインストールパスを追加
   - 例: `C:\Users\[ユーザー名]\AppData\Local\Programs\Microsoft VS Code\bin`

---

## 📦 各プロファイルの構成

各メンバーのプロファイルフォルダには以下が保存されます：

```plain
vscode/profiles/[your-name]/
├── settings.json              ← VS Code設定
├── vscode-extensions.json     ← 拡張機能一覧
├── keybindings.json          ← キーバインド（オプション：デフォルトでは出ないです）
└── snippets/                 ← スニペット（オプション：デフォルトでは出ないです）
```

### 特別なプロファイル: `.project-common`

```plain
プロジェクト全員が必ず適用する共通設定
- 必須拡張機能（Linter、Formatter等）
- コーディング規約に準拠した設定
- チーム標準のエディタ設定
```

---

## 🚀 使い方：自分の設定をエクスポート

### Step 1: エクスポート実行

1. **管理者権限**でコマンドプロンプトを開く
2. リポジトリのルートで実行：

   ```batch
   vscode_export_profile.bat
   ```

3. プロファイル名を入力（例: `suzuki-taro`）
   - 既存プロファイルから選択も可能（番号入力）
   - 新規プロファイル名は半角英数字とハイフンのみ

### Step 2: Git操作

```bash
git add vscode/profiles/[your-name]/
git commit -m "Add: 自分のVS Code設定を追加"
git push
```

### 何が保存される？

- ✅ **settings.json**: テーマ、フォント、拡張機能設定など（常に保存）
- ✅ **拡張機能一覧**: インストール済み拡張のID・バージョン（常に保存）
- 🔲 **keybindings.json**: オプション（`--include-keybindings`）
- 🔲 **snippets**: オプション（`--include-snippets`）

---

## 🎁 使い方：設定を適用

### Step 1: 最新を取得

```bash
git pull
```

### Step 2: 設定適用実行

1. **管理者権限**でコマンドプロンプトを開く
2. リポジトリのルートで実行：

```batch
vscode_setting.bat
```

### Step 3: 対話形式で選択

#### ① 拡張機能の選択

GUIで一覧が表示されます：必要な拡張機能を全て選択してください。

**💡ヒント**:
- 共通プロファイル（`.project-common`）の拡張機能は自動的に含まれます
- 既にインストール済みの拡張機能はスキップされます

#### ② 設定プロファイルの選択

GUIで一覧が表示されます：取り込みたいプロファイルを選択してください。

### Step 4: 自動実行される処理

```plain
✅ バックアップ作成（settings.backup-YYYYMMDD-HHMMSS.json）
✅ 拡張機能の一括インストール
✅ 設定のマージ（衝突解決あり）
✅ レポート出力（vscode-setting-merge-report.md）
```
現在の設定はバックアップされるので安心です。
元の設定に戻したい場合は、`%APPDATA%\Code\User\`の`settings.backup-YYYYMMDD-HHMMSS.json`を`settings.json`にリネームして復元してください。

---

## 🔒 安心ポイント：既存設定は守られる

### マージの優先順位

```plain
優先度：低 ← → 高

1️⃣ あなたの既存設定（ベース）
    ↓ マージ
2️⃣ 共通設定（.project-common）
    ↓ マージ
3️⃣ 選択したプロファイル（最優先）
```

### マージ規則

| 型 | マージ方法 |
|---|-----------|
| **オブジェクト（辞書）** | 再帰的にマージ（キー衝突は優先順位に従う） |
| **プリミティブ値** | 優先順位に従って上書き |
| **配列** | 重複を排除してユニオン化（文字列配列はソート） |

## 📊 マージレポートで確認

適用後、[vscode-setting-merge-report.md](vscode-setting-merge-report.md) が自動生成されます：

```markdown
# VS Code 設定・拡張機能 適用レポート

## 拡張機能インストール結果
- 新規インストール: 5 個
- スキップ（既存）: 10 個

## 設定マージ結果

### マージの詳細
| キー | アクション | ソース | 旧値 | 新値 |
|------|-----------|--------|------|------|
| `editor.fontSize` | 上書き | suzuki-taro | 12 | 14 |
| `workbench.colorTheme` | 追加 | .project-common | [なし] | "Monokai" |
```

---

## 🆕 新人向け：初回セットアップ手順

### 1. 前提条件確認

```cmd
# VS Code CLIの確認
code --version
# バージョン情報が表示されればOK
```

### 2. リポジトリをクローン

```bash
git clone <リポジトリURL>
cd <リポジトリフォルダ>
```

### 3. 設定を適用（管理者権限で）

```batch
vscode_setting.bat
```

### 4. 選択のガイドライン

```plain
【拡張機能】
→ 最初は先輩のおすすめを全部選択
→ 慣れてきたら必要なものを取捨選択
→ 共通拡張は自動インストールされるので考慮不要

【設定プロファイル】
→ 初心者独りで使う場合: Enter（共通設定のみ適用）
→ 誰かを参考にしたい: メンターのプロファイルを選択
```

### 5. VS Codeを再起動

```plain
すぐに開発開始できます！🎉
```

---

## 🎓 チーム共通設定（.project-common）の管理

### 誰が更新する？

```plain
✅ テックリード
✅ プロジェクトオーナー
✅ チーム合意の上、誰でも提案可能
```

### どんな設定を入れる？

#### 推奨内容

- ✅ 必須拡張機能（ESLint、Prettier、Pylint等）
- ✅ コーディング規約設定（インデント、改行コード等）
- ✅ デバッグ設定
- ✅ タスク定義

#### 避けるべき内容

- ❌ 個人の好みが強い設定（テーマ、フォントサイズ等）
- ❌ OS固有の設定
- ❌ ローカルパスを含む設定

### 更新フロー

```plain
1. .project-common/ を編集
2. git commit & push（またはPull Request作成）
3. チームレビュー
4. マージ後、全員が git pull & vscode_setting.bat
```

---

## 🛡️ SafePreset機能（オプション）※直接Pythonを実行する場合のみ

「見た目は変えたくない！」という方向け：

```cmd
# venv有効化（必須）
. .\venv\Scripts\activate
# SafePreset有効化
python vscode\setting.py --safe-preset
```

### 保護される設定

- `workbench.colorTheme` (カラーテーマ)
- `workbench.iconTheme` (アイコンテーマ)
- `editor.fontSize` (フォントサイズ)
- `editor.fontFamily` (フォントファミリー)
- `window.zoomLevel` (ズームレベル)
- `terminal.integrated.fontSize` (ターミナルフォントサイズ)
- `terminal.integrated.fontFamily` (ターミナルフォント)

---

## 🔧 トラブルシューティング

### code CLI が見つからない

**エラー**: `'code' は、内部コマンドまたは外部コマンド...として認識されていません。`

**解決策**:
1. 環境変数PATHにVS Codeのインストールパスを追加
   - 例: `C:\Users\[ユーザー名]\AppData\Local\Programs\Microsoft VS Code\bin`
2. ターミナルを再起動

---

## 📮 お問い合わせ

質問や要望がある場合は、プロジェクトのテックリードまで連絡してください。

---

## 🎉 まとめ

### この仕組みで実現できること

```plain
✅ 新人が15分で即戦力
✅ チーム標準を自動適用
✅ ベテランのノウハウを継承
✅ 設定メンテナンスの自動化
✅ 属人化の解消
```

### 次のアクション

1. **今日**: 自分の設定をエクスポート
2. **今週**: チーム共通設定をレビュー
3. **継続**: 便利な設定を見つけたら共有

Let's build a better development environment together! 🚀
