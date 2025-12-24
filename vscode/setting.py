#!/usr/bin/env python3
"""
VSCodeの拡張機能とvscodeの設定を適用する（Windows専用）。

機能:
- 拡張機能は全プロファイルの論理和でレコード化し、プロジェクトメンバーの利用状況を一覧化
- 共通でインストールすべき拡張機能は、.project-common プロファイルに集約
- ユーザーは参考情報を含めた表に対して、追加したい拡張機能を0～n個選択
- 選択した拡張機能を `code --install-extension <id>` により一括インストール
- vscodeの設定は、profiles 配下の共通設定(.project-common)以外のプロファイルを一覧化
- ユーザーは表に対して、受け継ぎたいプロファイルを0～1個任意選択
- 選択したプロファイルと共通設定(.project-common)を、ユーザー既存設定にマージして適用

使用方法:
    python setting.py [--no-install-extensions] [--safe-preset] [--dry-run]
"""

import json
import os
import shutil
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

try:
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout,
        QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
        QCheckBox, QHeaderView, QRadioButton, QButtonGroup, QTextEdit,
        QSplitter, QWidget
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QColor
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class Colors:
    """コンソール出力の色定義"""
    if COLORAMA_AVAILABLE:
        CYAN = Fore.CYAN
        GREEN = Fore.GREEN
        YELLOW = Fore.YELLOW
        RED = Fore.RED
        GRAY = Fore.LIGHTBLACK_EX
        MAGENTA = Fore.MAGENTA
        WHITE = Fore.WHITE
        RESET = Style.RESET_ALL
    else:
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        GRAY = '\033[90m'
        MAGENTA = '\033[95m'
        WHITE = '\033[97m'
        RESET = '\033[0m'


# 定数定義
COMMON_PROFILE_NAME = ".project-common"
COMMON_EXTENSION_PREFIX = "☑️自動 "
COMMON_EXTENSION_STATUS = "🔄"
ENABLED_EXTENSION_STATUS = "✔️"
DISABLED_EXTENSION_STATUS = "💤"
COMMON_PROFILE_DISPLAY_NAME = "プロジェクト\n共通"

SAFE_PRESET_KEYS = [
    "workbench.colorTheme",
    "workbench.iconTheme",
    "editor.fontSize",
    "editor.fontFamily",
    "window.zoomLevel",
    "terminal.integrated.fontSize",
    "terminal.integrated.fontFamily"
]


def print_color(message: str, color: str = Colors.RESET):
    """色付きメッセージを出力"""
    if COLORAMA_AVAILABLE:
        print(f"{color}{message}{Style.RESET_ALL}")
    else:
        print(f"{color}{message}{Colors.RESET}")


def get_user_settings_dir() -> Path:
    """VS Code ユーザー設定ディレクトリを取得"""
    appdata = os.getenv('APPDATA')
    if not appdata:
        raise RuntimeError("APPDATA 環境変数が見つかりません")

    path = Path(appdata) / "Code" / "User"
    if not path.exists():
        raise RuntimeError(f"VS Code ユーザー設定ディレクトリが見つかりません: {path}")

    return path


