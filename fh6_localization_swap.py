from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

FH6_DIRECTORY: str | None = "D:\\XboxGames\\Forza Horizon 6\\Content\\"
FH6_LANGUAGE: str | None = "EN"
LANGUAGE_PACK_MISSING_MESSAGE = f"Run Forza Horizon 6 and install the {FH6_LANGUAGE} language pack."
JP_PACK_MISSING_MESSAGE = "Run Forza Horizon 6 and install Japanese language pack."

@dataclass
class RunSummary:
    backups_created: int = 0
    backups_refreshed: int = 0
    files_replaced: int = 0
    files_restored: int = 0
    files_skipped: int = 0


def print_step(message: str) -> None:
    print(f"[INFO] {message}")


def print_warning(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str, exit_code: int = 1) -> int:
    print(f"[ERROR] {message}")
    return exit_code


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def require_file(path: Path, message: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back up and swap Forza Horizon 6 Japanese localization files with English copies."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Optional game root path. Defaults to FH6_DIRECTORY if valid, otherwise script directory.",
    )
    operation_group = parser.add_mutually_exclusive_group()
    operation_group.add_argument(
        "--swap",
        action="store_true",
        help="Back up and swap Japanese localization files with English copies.",
    )
    operation_group.add_argument(
        "--restore",
        action="store_true",
        help="Restore live files from the backup folders.",
    )
    return parser.parse_args()


def resolve_root(root_argument: str | None) -> Path:
    if root_argument:
        return Path(root_argument).expanduser().resolve()

    if FH6_DIRECTORY:
        configured_root = Path(FH6_DIRECTORY).expanduser().resolve()
        if (configured_root / "forzahorizon6.exe").is_file():
            return configured_root
        print_warning(
            f"FH6_DIRECTORY does not contain forzahorizon6.exe: {configured_root}. "
            "Falling back to script directory."
        )

    return Path(__file__).resolve().parent


def get_stringtable_paths(root: Path) -> tuple[Path, Path, Path]:
    stringtables_dir = root / "media" / "stripped" / "stringtables"
    return stringtables_dir, stringtables_dir / f"{FH6_LANGUAGE}.zip", stringtables_dir / "JP.zip"


def get_radioinfo_paths(root: Path) -> tuple[Path, Path, Path]:
    audio_dir = root / "media" / "audio"
    return audio_dir, audio_dir / f"RadioInfo_{FH6_LANGUAGE}.xml", audio_dir / "RadioInfo_JP.xml"


def get_audio_paths(root: Path) -> tuple[Path, Path]:
    audio_dir = root / "media" / "audio" / "fmodbanks"
    return audio_dir, audio_dir / "backup"


def backup_stringtables(lang_zip: Path, jp_zip: Path, summary: RunSummary) -> None:
    backup_dir = lang_zip.parent / "backup"
    backup_lang = backup_dir / lang_zip.name
    backup_jp = backup_dir / jp_zip.name

    print_step("Preparing stringtable backup.")
    refresh_backup = False

    if not backup_dir.exists():
        print_step(f"Creating backup folder: {backup_dir}")
        backup_dir.mkdir(parents=True, exist_ok=True)
        refresh_backup = True
    elif not backup_lang.is_file() or not backup_jp.is_file():
        print_warning("Stringtable backup is incomplete. Refreshing backup files.")
        refresh_backup = True
    else:
        live_checksum = sha256sum(lang_zip)
        backup_checksum = sha256sum(backup_lang)
        if live_checksum != backup_checksum:
            print_warning(f"Stringtable {FH6_LANGUAGE}.zip changed since the last backup. Refreshing backup files.")
            refresh_backup = True
        else:
            print_step("Stringtable backup is current.")

    if refresh_backup:
        copy_file(lang_zip, backup_lang)
        copy_file(jp_zip, backup_jp)
        summary.backups_created += 2
        summary.backups_refreshed += 1
        print_step("Stringtable backup ready.")


def replace_stringtable_jp(lang_zip: Path, jp_zip: Path, summary: RunSummary) -> None:
    print_step(f"Replacing {jp_zip.name} with a copy of {lang_zip.name}.")
    copy_file(lang_zip, jp_zip)
    summary.files_replaced += 1
    print_step("Stringtable replacement complete.")


