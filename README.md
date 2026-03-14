# bookmarks-cli

A terminal reader for your Obsidian bookmarks vault. Browse, read, archive, tag, and save articles from the command line.

(bookmark-cli-demo.png)

## Requirements

- Python 3.11+
- An Obsidian vault with `Unread/` and `Archive/` folders (saved via Obsidian Clipper)

## Install

```bash
git clone https://github.com/scottsteinhardt/bookmark-cli.git
cd bookmarks-cli
pip install -e .
```

Then point it at your vault:

```bash
bookmarks --set-vault ~/Documents/Bookmarks
```

Run it:

```bash
bookmarks
```

## Key Bindings

| Key | Action |
|-----|--------|
| `/` | Search (filters both lists live as you type) |
| `Enter` | Read article inline (below lists) |
| `v` | Read article fullscreen |
| `Tab` | Switch between Unread / Archive / Article |
| `Esc` | Close article |
| `s` | Save article from URL |
| `R` | Toggle read (move between Unread ↔ Archive) |
| `a` | Archive |
| `u` | Unarchive |
| `t` | Tag |
| `o` | Open source URL in browser |
| `d` `d` | Delete (press twice to confirm) |
| `w` | Cycle reading width (50% / 65% / 80% / 100%) |
| `f` | Display settings (width, line spacing, font info) |
| `r` | Refresh lists |
| `q` | Quit |

## Vault structure

The vault must have exactly these two folders:

```
YourVault/
├── Unread/
│   └── *.md
└── Archive/
    └── *.md
```

Files saved by Obsidian Clipper work out of the box. Anything tagged `priority` gets a ★ in the list.

## Changing font or size

Font family and size are controlled by your terminal emulator, not this app.

- **iTerm2 / Terminal.app** — `Cmd+,` → Profiles → Text → font
- **Kitty** — edit `kitty.conf` → `font_size`
- **Alacritty** — edit `alacritty.toml` → `font.size`
- **Quick zoom** — `Cmd+=` / `Cmd+-` in most terminals