def get_profiles_absolute_path(relative_path: str = "vscode\\profiles") -> Path:
    """プロファイルディレクトリの絶対パスを取得"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    absolute_path = project_root / relative_path

    if not absolute_path.exists():
        raise RuntimeError(f"プロファイルディレクトリが見つかりません: {absolute_path}")

    return absolute_path


def get_all_profile_folders(profiles_path: Path) -> List[str]:
    """全プロファイルフォルダを取得"""
    folders = []
    for item in profiles_path.iterdir():
        if item.is_dir():
            folders.append(item.name)
    return sorted(folders)


def get_selectable_profiles(profiles_path: Path) -> List[str]:
    """選択可能なプロファイル（ドット始まり以外）を取得"""
    all_folders = get_all_profile_folders(profiles_path)
    return [f for f in all_folders if not f.startswith('.')]


def get_extension_explanations(script_dir: Path) -> Dict[str, str]:
    """拡張機能の説明を読み込み"""
    explain_json_path = script_dir / "vscode-extensions-explain.json"

    if not explain_json_path.exists():
        print_color("  警告: vscode-extensions-explain.json が見つかりません", Colors.YELLOW)
        return {}

    try:
        with open(explain_json_path, 'r', encoding='utf-8-sig') as f:
            explanations = json.load(f)

        return {item['id']: item['explain'] for item in explanations}

    except Exception as e:
        print_color(f"  ✗ vscode-extensions-explain.json の読み込みに失敗しました", Colors.RED)
        print_color(f"    エラー: {e}", Colors.RED)
        raise RuntimeError("拡張機能の説明ファイルにシンタックスエラーがあります")


def get_extension_data(profile_path: Path, profile_name: str) -> List[Dict]:
    """プロファイルの拡張機能データを取得"""
    ext_json_path = profile_path / "vscode-extensions.json"

    if not ext_json_path.exists():
        print_color(f"  警告: {profile_name} の拡張機能リストが見つかりません", Colors.YELLOW)
        return []

    try:
        with open(ext_json_path, 'r', encoding='utf-8-sig') as f:
            extensions = json.load(f)

        # 要素が1つの場合でも必ずリストとして扱う
        if not isinstance(extensions, list):
            extensions = [extensions]

        return extensions

    except Exception as e:
        print_color(f"  ✗ {profile_name} の拡張機能リストの読み込みに失敗しました", Colors.RED)
        print_color(f"    パス: {ext_json_path}", Colors.GRAY)
        print_color(f"    エラー: {e}", Colors.RED)
        raise RuntimeError(f"拡張機能リストにシンタックスエラーがあります: {profile_name}")


def create_extension_matrix(
    profiles_path: Path,
    all_profiles: List[str],
    script_dir: Path
) -> Tuple[List[Dict], Dict[str, bool]]:
    """拡張機能マトリックスを作成"""
    print_color("\n拡張機能データを収集しています...", Colors.CYAN)

    # 拡張機能の説明を読み込み
    extension_explanations = get_extension_explanations(script_dir)
    print_color(f"  ✓ 拡張機能の説明: {len(extension_explanations)} 個", Colors.GRAY)

    # 全プロファイルの拡張機能を収集
    profile_extensions = {}
    all_extension_ids = set()

    for profile_name in all_profiles:
        profile_path = profiles_path / profile_name
        extensions = get_extension_data(profile_path, profile_name)

        ext_map = {}
        for ext in extensions:
            ext_id = ext['id']
            ext_map[ext_id] = {
                'enabled': ext.get('enabled', True),
                'version': ext.get('version')
            }
            all_extension_ids.add(ext_id)

        profile_extensions[profile_name] = ext_map
        print_color(f"  ✓ {profile_name} : {len(extensions)} 個の拡張機能", Colors.GRAY)

    # マトリックスを構築
    common_extensions = []
    other_extensions = []
    common_ext_ids = {}
    missing_explanation_count = 0

    for ext_id in sorted(all_extension_ids):
        explanation = extension_explanations.get(ext_id, "")

        if not explanation:
            missing_explanation_count += 1

        row = {
            'ExtensionID': ext_id,
            '説明': explanation
        }

        is_common_extension = False

        for profile_name in all_profiles:
            status = ""

            if ext_id in profile_extensions[profile_name]:
                ext_info = profile_extensions[profile_name][ext_id]
                if profile_name == COMMON_PROFILE_NAME:
                    status = COMMON_EXTENSION_STATUS
                    is_common_extension = True
                else:
                    status = ENABLED_EXTENSION_STATUS if ext_info['enabled'] else DISABLED_EXTENSION_STATUS

            display_name = COMMON_PROFILE_DISPLAY_NAME if profile_name == COMMON_PROFILE_NAME else profile_name
            row[display_name] = status

        if is_common_extension:
            row['ExtensionID'] = f"{COMMON_EXTENSION_PREFIX}{ext_id}"
            common_extensions.append(row)
            common_ext_ids[ext_id] = True
        else:
            other_extensions.append(row)

    matrix = other_extensions + common_extensions

    print_color(f"  合計 {len(all_extension_ids)} 個のユニークな拡張機能を検出しました", Colors.CYAN)
    print_color(f"    - 選択可能: {len(other_extensions)} 個", Colors.GRAY)
    print_color(f"    - 共通(必須): {len(common_extensions)} 個", Colors.GRAY)

    if missing_explanation_count > 0:
        print_color(f"    - 説明未設定: {missing_explanation_count} 個", Colors.YELLOW)
        print_color("      ⚠ vscode-extensions-explain.json のメンテナンスを推奨します\n", Colors.YELLOW)
    else:
        print()

    return matrix, common_ext_ids


class ExtensionSelectionDialog(QDialog):
    """拡張機能選択ダイアログ（ライトテーマ）"""

    def __init__(self, matrix: List[Dict], common_profile_name: str, parent=None):
        super().__init__(parent)
        self.matrix = matrix
        self.common_profile_name = common_profile_name
        self.selected_extensions = []
        # プロファイル列を抽出（ExtensionIDと説明以外）
        if matrix:
            self.profile_columns = [key for key in matrix[0].keys() if key not in ['ExtensionID', '説明']]
        else:
            self.profile_columns = []
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("拡張機能の選択")
        self.setGeometry(100, 100, 1400, 800)

        layout = QVBoxLayout()

        # タイトル
        title = QLabel("📦 インストールする拡張機能を選択してください")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        help_text = QLabel(
            f"※ {self.common_profile_name} の拡張機能は必須として自動的に含まれます\n"
            "※ チェックボックスで選択 → OKボタンで確定"
        )
        help_text.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(help_text)

        # 検索ボックス
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 検索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("拡張機能IDや説明で検索...")
        self.search_box.textChanged.connect(self.filter_table)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

        # スプリッター
        splitter = QSplitter(Qt.Orientation.Vertical)

        # テーブルコンテナ（固定列とスクロール可能なプロファイル列を横に並べる）
        table_container = QWidget()
        table_layout = QHBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        # 固定列テーブル（チェックボックス、拡張機能ID、説明）
        self.fixed_table = QTableWidget()
        self.fixed_table.setColumnCount(3)
        self.fixed_table.setHorizontalHeaderLabels(["", "拡張機能ID", "説明"])

        fixed_header = self.fixed_table.horizontalHeader()
        fixed_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        fixed_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        fixed_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.fixed_table.setColumnWidth(0, 50)
        self.fixed_table.setColumnWidth(1, 300)
        self.fixed_table.setSortingEnabled(False)  # ソートは無効化（プロファイルテーブルと同期が必要なため）
        self.fixed_table.setAlternatingRowColors(True)
        self.fixed_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fixed_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.fixed_table.setWordWrap(False)
        self.fixed_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.fixed_table.verticalHeader().setDefaultSectionSize(24)
        self.fixed_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.fixed_table.itemSelectionChanged.connect(self.on_fixed_table_selection_changed)

        # プロファイル列テーブル（スクロール可能）
        self.profile_table = QTableWidget()
        self.profile_table.setColumnCount(len(self.profile_columns))
        profile_headers = [col.replace("-", "\n") for col in self.profile_columns]
        self.profile_table.setHorizontalHeaderLabels(profile_headers)

        profile_header = self.profile_table.horizontalHeader()
        for i in range(len(self.profile_columns)):
            profile_header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            self.profile_table.setColumnWidth(i, 80)

        self.profile_table.setSortingEnabled(False)
        self.profile_table.setAlternatingRowColors(True)
        self.profile_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.profile_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.profile_table.setWordWrap(False)
        self.profile_table.verticalHeader().setVisible(False)
        self.profile_table.verticalHeader().setDefaultSectionSize(24)
        self.profile_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.profile_table.itemSelectionChanged.connect(self.on_profile_table_selection_changed)

        # プロファイル名の最大行数を計算してヘッダー高さを設定
        max_lines = max([col.count("-") + 1 for col in self.profile_columns]) if self.profile_columns else 1
        header_height = max(40, max_lines * 20)  # 1行あたり20px、最小40px
        fixed_header.setFixedHeight(header_height)
        profile_header.setFixedHeight(header_height)

        # 垂直スクロールを同期
        self.fixed_table.verticalScrollBar().valueChanged.connect(
            self.profile_table.verticalScrollBar().setValue
        )
        self.profile_table.verticalScrollBar().valueChanged.connect(
            self.fixed_table.verticalScrollBar().setValue
        )

        # 固定列とプロファイル列を横に配置
        table_layout.addWidget(self.fixed_table, stretch=3)
        table_layout.addWidget(self.profile_table, stretch=2)

        splitter.addWidget(table_container)

        # プレビュー
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_label = QLabel("📄 拡張機能説明")
        preview_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        preview_layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setPlaceholderText("拡張機能を選択すると説明が表示されます")
        preview_layout.addWidget(self.preview_text)

        splitter.addWidget(preview_widget)
        splitter.setSizes([600, 150])
        layout.addWidget(splitter)

        # 統計
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        layout.addWidget(self.stats_label)

        # ボタン
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("すべて選択")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("すべて解除")
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # ライトテーマスタイル（ExtensionSelectionDialog用）
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9f9f9;
                color: #333;
                gridline-color: #e0e0e0;
                selection-background-color: #cce8ff;
                selection-color: #000;
                border: 1px solid #ddd;
            }
            QTableWidget::item {
                padding: 2px 4px;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                color: #333;
                padding: 3px 2px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QLineEdit {
                background-color: white;
                color: #333;
                border: 1px solid #ccc;
                padding: 6px;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            QTextEdit {
                background-color: white;
                color: #333;
                border: 1px solid #ddd;
            }
        """)

    def load_data(self):
        """データをテーブルに読み込み"""
        self.fixed_table.setRowCount(len(self.matrix))
        self.profile_table.setRowCount(len(self.matrix))

        for row, ext_data in enumerate(self.matrix):
            ext_id = ext_data['ExtensionID']
            explain = ext_data.get('説明', '')

            is_common = ext_id.startswith("☑️自動 ")
            clean_id = ext_id.replace("☑️自動 ", "")

            # 固定列テーブル: チェックボックス
            checkbox = QCheckBox()
            checkbox.setChecked(is_common)
            checkbox.setEnabled(not is_common)
            checkbox.stateChanged.connect(self.update_stats)

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.fixed_table.setCellWidget(row, 0, checkbox_widget)

            # 固定列テーブル: ID
            id_item = QTableWidgetItem(f"☑️ {clean_id}" if is_common else clean_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if is_common:
                id_item.setForeground(QColor("#888"))
            self.fixed_table.setItem(row, 1, id_item)

            # 固定列テーブル: 説明
            explain_item = QTableWidgetItem(explain)
            explain_item.setFlags(explain_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if is_common:
                explain_item.setForeground(QColor("#888"))
            self.fixed_table.setItem(row, 2, explain_item)

            # プロファイル列テーブル: プロファイルごとに状態を表示
            for col_index, profile_name in enumerate(self.profile_columns):
                status = ext_data.get(profile_name, "")
                status_item = QTableWidgetItem(status)
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if is_common:
                    status_item.setForeground(QColor("#888"))
                self.profile_table.setItem(row, col_index, status_item)

        self.update_stats()

    def filter_table(self):
        """検索フィルタ"""
        search_text = self.search_box.text().lower()
        for row in range(self.fixed_table.rowCount()):
            id_item = self.fixed_table.item(row, 1)
            explain_item = self.fixed_table.item(row, 2)
            match = search_text in id_item.text().lower() or search_text in explain_item.text().lower()
            self.fixed_table.setRowHidden(row, not match)
            self.profile_table.setRowHidden(row, not match)

    def update_stats(self):
        """統計更新"""
        total = selected = common = 0
        for row in range(self.fixed_table.rowCount()):
            checkbox_widget = self.fixed_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            total += 1
            if checkbox.isChecked():
                selected += 1
                if not checkbox.isEnabled():
                    common += 1
        self.stats_label.setText(
            f"📊 合計: {total} 個 | 選択済み: {selected} 個 "
            f"（うち共通: {common} 個 / 任意選択: {selected - common} 個）"
        )

    def update_preview(self):
        """プレビュー更新"""
        selected_rows = self.fixed_table.selectedIndexes()
        if not selected_rows:
            self.preview_text.clear()
            return
        row = selected_rows[0].row()
        ext_id = self.fixed_table.item(row, 1).text().replace("☑️ ", "")
        explain = self.fixed_table.item(row, 2).text()
        preview_html = f"""
        <h3 style="color: #0078d4;">{ext_id}</h3>
        <p>{explain}</p>
        """
        self.preview_text.setHtml(preview_html)

    def on_fixed_table_selection_changed(self):
        """固定テーブルの選択が変更されたとき、プロファイルテーブルの選択も同期"""
        selected_rows = self.fixed_table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            self.profile_table.selectRow(row)
        self.update_preview()

    def on_profile_table_selection_changed(self):
        """プロファイルテーブルの選択が変更されたとき、固定テーブルの選択も同期"""
        selected_rows = self.profile_table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            self.fixed_table.selectRow(row)

    def select_all(self):
        """すべて選択"""
        for row in range(self.fixed_table.rowCount()):
            checkbox_widget = self.fixed_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox.isEnabled():
                checkbox.setChecked(True)

    def deselect_all(self):
        """すべて解除"""
        for row in range(self.fixed_table.rowCount()):
            checkbox_widget = self.fixed_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox.isEnabled():
                checkbox.setChecked(False)

    def accept(self):
        """OK押下時"""
        self.selected_extensions = []
        for row in range(self.fixed_table.rowCount()):
            checkbox_widget = self.fixed_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox.isChecked():
                ext_id = self.fixed_table.item(row, 1).text().replace("☑️ ", "")
                self.selected_extensions.append(ext_id)
        super().accept()


def show_extension_selection_ui(matrix: List[Dict]) -> Optional[List[str]]:
    """拡張機能選択UIを表示（キャンセル時はNoneを返す）"""
    if PYQT6_AVAILABLE:
        # GUIモード（QApplicationは既に作成済み）
        dialog = ExtensionSelectionDialog(matrix, COMMON_PROFILE_DISPLAY_NAME)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_extensions
        else:
            # キャンセルされた場合はNoneを返す
            return None
    else:
        # フォールバック: CLI モード
        print_color("\n拡張機能の選択:", Colors.CYAN)
        print_color(f"※ {COMMON_PROFILE_DISPLAY_NAME} の拡張機能は必須として自動的に含まれます", Colors.YELLOW)
        print()

        selectable = [row for row in matrix if not row['ExtensionID'].startswith(COMMON_EXTENSION_PREFIX)]

        if not selectable:
            print_color("選択可能な拡張機能がありません", Colors.YELLOW)
            return []

        for i, row in enumerate(selectable, 1):
            ext_id = row['ExtensionID']
            explanation = row.get('説明', '')
            if explanation:
                print(f"  {i}. {ext_id}")
                print(f"     {explanation}")
            else:
                print(f"  {i}. {ext_id}")

        print()
        print("インストールする拡張機能の番号を入力してください（カンマ区切り、または 'all' で全選択、Enter でキャンセル）:")
        user_input = input("入力: ").strip()

        if not user_input:
            # Enterでキャンセル = Noneを返す
            return None

        if user_input.lower() == 'all':
            return [row['ExtensionID'] for row in selectable]

        selected = []
        try:
            numbers = [int(n.strip()) for n in user_input.split(',')]
            for num in numbers:
                if 1 <= num <= len(selectable):
                    selected.append(selectable[num - 1]['ExtensionID'])
                else:
                    print_color(f"警告: 無効な番号 {num} はスキップされました", Colors.YELLOW)
        except ValueError:
            print_color("警告: 無効な入力形式です。数字をカンマ区切りで入力してください。", Colors.YELLOW)
            return []

        return selected


def get_currently_installed_extensions() -> Set[str]:
    """現在インストール済みの拡張機能を取得"""
    code_path = shutil.which('code')
    if not code_path:
        print_color("  警告: code CLI が見つからないため、現在の拡張機能の取得をスキップします", Colors.YELLOW)
        return set()

    try:
        # SSL証明書エラー対策（インストールと同じ設定を使用）
        env = os.environ.copy()
        env['NODE_TLS_REJECT_UNAUTHORIZED'] = '0'

        result = subprocess.run(
            f'"{code_path}" --list-extensions',
            capture_output=True,
            text=True,
            env=env,
            shell=True,
            check=True
        )

        return {line.strip().lower() for line in result.stdout.strip().split('\n') if line.strip()}

    except Exception as e:
        print_color(f"  警告: 拡張機能一覧の取得に失敗しました (SSL証明書エラーの可能性)", Colors.YELLOW)
        print_color(f"    エラー詳細: {e}", Colors.GRAY)
        return set()


def install_selected_extensions(
    selected_extensions: List[str],
    common_extensions: Dict[str, bool],
    dry_run: bool
) -> Dict[str, List[str]]:
    """選択された拡張機能をインストール"""
    extensions_to_install = set(selected_extensions)
    extensions_to_install.update(common_extensions.keys())

    if not extensions_to_install:
        print_color("インストールする拡張機能が選択されていません。", Colors.YELLOW)
        return {'installed': [], 'skipped': [], 'failed': []}

    print_color(f"\nインストール対象の拡張機能: {len(extensions_to_install)} 個", Colors.CYAN)

    installed = []
    skipped = []
    failed = []

    currently_installed = get_currently_installed_extensions()

    for ext_id in sorted(extensions_to_install):
        if ext_id.lower() in currently_installed:
            print_color(f"  ⏭  {ext_id} (既にインストール済み)", Colors.GRAY)
            skipped.append(ext_id)
            continue

        if dry_run:
            print_color(f"  [DryRun] インストール: {ext_id}", Colors.MAGENTA)
            installed.append(ext_id)
        else:
            print_color(f"  📦 インストール中: {ext_id} ...", Colors.YELLOW)

            try:
                # code コマンドのフルパスを取得
                code_path = shutil.which('code')
                if not code_path:
                    print_color(f"    ✗ エラー: code コマンドが見つかりません", Colors.RED)
                    failed.append(ext_id)
                    continue

                # デバッグ情報（初回のみ表示）
                if ext_id == sorted(extensions_to_install)[0]:
                    print_color(f"    [Debug] code path: {code_path}", Colors.GRAY)

                # SSL証明書エラー対策
                env = os.environ.copy()
                env['NODE_TLS_REJECT_UNAUTHORIZED'] = '0'

                # Windowsの場合、.cmdファイルはshell=Trueで実行する必要がある
                # SSL証明書エラー対策として --strict-ssl false を追加
                result = subprocess.run(
                    f'"{code_path}" --install-extension {ext_id} --force --strict-ssl false',
                    capture_output=True,
                    text=True,
                    env=env,
                    shell=True
                )

                if result.returncode == 0:
                    print_color("    ✓ 完了", Colors.GREEN)
                    installed.append(ext_id)
                else:
                    print_color(f"    ✗ 失敗 (終了コード: {result.returncode})", Colors.RED)
                    if result.stderr:
                        for line in result.stderr.strip().split('\n'):
                            if 'NODE_TLS_REJECT_UNAUTHORIZED' not in line:
                                print_color(f"      {line}", Colors.GRAY)
                    failed.append(ext_id)

            except FileNotFoundError as e:
                print_color(f"    ✗ エラー: code コマンドが実行できません - {e}", Colors.RED)
                print_color(f"      VS Code の 'Shell Command: Install code command in PATH' を実行してください", Colors.YELLOW)
                failed.append(ext_id)
            except Exception as e:
                print_color(f"    ✗ エラー: {e}", Colors.RED)
                failed.append(ext_id)

    print_color("\n拡張機能インストール結果:", Colors.CYAN)
    print_color(f"  新規インストール: {len(installed)} 個", Colors.GREEN)
    print_color(f"  スキップ（既存）: {len(skipped)} 個", Colors.GRAY)
    if failed:
        print_color(f"  失敗: {len(failed)} 個", Colors.RED)

    return {
        'installed': installed,
        'skipped': skipped,
        'failed': failed
    }


def read_json_file(path: Path) -> OrderedDict:
    """JSONファイルを読み込んでOrderedDictとして返す"""
    if not path.exists():
        return OrderedDict()

    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)

        return data if isinstance(data, OrderedDict) else OrderedDict(sorted(data.items()))

    except Exception as e:
        file_name = path.name
        print_color(f"  ✗ JSON読み込みエラー: {file_name}", Colors.RED)
        print_color(f"    パス: {path}", Colors.GRAY)
        print_color(f"    エラー: {e}", Colors.RED)
        raise RuntimeError(f"JSONファイルの読み込みに失敗しました: {file_name}")


def merge_settings(
    base: OrderedDict,
    override: OrderedDict,
    source: str,
    merge_log: List[Dict]
) -> OrderedDict:
    """設定をマージ"""
    result = OrderedDict(base)

    for key in sorted(override.keys()):
        override_value = override[key]

        if key in result:
            base_value = result[key]

            # 値が同じ場合はスキップ
            if base_value == override_value:
                continue

            # オブジェクト（辞書）の場合は再帰的にマージ
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = merge_settings(
                    OrderedDict(base_value),
                    OrderedDict(override_value),
                    source,
                    merge_log
                )
                merge_log.append({
                    'Key': key,
                    'Action': '再帰マージ',
                    'Source': source,
                    'OldValue': '[Object]',
                    'NewValue': '[Object]'
                })

            # 配列の場合はユニオン化
            elif isinstance(base_value, list) and isinstance(override_value, list):
                union_array = []
                seen = set()

                for item in base_value:
                    item_str = json.dumps(item, ensure_ascii=False, sort_keys=True) if not isinstance(item, str) else item
                    if item_str not in seen:
                        union_array.append(item)
                        seen.add(item_str)

                for item in override_value:
                    item_str = json.dumps(item, ensure_ascii=False, sort_keys=True) if not isinstance(item, str) else item
                    if item_str not in seen:
                        union_array.append(item)
                        seen.add(item_str)

                # 文字列配列の場合はソート
                if all(isinstance(item, str) for item in union_array):
                    union_array.sort()

                result[key] = union_array
                merge_log.append({
                    'Key': key,
                    'Action': '配列マージ',
                    'Source': source,
                    'OldValue': f'[{len(base_value)} items]',
                    'NewValue': f'[{len(union_array)} items]'
                })

            else:
                # プリミティブ値の場合は上書き
                old_value = f'[{len(base_value)} items]' if isinstance(base_value, list) else str(base_value)
                new_value = f'[{len(override_value)} items]' if isinstance(override_value, list) else str(override_value)

                result[key] = override_value
                merge_log.append({
                    'Key': key,
                    'Action': '上書き',
                    'Source': source,
                    'OldValue': old_value,
                    'NewValue': new_value
                })
        else:
            # 新規キー
            new_value = f'[{len(override_value)} items]' if isinstance(override_value, list) else '[Object]' if isinstance(override_value, dict) else str(override_value)

            result[key] = override_value
            merge_log.append({
                'Key': key,
                'Action': '追加',
                'Source': source,
                'OldValue': '[なし]',
                'NewValue': new_value
            })

    return result


def protect_safe_preset_keys(
    merged_settings: OrderedDict,
    user_settings: OrderedDict,
    safe_keys: List[str],
    merge_log: List[Dict]
) -> OrderedDict:
    """セーフプリセットキーを保護"""
    for key in safe_keys:
        if key in user_settings:
            user_value = user_settings[key]

            if key in merged_settings and merged_settings[key] != user_value:
                merged_settings[key] = user_value
                merge_log.append({
                    'Key': key,
                    'Action': '保護（SafePreset）',
                    'Source': 'ユーザー既存設定',
                    'OldValue': str(merged_settings.get(key)),
                    'NewValue': str(user_value)
                })

    return merged_settings


class ProfileSelectionDialog(QDialog):
    """設定プロファイル選択ダイアログ（ライトテーマ）"""

    def __init__(self, profiles: List[Dict], parent=None):
        super().__init__(parent)
        self.profiles = profiles
        self.selected_profile = None
        self.init_ui()

    def init_ui(self):
        """UIの初期化"""
        self.setWindowTitle("設定プロファイルの選択")
        self.setGeometry(150, 150, 900, 600)

        layout = QVBoxLayout()

        title = QLabel("⚙️ 適用する設定プロファイルを選択してください")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        help_text = QLabel("※ 1つのプロファイルを選択するか、「共通設定のみ」を選択できます")
        help_text.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(help_text)

        # ラジオボタングループ
        self.radio_group = QButtonGroup()

        # テーブル
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "設定プロファイル", "画面カラーテーマ", "アイコンテーマ"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(1, 250)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.load_profiles()
        layout.addWidget(self.table)

        # ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # ライトテーマスタイル
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9f9f9;
                color: #333;
                gridline-color: #e0e0e0;
                selection-background-color: #cce8ff;
                selection-color: #000;
                border: 1px solid #ddd;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                color: #333;
                padding: 6px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QRadioButton {
                color: #333;
            }
        """)

    def load_profiles(self):
        """プロファイルをテーブルに読み込み"""
        all_items = [
            {
                'name': None,
                'display_name': 'プロジェクト共通設定のみ',
                'color_theme': '変更しません',
                'icon_theme': '変更しません'
            }
        ] + self.profiles

        self.table.setRowCount(len(all_items))

        for row, profile in enumerate(all_items):
            radio = QRadioButton()
            if row == 0:
                radio.setChecked(True)

            self.radio_group.addButton(radio, row)

            radio_widget = QWidget()
            radio_layout = QHBoxLayout(radio_widget)
            radio_layout.addWidget(radio)
            radio_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, radio_widget)

            name_item = QTableWidgetItem(profile.get('display_name', profile['name']))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if row == 0:
                name_item.setForeground(QColor("#0078d4"))
                name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row, 1, name_item)

            color_item = QTableWidgetItem(profile['color_theme'])
            color_item.setFlags(color_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, color_item)

            icon_item = QTableWidgetItem(profile['icon_theme'])
            icon_item.setFlags(icon_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, icon_item)

    def accept(self):
        """OK押下時"""
        checked_id = self.radio_group.checkedId()
        if checked_id == 0:
            self.selected_profile = None
        else:
            self.selected_profile = self.profiles[checked_id - 1]['name']
        super().accept()


def show_profile_selection_ui(selectable_profiles: List[str], profiles_path: Path) -> Optional[str]:
    """設定プロファイル選択UIを表示"""
    if not selectable_profiles:
        print_color("\n選択可能なプロファイルがありません。", Colors.YELLOW)
        return None

    if PYQT6_AVAILABLE:
        # GUIモード（QApplicationは既に作成済み）
        # プロファイル情報を収集
        profiles = []
        for profile_name in selectable_profiles:
            settings_path = profiles_path / profile_name / "settings.json"
            settings = read_json_file(settings_path)

            profiles.append({
                'name': profile_name,
                'color_theme': settings.get("workbench.colorTheme", "変更しません"),
                'icon_theme': settings.get("workbench.iconTheme", "変更しません")
            })

        dialog = ProfileSelectionDialog(profiles)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_profile
        else:
            return None
    else:
        # フォールバック: CLI モード
        print_color("\n設定プロファイルの選択:", Colors.CYAN)
        print_color("※ 1つのプロファイルを選択するか、Enter で共通設定のみ適用できます", Colors.YELLOW)
        print()

        profile_objects = []
        for i, profile_name in enumerate(selectable_profiles, 1):
            settings_path = profiles_path / profile_name / "settings.json"
            settings = read_json_file(settings_path)

            color_theme = settings.get("workbench.colorTheme", "変更しません")
            icon_theme = settings.get("workbench.iconTheme", "変更しません")

            profile_objects.append({
                'index': i,
                'name': profile_name,
                'color_theme': color_theme,
                'icon_theme': icon_theme
            })

            print(f"  {i}. {profile_name}")
            print(f"     画面カラーテーマ: {color_theme}")
            print(f"     アイコンテーマ: {icon_theme}")

        print()
        print(f"  0. {COMMON_PROFILE_DISPLAY_NAME}のみ（テーマ変更なし）")
        print()
        print("適用するプロファイルの番号を入力してください（Enter で共通設定のみ）:")

        user_input = input("入力: ").strip()

        if not user_input or user_input == '0':
            return None

        try:
            index = int(user_input)
            if 1 <= index <= len(selectable_profiles):
                return selectable_profiles[index - 1]
            else:
                print_color(f"無効な番号です。1 から {len(selectable_profiles)} の範囲で入力してください。", Colors.RED)
                return None
        except ValueError:
            print_color("無効な入力です。", Colors.RED)
            return None


def backup_user_settings(user_settings_path: Path, dry_run: bool) -> Optional[Path]:
    """ユーザー設定をバックアップ"""
    if not user_settings_path.exists():
        print_color("バックアップ対象の settings.json が存在しません。スキップします。", Colors.YELLOW)
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = user_settings_path.parent / f"settings.backup-{timestamp}.json"

    if dry_run:
        print_color(f"[DryRun] バックアップ先: {backup_path}", Colors.MAGENTA)
        return backup_path

    try:
        shutil.copy2(user_settings_path, backup_path)
        print_color(f"✓ 既存設定をバックアップしました: {backup_path}", Colors.GREEN)
        return backup_path
    except Exception as e:
        print_color(f"警告: バックアップに失敗しました: {e}", Colors.YELLOW)
        return None


def save_merged_settings(merged_settings: OrderedDict, user_settings_path: Path, dry_run: bool):
    """マージした設定を保存"""
    if dry_run:
        print_color("[DryRun] 設定の保存はスキップされました", Colors.MAGENTA)
        return

    try:
        with open(user_settings_path, 'w', encoding='utf-8') as f:
            json.dump(merged_settings, f, ensure_ascii=False, indent=4)

        print_color(f"✓ マージした設定を保存しました: {user_settings_path}", Colors.GREEN)
    except Exception as e:
        raise RuntimeError(f"設定の保存に失敗しました: {e}")


def write_merge_report(
    merge_log: List[Dict],
    report_path: Path,
    extension_result: Dict[str, List[str]],
    selected_profile: Optional[str],
    use_safe_preset: bool,
    dry_run: bool
):
    """マージレポートを出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "# VS Code 設定・拡張機能 適用レポート",
        "",
        f"生成日時: {timestamp}",
        f"モード: {'DryRun（適用なし）' if dry_run else '実行'}",
        "",
        "## 拡張機能インストール結果",
        "",
        f"- 新規インストール: {len(extension_result['installed'])} 個",
        f"- スキップ（既存）: {len(extension_result['skipped'])} 個",
        f"- 失敗: {len(extension_result['failed'])} 個",
        "",
        "### 新規インストールされた拡張機能"
    ]

    if extension_result['installed']:
        for ext in extension_result['installed']:
            report_lines.append(f"- {ext}")
    else:
        report_lines.append("（なし）")

    report_lines.extend([
        "",
        "### 失敗した拡張機能"
    ])

    if extension_result['failed']:
        for ext in extension_result['failed']:
            report_lines.append(f"- {ext}")
    else:
        report_lines.append("（なし）")

    report_lines.extend([
        "",
        "## 設定マージ結果",
        "",
        "### 適用したプロファイル"
    ])

    if selected_profile:
        report_lines.append(f"- {selected_profile}")
    else:
        report_lines.append("（選択なし）")

    report_lines.extend([
        f"- 共通設定: {COMMON_PROFILE_NAME}（常に適用）",
        f"- SafePreset: {'有効' if use_safe_preset else '無効'}",
        "",
        "### マージの詳細",
        "",
        "| キー | アクション | ソース | 旧値 | 新値 |",
        "|------|-----------|--------|------|------|"
    ])

    if merge_log:
        for log in merge_log:
            report_lines.append(
                f"| `{log['Key']}` | {log['Action']} | {log['Source']} | `{log['OldValue']}` | `{log['NewValue']}` |"
            )
    else:
        report_lines.append("| - | - | - | - | - |")

    report_lines.extend([
        "",
        "---",
        "*このレポートは自動生成されました*"
    ])

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        print_color(f"\n✓ レポートを保存しました: {report_path}", Colors.GREEN)
    except Exception as e:
        print_color(f"警告: レポートの保存に失敗しました: {e}", Colors.YELLOW)


