import json
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "bookmarks-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_vault_path() -> Path | None:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            path = Path(data["vault_path"])
            if path.exists():
                return path
        except (KeyError, json.JSONDecodeError):
            pass
    return None


def set_vault_path(vault_path: Path) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"vault_path": str(vault_path)}))


def prompt_vault_path() -> Path:
    print("Bookmarks CLI — First time setup")
    print("Enter the path to your Obsidian vault (must contain Unread/ and Archive/ folders):")
    while True:
        raw = input("> ").strip()
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(f"  Path does not exist: {path}")
            continue
        if not (path / "Unread").exists() or not (path / "Archive").exists():
            print(f"  Vault must contain both Unread/ and Archive/ folders.")
            continue
        set_vault_path(path)
        print(f"  Saved. Run `bookmarks` again to start.\n")
        return path