def backup_radioinfo(lang_xml: Path, jp_xml: Path, summary: RunSummary) -> None:
    backup_dir = lang_xml.parent / "backup"
    backup_lang = backup_dir / lang_xml.name
    backup_jp = backup_dir / jp_xml.name

    print_step("Preparing RadioInfo backup.")
    refresh_backup = False

    if not backup_dir.exists():
        print_step(f"Creating backup folder: {backup_dir}")
        backup_dir.mkdir(parents=True, exist_ok=True)
        refresh_backup = True
    elif not backup_lang.is_file() or not backup_jp.is_file():
        print_warning("RadioInfo backup is incomplete. Refreshing backup files.")
        refresh_backup = True
    else:
        live_checksum = sha256sum(lang_xml)
        backup_checksum = sha256sum(backup_lang)
        if live_checksum != backup_checksum:
            print_warning(f"RadioInfo_{FH6_LANGUAGE}.xml changed since the last backup. Refreshing backup files.")
            refresh_backup = True
        else:
            print_step("RadioInfo backup is current.")

    if refresh_backup:
        copy_file(lang_xml, backup_lang)
        copy_file(jp_xml, backup_jp)
        summary.backups_created += 2
        summary.backups_refreshed += 1
        print_step("RadioInfo backup ready.")


def replace_radioinfo_jp(lang_xml: Path, jp_xml: Path, summary: RunSummary) -> None:
    print_step(f"Replacing {jp_xml.name} with a copy of {lang_xml.name}.")
    copy_file(lang_xml, jp_xml)
    summary.files_replaced += 1
    print_step("RadioInfo replacement complete.")


def discover_stinger_files(audio_dir: Path) -> tuple[list[Path], list[Path]]:
    lang_files = sorted(
        path
        for path in audio_dir.iterdir()
        if path.is_file() and f"_Stingers_{FH6_LANGUAGE}" in path.name
    )
    jp_files = sorted(
        path
        for path in audio_dir.iterdir()
        if path.is_file() and "_Stingers_JP" in path.name
    )
    return lang_files, jp_files


def discover_dj_files(audio_dir: Path) -> tuple[list[Path], list[Path]]:
    dj_pattern = re.compile(rf"VO_DJ_[0-9]{2}_({FH6_LANGUAGE}|JP)")
    lang_files = sorted(
        path
        for path in audio_dir.iterdir()
        if path.is_file() and dj_pattern.search(path.name) and f"_{FH6_LANGUAGE}" in path.name
    )
    jp_files = sorted(
        path
        for path in audio_dir.iterdir()
        if path.is_file() and dj_pattern.search(path.name) and "_JP" in path.name
    )
    return lang_files, jp_files


def refresh_stinger_backup_needed(lang_files: list[Path], jp_files: list[Path], backup_dir: Path) -> bool:
    if not backup_dir.exists():
        return True

    if not lang_files and not jp_files:
        return False

    for lang_file in lang_files:
        backup_file = backup_dir / lang_file.name
        if not backup_file.is_file():
            print_warning(f"Missing stinger backup file: {backup_file.name}")
            return True
        if sha256sum(lang_file) != sha256sum(backup_file):
            print_warning(f"Detected changed stinger file: {lang_file.name}")
            return True

    for jp_file in jp_files:
        backup_file = backup_dir / jp_file.name
        if not backup_file.is_file():
            print_warning(f"Missing stinger backup file: {backup_file.name}")
            return True

    return False


def clear_stinger_backup_files(backup_dir: Path) -> None:
    for backup_file in backup_dir.iterdir():
        if backup_file.is_file() and (f"_Stingers_{FH6_LANGUAGE}" in backup_file.name or "_Stingers_JP" in backup_file.name):
            backup_file.unlink()