def show_console_summary(
    merge_log: List[Dict],
    extension_result: Dict[str, List[str]],
    selected_profile: Optional[str],
    use_safe_preset: bool,
    dry_run: bool
):
    """コンソールサマリーを表示"""
    print_color("\n", Colors.WHITE)
    print_color("═══════════════════════════════════════════════════════════", Colors.CYAN)
    print_color("                    処理完了サマリー", Colors.CYAN)
    print_color("═══════════════════════════════════════════════════════════", Colors.CYAN)

    if dry_run:
        print_color("[DryRun モード - 実際の適用は行われていません]", Colors.MAGENTA)

    print_color("\n【拡張機能】", Colors.YELLOW)
    print_color(f"  新規インストール: {len(extension_result['installed'])} 個", Colors.GREEN)
    print_color(f"  スキップ（既存）: {len(extension_result['skipped'])} 個", Colors.GRAY)
    if extension_result['failed']:
        print_color(f"  失敗: {len(extension_result['failed'])} 個", Colors.RED)

    print_color("\n【設定プロファイル】", Colors.YELLOW)
    if selected_profile:
        print_color(f"  選択されたプロファイル: {selected_profile}", Colors.WHITE)
    else:
        print_color("  選択されたプロファイル: なし", Colors.GRAY)
    print_color(f"  共通設定: {COMMON_PROFILE_NAME}（常に適用）", Colors.WHITE)
    print_color(f"  SafePreset: {'有効' if use_safe_preset else '無効'}", Colors.WHITE)

    print_color("\n【設定マージ】", Colors.YELLOW)
    additions = sum(1 for log in merge_log if log['Action'] == '追加')
    overwrites = sum(1 for log in merge_log if log['Action'] == '上書き')
    protections = sum(1 for log in merge_log if log['Action'] == '保護（SafePreset）')

    print_color(f"  追加: {additions} 個", Colors.GREEN)
    print_color(f"  上書き: {overwrites} 個", Colors.YELLOW)
    if protections > 0:
        print_color(f"  保護: {protections} 個", Colors.CYAN)

    print_color("\n═══════════════════════════════════════════════════════════", Colors.CYAN)


