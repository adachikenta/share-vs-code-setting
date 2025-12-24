#!/usr/bin/env python3
"""
VS Code の現在のユーザー設定と拡張一覧を、選択/新規のプロファイルフォルダへ保存します（Windows専用）。

機能:
- 既存の profiles 配下のフォルダ（ドット始まり以外）から選択、または新規作成
- settings.json / keybindings.json / snippets をコピー（存在するもののみ）
- 拡張一覧を 'code --list-extensions --show-versions' で取得し、JSONへ整形して保存
- 保存先: vscode\profiles\<alias>\

使用方法:
    python export_profile.py [--alias <profile_name>] [--include-keybindings] [--include-snippets]
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class Colors:
    """コンソール出力の色定義"""
    if COLORAMA_AVAILABLE:
        CYAN = Fore.CYAN
        GREEN = Fore.GREEN
        YELLOW = Fore.YELLOW
        RED = Fore.RED
        GRAY = Fore.LIGHTBLACK_EX
        RESET = Style.RESET_ALL
    else:
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        GRAY = '\033[90m'
        RESET = '\033[0m'


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

    absolute_path.mkdir(parents=True, exist_ok=True)

    return absolute_path


def get_existing_profiles(profiles_path: Path) -> List[str]:
    """既存のプロファイル一覧を取得（ドット始まり以外）"""
    if not profiles_path.exists():
        return []

    profiles = []
    for item in profiles_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            profiles.append(item.name)

    return sorted(profiles)


def select_or_create_profile(profiles_path: Path) -> str:
    """プロファイルを選択または新規作成"""
    existing = get_existing_profiles(profiles_path)

    print_color("\n既存プロファイル：", Colors.CYAN)
    if existing:
        for i, profile in enumerate(existing, 1):
            print(f"  {i}. {profile}")
    else:
        print("  （なし）")

    print()
    print("プロファイルを選択する場合は番号、または新規名（例: suzuki-taro）を入力してください。")

    while True:
        user_input = input("入力: ").strip()

        if not user_input:
            print_color("入力が空です。もう一度入力してください。", Colors.YELLOW)
            continue

        # 数字の場合は既存プロファイルから選択
        if user_input.isdigit():
            index = int(user_input)
            if 1 <= index <= len(existing):
                return existing[index - 1]
            else:
                print_color(f"無効な番号です。1 から {len(existing)} の範囲で入力してください。", Colors.RED)
                continue

        # 新規プロファイル名の検証（半角英数字とハイフンのみ）
        if not re.match(r'^[a-z0-9-]+$', user_input):
            print_color("不正なプロファイル名です。半角英数字とハイフンのみを使用してください。", Colors.RED)
            continue

        return user_input


def copy_file_if_exists(src: Path, dst: Path, file_name: str):
    """ファイルが存在する場合はコピー"""
    if src.exists():
        shutil.copy2(src, dst)
        print(f"{file_name} を保存しました。")
    else:
        print(f"{file_name} は見つかりません。スキップします。")


def copy_directory_if_exists(src: Path, dst: Path, dir_name: str):
    """ディレクトリが存在する場合はコピー"""
    if src.exists() and src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"{dir_name} を保存しました。")
    else:
        print(f"{dir_name} は見つかりません。スキップします。")


def export_extensions(profile_dir: Path) -> Optional[List[Dict]]:
    """拡張機能一覧を取得してJSONとして保存"""
    # code CLI の確認
    code_cmd = shutil.which('code')
    if not code_cmd:
        print_color("警告: 'code' CLI が見つからないため、拡張一覧の保存をスキップします。", Colors.YELLOW)
        return None

    try:
        # 拡張機能一覧を取得
        result = subprocess.run(
            [code_cmd, '--list-extensions', '--show-versions'],
            capture_output=True,
            text=True,
            check=True,
            shell=False
        )

        lines = result.stdout.strip().split('\n')
        if not lines or (len(lines) == 1 and not lines[0]):
            print_color("警告: 拡張一覧を取得できませんでした。", Colors.YELLOW)
            return None

        # 拡張機能情報を解析
        extensions = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = re.match(r'^(.+)@(.+)$', line)
            if match:
                ext_id = match.group(1)
                version = match.group(2)
                extensions.append({
                    "id": ext_id,
                    "version": version,
                    "enabled": True
                })
            else:
                extensions.append({
                    "id": line,
                    "version": None,
                    "enabled": True
                })

        # JSON形式で保存（既存ファイルがあれば削除してから作成）
        ext_json_path = profile_dir / "vscode-extensions.json"
        if ext_json_path.exists():
            ext_json_path.unlink()

        with open(ext_json_path, 'w', encoding='utf-8') as f:
            json.dump(extensions, f, ensure_ascii=False, indent=4)

        print(f"拡張一覧を保存しました: {ext_json_path}")
        return extensions

    except FileNotFoundError as e:
        print_color("警告: 'code' コマンドが実行できませんでした。VS Code CLIがインストールされていない可能性があります。", Colors.YELLOW)
        print_color("  VS Codeで「Ctrl+Shift+P」を押して「シェルコマンド: PATH内にcodeコマンドをインストールします」を実行してください。", Colors.GRAY)
        return None
    except subprocess.CalledProcessError as e:
        print_color(f"警告: 拡張一覧の取得に失敗しました: {e}", Colors.YELLOW)
        return None
    except Exception as e:
        print_color(f"警告: 拡張一覧の処理中にエラーが発生しました: {e}", Colors.YELLOW)
        return None


def check_extension_explanations(installed_extensions: List[Dict], script_dir: Path):
    """拡張機能の説明が登録されているかチェック"""
    explain_json_path = script_dir / "vscode-extensions-explain.json"

    if not explain_json_path.exists():
        print_color("警告: vscode-extensions-explain.json が見つかりません。", Colors.YELLOW)
        return

    try:
        with open(explain_json_path, 'r', encoding='utf-8') as f:
            explain_data = json.load(f)

        explained_ids = {item['id'] for item in explain_data}

        missing_explanations = []
        for ext in installed_extensions:
            if ext['id'] not in explained_ids:
                missing_explanations.append(ext['id'])

        if missing_explanations:
            print_color("\n以下の拡張機能は vscode-extensions-explain.json に説明がありません：", Colors.YELLOW)
            for ext_id in missing_explanations:
                print_color(f"  - {ext_id}", Colors.YELLOW)
            print()
            print_color("vscode-extensions-explain.json への説明追記をお願いします。", Colors.CYAN)
        else:
            print_color("\nすべての拡張機能に説明が登録されています。", Colors.GREEN)

    except Exception as e:
        print_color(f"警告: vscode-extensions-explain.json の読み込みに失敗しました: {e}", Colors.YELLOW)


def main(alias: Optional[str] = None, include_keybindings: bool = False, include_snippets: bool = False):
    """メイン処理"""
    try:
        script_dir = Path(__file__).parent

        # 1) プロファイルルートの初期化
        profiles_root = get_profiles_absolute_path()

        # 2) プロファイル名の決定（選択 or 新規）
        if not alias:
            alias = select_or_create_profile(profiles_root)

        # 3) プロファイルディレクトリの準備
        profile_dir = profiles_root / alias
        profile_dir.mkdir(parents=True, exist_ok=True)
        print_color(f"保存先プロファイル: {alias} ({profile_dir})", Colors.GREEN)

        # 4) VS Code ユーザー設定ディレクトリの取得
        user_dir = get_user_settings_dir()

        # 5) settings.json のコピー
        src_settings = user_dir / "settings.json"
        dst_settings = profile_dir / "settings.json"
        if src_settings.exists():
            copy_file_if_exists(src_settings, dst_settings, "settings.json")
        else:
            print_color("警告: ユーザー settings.json が見つかりませんでした。", Colors.YELLOW)

        # 6) keybindings.json のコピー（任意）
        if include_keybindings:
            src_key = user_dir / "keybindings.json"
            dst_key = profile_dir / "keybindings.json"
            copy_file_if_exists(src_key, dst_key, "keybindings.json")

        # 7) snippets のコピー（任意）
        if include_snippets:
            src_snippets = user_dir / "snippets"
            dst_snippets = profile_dir / "snippets"
            copy_directory_if_exists(src_snippets, dst_snippets, "snippets")

        # 8) 拡張一覧の取得と JSON 生成
        installed_extensions = export_extensions(profile_dir)

        # 9) 拡張の説明ファイルとの照合
        if installed_extensions:
            check_extension_explanations(installed_extensions, script_dir)

        # 10) 完了メッセージ
        print_color(f"\n完了: プロファイル '{alias}' に設定と拡張を保存しました。", Colors.CYAN)

    except Exception as e:
        print_color(f"\nエラーが発生しました: {e}", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="VS Codeの設定と拡張機能をプロファイルにエクスポート"
    )
    parser.add_argument(
        '--alias',
        type=str,
        help='プロファイル名（未指定の場合は選択UI）'
    )
    parser.add_argument(
        '--include-keybindings',
        action='store_true',
        help='keybindings.json も保存する'
    )
    parser.add_argument(
        '--include-snippets',
        action='store_true',
        help='snippets フォルダも保存する'
    )

    args = parser.parse_args()

    main(
        alias=args.alias,
        include_keybindings=args.include_keybindings,
        include_snippets=args.include_snippets
    )