def refresh_dj_backup_needed(lang_files: list[Path], jp_files: list[Path], backup_dir: Path) -> bool:
    if not backup_dir.exists():
        return True

    if not lang_files and not jp_files:
        return False

    for lang_file in lang_files:
        backup_file = backup_dir / lang_file.name
        if not backup_file.is_file():
            print_warning(f"Missing DJ backup file: {backup_file.name}")
            return True
        if sha256sum(lang_file) != sha256sum(backup_file):
            print_warning(f"Detected changed DJ {FH6_LANGUAGE} file: {lang_file.name}")
            return True

    for jp_file in jp_files:
        backup_file = backup_dir / jp_file.name
        if not backup_file.is_file():
            print_warning(f"Missing DJ backup file: {backup_file.name}")
            return True

    return False


def clear_dj_backup_files(backup_dir: Path) -> None:
    dj_pattern = re.compile(rf"VO_DJ_[0-9]{2}_({FH6_LANGUAGE}|JP)")
    for backup_file in backup_dir.iterdir():
        if backup_file.is_file() and dj_pattern.search(backup_file.name):
            backup_file.unlink()


def backup_stingers(audio_dir: Path, summary: RunSummary) -> tuple[list[Path], list[Path]]:
    lang_files, jp_files = discover_stinger_files(audio_dir)
    backup_dir = audio_dir / "backup"

    print_step("Preparing stinger backup.")
    if not lang_files and not jp_files:
        print_warning(f"No _Stingers_{FH6_LANGUAGE} or _Stingers_JP files were found in media\\audio\\fmodbanks.")
        return lang_files, jp_files

    refresh_backup = refresh_stinger_backup_needed(lang_files, jp_files, backup_dir)

    if refresh_backup:
        if not backup_dir.exists():
            print_step(f"Creating backup folder: {backup_dir}")
            backup_dir.mkdir(parents=True, exist_ok=True)
        else:
            print_step("Clearing existing stinger backup files before refresh.")
            clear_stinger_backup_files(backup_dir)
        print_step("Refreshing stinger backup files.")
        for source in lang_files + jp_files:
            copy_file(source, backup_dir / source.name)
            summary.backups_created += 1
        summary.backups_refreshed += 1
        print_step("Stinger backup ready.")
    else:
        print_step("Stinger backup is current.")

    return lang_files, jp_files


def backup_djs(audio_dir: Path, summary: RunSummary) -> tuple[list[Path], list[Path]]:
    lang_files, jp_files = discover_dj_files(audio_dir)
    backup_dir = audio_dir / "backup"

    print_step("Preparing DJ backup.")
    if not lang_files and not jp_files:
        print_warning(f"No VO_DJ_[0-9][0-9]_{FH6_LANGUAGE} or VO_DJ_[0-9][0-9]_JP files were found in media\\audio\\fmodbanks.")
        return lang_files, jp_files

    refresh_backup = refresh_dj_backup_needed(lang_files, jp_files, backup_dir)

    if refresh_backup:
        if not backup_dir.exists():
            print_step(f"Creating backup folder: {backup_dir}")
            backup_dir.mkdir(parents=True, exist_ok=True)
        else:
            print_step("Clearing existing DJ backup files before refresh.")
            clear_dj_backup_files(backup_dir)
        print_step("Refreshing DJ backup files.")
        for source in lang_files + jp_files:
            copy_file(source, backup_dir / source.name)
            summary.backups_created += 1
        summary.backups_refreshed += 1
        print_step("DJ backup ready.")
    else:
        print_step("DJ backup is current.")

    return lang_files, jp_files


def replace_stingers(audio_dir: Path, lang_files: list[Path], summary: RunSummary) -> None:
    if not lang_files:
        return

    print_step("Replacing Japanese stinger files with English copies.")
    for lang_file in lang_files:
        jp_name = lang_file.name.replace(f"_Stingers_{FH6_LANGUAGE}", "_Stingers_JP")
        jp_file = audio_dir / jp_name
        if not jp_file.is_file():
            summary.files_skipped += 1
            print_warning(f"Skipping {lang_file.name}: matching Japanese file was not found.")
            continue

        copy_file(lang_file, jp_file)
        summary.files_replaced += 1
        print_step(f"Replaced {jp_file.name} using {lang_file.name}.")