def main(
    install_extensions: bool = True,
    use_safe_preset: bool = False,
    dry_run: bool = False
):
    """メイン処理"""
    # PyQt6が利用可能な場合、QApplicationを最初に作成（複数ダイアログで共有）
    if PYQT6_AVAILABLE:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

    try:
        print_color("═══════════════════════════════════════════════════════════", Colors.CYAN)
        print_color("  VS Code 設定・拡張機能 適用スクリプト (Windows専用)", Colors.CYAN)
        print_color("═══════════════════════════════════════════════════════════", Colors.CYAN)

        script_dir = Path(__file__).parent

        # 1. 前提条件チェック
        print_color("\n[1/6] 前提条件のチェック...", Colors.YELLOW)

        code_path = shutil.which('code')
        code_cli_exists = code_path is not None
        if not code_cli_exists:
            print_color("  警告: code CLI が見つかりません。拡張機能のインストールはスキップされます。", Colors.YELLOW)
        else:
            print_color(f"  ✓ code CLI: {code_path}", Colors.GREEN)

        user_settings_dir = get_user_settings_dir()
        user_settings_path = user_settings_dir / "settings.json"
        print_color(f"  ✓ ユーザー設定ディレクトリ: {user_settings_dir}", Colors.GREEN)

        profiles_path = get_profiles_absolute_path()
        print_color(f"  ✓ プロファイルディレクトリ: {profiles_path}", Colors.GREEN)

        # SSL証明書エラー回避のため、http.proxyStrictSSLをfalseに設定
        try:
            if os.path.exists(user_settings_path):
                with open(user_settings_path, 'r', encoding='utf-8-sig') as f:
                    current_settings = json.load(f)
            else:
                current_settings = {}

            # http.proxyStrictSSLの確認と設定
            needs_update = False
            if 'http.proxyStrictSSL' not in current_settings:
                print_color("  ✓ SSL証明書検証を無効化します (http.proxyStrictSSL: false)", Colors.CYAN)
                needs_update = True
            elif current_settings.get('http.proxyStrictSSL') is not False:
                print_color("  ✓ SSL証明書検証を無効化します (http.proxyStrictSSL: false)", Colors.CYAN)
                needs_update = True

            if needs_update:
                current_settings['http.proxyStrictSSL'] = False
                os.makedirs(os.path.dirname(user_settings_path), exist_ok=True)
                with open(user_settings_path, 'w', encoding='utf-8') as f:
                    json.dump(current_settings, f, indent=4, ensure_ascii=False)
                print_color("  ✓ settings.jsonに設定を追加しました", Colors.GREEN)
            else:
                print_color("  ✓ SSL証明書検証は既に無効化されています", Colors.GREEN)
        except Exception as e:
            print_color(f"  ⚠ SSL設定の追加に失敗しました: {e}", Colors.YELLOW)
            print_color("  ⚠ 拡張機能のインストールでSSLエラーが発生する可能性があります", Colors.YELLOW)

        # 2. 拡張機能の処理
        print_color("\n[2/6] 拡張機能の処理...", Colors.YELLOW)

        all_profiles = get_all_profile_folders(profiles_path)
        extension_matrix, common_extensions = create_extension_matrix(profiles_path, all_profiles, script_dir)

        selected_extensions = show_extension_selection_ui(extension_matrix)

        # キャンセルチェック
        if selected_extensions is None:
            print_color("\n拡張機能の選択がキャンセルされました", Colors.YELLOW)
            extension_result = {'installed': [], 'skipped': [], 'failed': []}
            print_color("\n[3/6] 拡張機能のインストール - スキップ", Colors.YELLOW)
        else:
            print_color(f"\n選択された拡張機能: {len(selected_extensions)} 個", Colors.CYAN)

            extension_result = {'installed': [], 'skipped': [], 'failed': []}

            if not code_cli_exists:
                print_color("\n[3/6] 拡張機能のインストール - スキップ (code CLI が見つかりません)", Colors.YELLOW)
            elif not install_extensions:
                print_color("\n[3/6] 拡張機能のインストール - スキップ (--no-install-extensions)", Colors.YELLOW)
            else:
                print_color("\n[3/6] 拡張機能のインストール...", Colors.YELLOW)
                extension_result = install_selected_extensions(selected_extensions, common_extensions, dry_run)

        # 4. 設定プロファイルの選択
        print_color("\n[4/6] 設定プロファイルの選択...", Colors.YELLOW)

        selectable_profiles = get_selectable_profiles(profiles_path)
        print_color(f"選択可能なプロファイル: {len(selectable_profiles)} 個", Colors.CYAN)

        selected_profile = show_profile_selection_ui(selectable_profiles, profiles_path)

        if selected_profile:
            print_color(f"選択されたプロファイル: {selected_profile}", Colors.CYAN)
        else:
            print_color("プロファイルが選択されませんでした。共通設定のみ適用されます。", Colors.YELLOW)

        # 5. 設定のマージ
        print_color("\n[5/6] 設定のマージ...", Colors.YELLOW)

        backup_user_settings(user_settings_path, dry_run)

        user_settings = read_json_file(user_settings_path)
        print_color(f"  ✓ ユーザー既存設定を読み込みました ({len(user_settings)} キー)", Colors.GREEN)

        merge_log = []
        merged_settings = OrderedDict(user_settings)

        # 共通設定を先に適用
        common_settings_path = profiles_path / COMMON_PROFILE_NAME / "settings.json"
        common_settings = read_json_file(common_settings_path)

        if common_settings:
            print_color(f"  マージ中: {COMMON_PROFILE_NAME} ({len(common_settings)} キー)", Colors.CYAN)
            merged_settings = merge_settings(merged_settings, common_settings, COMMON_PROFILE_NAME, merge_log)
        else:
            print_color(f"  スキップ: {COMMON_PROFILE_NAME} (設定なし)", Colors.GRAY)

        # 選択されたプロファイルを最後に適用
        if selected_profile:
            profile_settings_path = profiles_path / selected_profile / "settings.json"
            profile_settings = read_json_file(profile_settings_path)

            if profile_settings:
                print_color(f"  マージ中: {selected_profile} ({len(profile_settings)} キー) ← 最優先", Colors.CYAN)
                merged_settings = merge_settings(merged_settings, profile_settings, selected_profile, merge_log)
            else:
                print_color(f"  スキップ: {selected_profile} (設定なし)", Colors.GRAY)

        # SafePreset の適用
        if use_safe_preset:
            print_color("  SafePreset を適用中...", Colors.YELLOW)
            merged_settings = protect_safe_preset_keys(merged_settings, user_settings, SAFE_PRESET_KEYS, merge_log)

        # 設定を保存
        save_merged_settings(merged_settings, user_settings_path, dry_run)

        # 6. レポート出力
        print_color("\n[6/6] レポート出力...", Colors.YELLOW)

        report_path = script_dir / "vscode-setting-merge-report.md"
        write_merge_report(merge_log, report_path, extension_result, selected_profile, use_safe_preset, dry_run)

        show_console_summary(merge_log, extension_result, selected_profile, use_safe_preset, dry_run)

        print_color("\n処理が完了しました！", Colors.GREEN)

    except Exception as e:
        print_color(f"\n✗ エラーが発生しました: {e}", Colors.RED)
        import traceback
        print_color(f"スタックトレース:\n{traceback.format_exc()}", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="VSCodeの設定と拡張機能を適用"
    )
    parser.add_argument(
        '--no-install-extensions',
        action='store_true',
        help='拡張機能のインストールをスキップ'
    )
    parser.add_argument(
        '--safe-preset',
        action='store_true',
        help='外観系設定をユーザー既存値で保護'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='変更を適用せずにレポートのみ表示'
    )

    args = parser.parse_args()

    main(
        install_extensions=not args.no_install_extensions,
        use_safe_preset=args.safe_preset,
        dry_run=args.dry_run
    )
