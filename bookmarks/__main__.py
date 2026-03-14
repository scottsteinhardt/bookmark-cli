import argparse
import sys
from pathlib import Path

from .config import get_vault_path, prompt_vault_path, set_vault_path
from .app import BookmarksApp


def main() -> None:
    parser = argparse.ArgumentParser(description="Obsidian bookmarks reader")
    parser.add_argument("--vault", metavar="PATH", help="Path to Obsidian vault")
    parser.add_argument("--set-vault", metavar="PATH", help="Set and save vault path")
    args = parser.parse_args()

    if args.set_vault:
        path = Path(args.set_vault).expanduser().resolve()
        if not path.exists():
            print(f"Error: {path} does not exist")
            sys.exit(1)
        set_vault_path(path)
        print(f"Vault set to: {path}")
        return

    if args.vault:
        vault_path = Path(args.vault).expanduser().resolve()
    else:
        vault_path = get_vault_path()
        if vault_path is None:
            vault_path = prompt_vault_path()

    BookmarksApp(vault_path).run()


if __name__ == "__main__":
    main()