def replace_djs(audio_dir: Path, lang_files: list[Path], summary: RunSummary) -> None:
    if not lang_files:
        return

    print_step("Replacing Japanese DJ files with English copies.")
    for lang_file in lang_files:
        jp_name = re.sub(rf"VO_DJ_([0-9]{{2}})_{FH6_LANGUAGE}", r"VO_DJ_\1_JP", lang_file.name, count=1)
        jp_file = audio_dir / jp_name
        if not jp_file.is_file():
            summary.files_skipped += 1
            print_warning(f"Skipping {lang_file.name}: matching Japanese file was not found.")
            continue

        copy_file(lang_file, jp_file)
        summary.files_replaced += 1
        print_step(f"Replaced {jp_file.name} using {lang_file.name}.")


def restore_stringtables(stringtables_dir: Path, summary: RunSummary) -> None:
    backup_dir = stringtables_dir / "backup"
    backup_lang = backup_dir / f"{FH6_LANGUAGE}.zip"
    backup_jp = backup_dir / "JP.zip"
    live_lang = stringtables_dir / f"{FH6_LANGUAGE}.zip"
    live_jp = stringtables_dir / "JP.zip"

    print_step("Restoring stringtable files from backup.")
    require_file(backup_lang, f"Missing backup file: {backup_lang}")
    require_file(backup_jp, f"Missing backup file: {backup_jp}")
    copy_file(backup_lang, live_lang)
    copy_file(backup_jp, live_jp)
    summary.files_restored += 2
    print_step("Stringtable restore complete.")


def restore_radioinfo(audio_dir: Path, summary: RunSummary) -> None:
    backup_dir = audio_dir / "backup"
    backup_lang = backup_dir / f"RadioInfo_{FH6_LANGUAGE}.xml"
    backup_jp = backup_dir / "RadioInfo_JP.xml"
    live_lang = audio_dir / f"RadioInfo_{FH6_LANGUAGE}.xml"
    live_jp = audio_dir / "RadioInfo_JP.xml"

    print_step("Restoring RadioInfo files from backup.")
    require_file(backup_lang, f"Missing backup file: {backup_lang}")
    require_file(backup_jp, f"Missing backup file: {backup_jp}")
    copy_file(backup_lang, live_lang)
    copy_file(backup_jp, live_jp)
    summary.files_restored += 2
    print_step("RadioInfo restore complete.")


def restore_stingers(audio_dir: Path, summary: RunSummary) -> None:
    backup_dir = audio_dir / "backup"
    print_step("Restoring stinger files from backup.")
    if not backup_dir.is_dir():
        raise FileNotFoundError(f"Missing backup folder: {backup_dir}")

    backup_files = sorted(
        path
        for path in backup_dir.iterdir()
        if path.is_file() and (f"_Stingers_{FH6_LANGUAGE}" in path.name or "_Stingers_JP" in path.name)
    )
    if not backup_files:
        raise FileNotFoundError(f"No backed-up stinger files found in: {backup_dir}")

    for backup_file in backup_files:
        copy_file(backup_file, audio_dir / backup_file.name)
        summary.files_restored += 1
        print_step(f"Restored {backup_file.name}.")


def print_summary(summary: RunSummary, restore_mode: bool) -> None:
    print_step("Operation summary:")
    if restore_mode:
        print(f"  Restored files: {summary.files_restored}")
        print(f"  Skipped files: {summary.files_skipped}")
        return

    print(f"  Backup files copied: {summary.backups_created}")
    print(f"  Backup refresh operations: {summary.backups_refreshed}")
    print(f"  Files replaced: {summary.files_replaced}")
    print(f"  Skipped files: {summary.files_skipped}")


def run_replace(root: Path) -> int:
    summary = RunSummary()

    _, lang_zip, jp_zip = get_stringtable_paths(root)
    audio_dir, lang_xml, jp_xml = get_radioinfo_paths(root)

    print_step(f"Using game root: {root}")
    print_step(f"Using base language: {FH6_LANGUAGE}")
    print_step("Validating required files.")
    require_file(lang_zip, f"Missing required file: {lang_zip}")
    require_file(lang_xml, f"Missing required file: {lang_xml}")
    if not lang_zip.is_file():
        return fail(LANGUAGE_PACK_MISSING_MESSAGE)  
    if not jp_zip.is_file():
        return fail(JP_PACK_MISSING_MESSAGE)
    require_file(jp_xml, f"Missing required file: {jp_xml}")

    backup_stringtables(lang_zip, jp_zip, summary)
    replace_stringtable_jp(lang_zip, jp_zip, summary)
    backup_radioinfo(lang_xml, jp_xml, summary)
    replace_radioinfo_jp(lang_xml, jp_xml, summary)
    print_summary(summary, restore_mode=False)
    return 0


def run_swap_stringtables(root: Path) -> int:
    summary = RunSummary()
    _, lang_zip, jp_zip = get_stringtable_paths(root)

    print_step(f"Using game root: {root}")
    print_step(f"Using base language: {FH6_LANGUAGE}")
    print_step("Validating required stringtable files.")
    require_file(lang_zip, f"Missing required file: {lang_zip}")
    if not lang_zip.is_file():
        return fail(LANGUAGE_PACK_MISSING_MESSAGE)  
    if not jp_zip.is_file():
        return fail(JP_PACK_MISSING_MESSAGE)

    backup_stringtables(lang_zip, jp_zip, summary)
    replace_stringtable_jp(lang_zip, jp_zip, summary)
    print_summary(summary, restore_mode=False)
    return 0


def run_swap_radioinfo(root: Path) -> int:
    summary = RunSummary()
    _, lang_xml, jp_xml = get_radioinfo_paths(root)

    print_step(f"Using game root: {root}")
    print_step(f"Using base language: {FH6_LANGUAGE}")
    require_file(lang_xml, f"Missing required file: {lang_xml}")
    require_file(jp_xml, f"Missing required file: {jp_xml}")

    backup_radioinfo(lang_xml, jp_xml, summary)
    replace_radioinfo_jp(lang_xml, jp_xml, summary)
    print_summary(summary, restore_mode=False)
    return 0


def run_restore(root: Path) -> int:
    summary = RunSummary()
    stringtables_dir, _, _ = get_stringtable_paths(root)
    audio_dir, _, _ = get_radioinfo_paths(root)

    print_step(f"Using game root: {root}")
    print_step(f"Using base language: {FH6_LANGUAGE}")
    restore_stringtables(stringtables_dir, summary)
    restore_radioinfo(audio_dir, summary)
    print_summary(summary, restore_mode=True)
    return 0


def select_operation() -> str:
    menu_options: list[tuple[str, str]] = [
        ("swap_stringtables", "Swap StringTables"),
        ("swap_radioinfo", "Swap RadioInfo"),
        ("swap", "Swap everything"),
        ("restore", "Restore from backup"),
        ("exit", "Exit"),
    ]

    print_step("Choose an operation:")
    for index, (_, label) in enumerate(menu_options, start=1):
        print(f"  {index}. {label}")

    while True:
        choice = input("Enter choice number: ").strip()
        if not choice.isdigit():
            print_warning("Please enter a valid number.")
            continue

        selected_index = int(choice)
        if 1 <= selected_index <= len(menu_options):
            return menu_options[selected_index - 1][0]

        print_warning("Selection out of range. Try again.")


def main() -> int:
    args = parse_args()
    root = resolve_root(args.path)
    operation_handlers: dict[str, Callable[[Path], int]] = {
        "swap_stringtables": run_swap_stringtables,
        "swap_radioinfo": run_swap_radioinfo,
        "swap": run_replace,
        "restore": run_restore,
    }

    try:
        if args.swap:
            operation = "swap"
            return operation_handlers[operation](root)
        elif args.restore:
            operation = "restore"
            return operation_handlers[operation](root)
        elif sys.stdin.isatty():
            while True:
                operation = select_operation()
                if operation == "exit":
                    print_step("Exiting.")
                    return 0

                try:
                    operation_handlers[operation](root)
                except FileNotFoundError as error:
                    fail(str(error))
                except OSError as error:
                    fail(f"File operation failed: {error}")
        else:
            print_step("No operation was specified. Defaulting to swap mode.")
            operation = "swap"
            return operation_handlers[operation](root)
    except FileNotFoundError as error:
        return fail(str(error))
    except OSError as error:
        return fail(f"File operation failed: {error}")


if __name__ == "__main__":
    sys.exit(main())