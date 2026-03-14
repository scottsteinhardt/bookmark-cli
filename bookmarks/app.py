from pathlib import Path
import subprocess

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Header,
    Input,
    Label,
    Markdown,
    Static,
)

from .clipper import fetch_article
from .vault import Story, Vault

STAR = "★"
READER_WIDTHS = ["50%", "65%", "80%", "100%"]


# ─── Inline tag input (Escape cancels) ───────────────────────────────────────


class TagInput(Input):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def action_cancel(self) -> None:
        self.app.hide_tag_bar()


class SearchInput(Input):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def action_cancel(self) -> None:
        self.app.hide_search_bar()


# ─── Tag modal (for when reader is open) ─────────────────────────────────────


class TagModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_cancel", "Cancel")]

    CSS = """
    TagModal { align: center middle; }
    #tag-dialog {
        background: $surface; border: solid $accent;
        padding: 1 2; width: 70; height: auto;
    }
    #tag-title { text-style: bold; margin-bottom: 1; }
    #tag-buttons { margin-top: 1; align: right middle; height: auto; }
    #tag-buttons Button { margin-left: 1; }
    .hint { color: $text-muted; text-style: italic; }
    """

    def __init__(self, story: Story, vault: Vault) -> None:
        super().__init__()
        self.story = story
        self.vault = vault

    def compose(self) -> ComposeResult:
        from textual.containers import Center
        with Center():
            with Vertical(id="tag-dialog"):
                yield Label(f"Tags — {self.story.display_title}", id="tag-title")
                yield Input(
                    value=", ".join(self.story.tags),
                    placeholder="clippings, music, priority",
                    id="tag-input",
                )
                yield Label("Comma-separated. Enter to save.", classes="hint")
                with Horizontal(id="tag-buttons"):
                    yield Button("Save", variant="primary", id="save-btn")
                    yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#tag-input", Input).focus()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._save() if event.button.id == "save-btn" else self.dismiss(False)

    def action_dismiss_cancel(self) -> None:
        self.dismiss(False)

    def _save(self) -> None:
        raw = self.query_one("#tag-input", Input).value
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        self.vault.save_tags(self.story, tags)
        self.dismiss(True)


# ─── Save (clip) screen ───────────────────────────────────────────────────────


class SaveScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_cancel", "Cancel")]

    CSS = """
    SaveScreen { align: center middle; }
    #save-dialog {
        background: $surface; border: solid $accent;
        padding: 1 2; width: 70; height: auto;
    }
    #save-title { text-style: bold; margin-bottom: 1; }
    #save-status { margin-top: 1; height: 1; }
    #save-buttons { margin-top: 1; align: right middle; height: auto; }
    #save-buttons Button { margin-left: 1; }
    """

    def __init__(self, vault: Vault) -> None:
        super().__init__()
        self.vault = vault

    def compose(self) -> ComposeResult:
        from textual.containers import Center
        with Center():
            with Vertical(id="save-dialog"):
                yield Label("Save Article", id="save-title")
                yield Input(placeholder="https://...", id="url-input")
                yield Static("", id="save-status")
                with Horizontal(id="save-buttons"):
                    yield Button("Fetch & Save", variant="primary", id="fetch-btn")
                    yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self._start_fetch()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._start_fetch() if event.button.id == "fetch-btn" else self.dismiss(None)

    def action_dismiss_cancel(self) -> None:
        self.dismiss(None)

    def _start_fetch(self) -> None:
        url = self.query_one("#url-input", Input).value.strip()
        if not url:
            return
        self.query_one("#url-input", Input).disabled = True
        self.query_one("#fetch-btn", Button).disabled = True
        self._fetch(url)

    @work(thread=True)
    def _fetch(self, url: str) -> None:
        status = self.query_one("#save-status", Static)
        self.app.call_from_thread(status.update, "Fetching article…")
        try:
            article = fetch_article(url)
            self.app.call_from_thread(status.update, f"Saving: {article.title[:50]}")
            story = self.vault.save_new(
                title=article.title, source=article.url,
                content=article.content, author=article.author,
                description=article.description, published=article.published,
            )
            self.app.call_from_thread(self.dismiss, story)
        except Exception as exc:
            def show_error() -> None:
                status.update(f"Error: {exc}")
                self.query_one("#url-input", Input).disabled = False
                self.query_one("#fetch-btn", Button).disabled = False
            self.app.call_from_thread(show_error)


# ─── Display settings modal ───────────────────────────────────────────────────

SPACING_OPTIONS = [
    ("Compact",  (0, 1)),
    ("Normal",   (0, 2)),
    ("Spacious", (1, 4)),
]


class DisplayScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Close")]

    CSS = """
    DisplayScreen { align: center middle; }
    #display-dialog {
        background: $surface; border: solid $accent;
        padding: 1 2; width: 72; height: auto;
    }
    #display-title { text-style: bold; margin-bottom: 1; }
    .ds-section { text-style: bold; color: $accent; margin-top: 1; height: 1; }
    .ds-row { layout: horizontal; height: 3; margin-top: 0; }
    .ds-row Button { margin-right: 1; }
    #terminal-info {
        margin-top: 1; color: $text-muted; height: auto;
    }
    #display-close { margin-top: 1; align: right middle; height: auto; }
    """

    def __init__(self, width_idx: int, spacing_idx: int) -> None:
        super().__init__()
        self._width_idx = width_idx
        self._spacing_idx = spacing_idx

    def compose(self) -> ComposeResult:
        with Vertical(id="display-dialog"):
            yield Label("Display Settings", id="display-title")

            yield Label("Reading Width", classes="ds-section")
            with Horizontal(classes="ds-row"):
                for i, w in enumerate(READER_WIDTHS):
                    yield Button(
                        w, id=f"width-{i}",
                        variant="primary" if i == self._width_idx else "default",
                    )

            yield Label("Line Spacing", classes="ds-section")
            with Horizontal(classes="ds-row"):
                for i, (name, _) in enumerate(SPACING_OPTIONS):
                    yield Button(
                        name, id=f"spacing-{i}",
                        variant="primary" if i == self._spacing_idx else "default",
                    )

            yield Static(
                "Font & size — set in your terminal emulator:\n"
                "  iTerm2       Cmd+,  →  Profiles → Text → font\n"
                "  Terminal.app Cmd+,  →  Profiles → font\n"
                "  Kitty        kitty.conf  →  font_size\n"
                "  Alacritty    alacritty.toml  →  font.size\n"
                "  Quick zoom   Cmd+= / Cmd+−  (most terminals)",
                id="terminal-info",
            )

            with Horizontal(id="display-close"):
                yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "close-btn":
            self.dismiss((self._width_idx, self._spacing_idx))
            return
        if bid.startswith("width-"):
            new_idx = int(bid.split("-")[1])
            if new_idx != self._width_idx:
                self._width_idx = new_idx
                self._refresh_buttons("width", len(READER_WIDTHS))
        elif bid.startswith("spacing-"):
            new_idx = int(bid.split("-")[1])
            if new_idx != self._spacing_idx:
                self._spacing_idx = new_idx
                self._refresh_buttons("spacing", len(SPACING_OPTIONS))

    def _refresh_buttons(self, prefix: str, count: int) -> None:
        current = self._width_idx if prefix == "width" else self._spacing_idx
        for i in range(count):
            btn = self.query_one(f"#{prefix}-{i}", Button)
            btn.variant = "primary" if i == current else "default"

    def action_dismiss(self) -> None:
        self.dismiss((self._width_idx, self._spacing_idx))


# ─── Full-screen reader modal ─────────────────────────────────────────────────


class ReaderScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("o", "open_browser", "Open URL"),
        Binding("w", "cycle_width", "Width"),
    ]

    CSS = """
    ReaderScreen { align: center top; background: $background 80%; }
    #full-reader {
        width: 80%; height: 100%;
        background: $surface; border: solid $primary;
    }
    #full-reader-bar {
        height: 3; background: $boost; padding: 0 1;
        border-bottom: solid $primary;
    }
    #full-reader-title { text-style: bold; color: $accent; height: 1; overflow: hidden hidden; }
    #full-reader-meta { color: $text-muted; height: 1; overflow: hidden hidden; }
    #full-reader-hints { color: $text-disabled; height: 1; }
    #full-reader-scroll { height: 1fr; overflow-y: auto; }
    #full-reader-content { height: auto; width: 80%; padding: 0 2; }
    """

    def __init__(self, story: Story, vault: Vault) -> None:
        super().__init__()
        self.story = story
        self.vault = vault
        self._width_idx = 2  # default 80%
        self._widths = ["50%", "65%", "80%", "100%"]

    def _meta(self) -> str:
        parts = []
        if self.story.domain:
            parts.append(self.story.domain)
        if self.story.authors:
            parts.append(f"by {', '.join(self.story.authors)}")
        if self.story.published and str(self.story.published) not in ("", "None"):
            parts.append(str(self.story.published))
        if self.story.tags:
            parts.append("  ".join(f"#{t}" for t in self.story.tags))
        return "  ·  ".join(parts)

    def compose(self) -> ComposeResult:
        with Vertical(id="full-reader"):
            with Vertical(id="full-reader-bar"):
                yield Label(self.story.display_title, id="full-reader-title")
                yield Label(self._meta(), id="full-reader-meta")
                yield Label(r"\[Esc] close  \[o] browser  \[w] width", id="full-reader-hints")
            with VerticalScroll(id="full-reader-scroll"):
                yield Markdown("Loading…", id="full-reader-content")

    def on_mount(self) -> None:
        self._load()

    @work(thread=True)
    def _load(self) -> None:
        content = self.vault.read_content(self.story)
        self.app.call_from_thread(
            self.query_one("#full-reader-content", Markdown).update, content
        )

    def action_open_browser(self) -> None:
        if self.story.source:
            subprocess.run(["open", self.story.source])
            self.app.notify("Opening in browser…")

    def action_cycle_width(self) -> None:
        self._width_idx = (self._width_idx + 1) % len(self._widths)
        w = self._widths[self._width_idx]
        self.query_one("#full-reader-content", Markdown).styles.width = w
        self.app.notify(f"Width: {w}")


# ─── Main app ─────────────────────────────────────────────────────────────────


class BookmarksApp(App):
    TITLE = "Obsidian Bookmarks"
    CSS = """
    Screen { layout: vertical; }

    /* ── List panes ── */
    #main-wrapper { layout: vertical; height: 1fr; }

    #lists { layout: horizontal; height: 1fr; }

    .pane { width: 1fr; layout: vertical; border: solid $primary; }
    .pane:focus-within { border: solid $accent; }
    .pane-title {
        background: $primary; color: $text;
        padding: 0 1; text-align: center; height: 1;
    }

    DataTable { height: 1fr; }

    /* ── Inline reader pane (below lists) ── */
    #reader-pane {
        layout: vertical;
        height: 60%;
        display: none;
    }

    #reader-bar {
        layout: vertical;
        height: 3;
        background: $boost;
        padding: 0 1;
        border-top: tall $primary;
        border-bottom: solid $primary;
    }

    #reader-title {
        text-style: bold;
        color: $accent;
        height: 1;
        overflow: hidden hidden;
    }

    #reader-meta {
        color: $text-muted;
        height: 1;
        overflow: hidden hidden;
    }

    #reader-hints {
        color: $text-disabled;
        height: 1;
    }

    #reader-scroll {
        height: 1fr;
        overflow-y: auto;
    }

    #reader-content {
        height: auto;
        width: 65%;
        padding: 0 2;
    }

    /* ── Keys bar ── */
    #keys-bar {
        height: 1;
        background: $boost;
        color: $text-muted;
        padding: 0 1;
    }

    /* ── Search bar ── */
    #search-bar {
        height: 3;
        background: $boost;
        border-top: solid $success;
        padding: 0 1;
        layout: horizontal;
        align: left middle;
        display: none;
    }
    #search-bar-label { width: auto; padding: 0 1; color: $success; height: 3; content-align: left middle; }
    #search-bar-input { width: 1fr; border: solid $success; }

    /* ── Inline tag bar ── */
    #tag-bar {
        height: 1;
        background: $boost;
        border-top: solid $accent;
        padding: 0 1;
        layout: horizontal;
        display: none;
    }
    #tag-bar-label { width: auto; padding: 0 1; color: $accent; }
    #tag-bar-input { width: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("/", "search", "Search", show=False, priority=True),
        Binding("s", "save_article", "Save URL", show=False),
        Binding("tab", "switch_pane", "Switch pane", show=False),
        Binding("escape", "close_reader", "Close", show=False),
        Binding("R", "toggle_read", "Toggle read", show=False),
        Binding("a", "archive_story", "Archive", show=False),
        Binding("u", "unarchive_story", "Unarchive", show=False),
        Binding("t", "tag_story", "Tag", show=False),
        Binding("o", "open_browser", "Open URL", show=False),
        Binding("v", "open_fullscreen", "Fullscreen", show=False),
        Binding("d", "delete_story", "Delete", show=False),
        Binding("w", "cycle_width", "Width", show=False),
        Binding("f", "font_info", "Font?", show=False),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    def __init__(self, vault_path: Path) -> None:
        super().__init__()
        self.vault = Vault(vault_path)
        self._story_cache: dict[str, Story] = {}
        self._col_keys: dict[str, object] = {}
        self._delete_pending: str | None = None
        self._tagging_story: Story | None = None
        self._tag_table_id: str | None = None
        self._reader_story: Story | None = None
        self._reader_width_idx = 1   # default: 65%
        self._reader_spacing_idx = 1  # default: Normal
        self._unread_paths: list[Path] = []
        self._archive_paths: list[Path] = []
        self._search_active = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-wrapper"):
            with Horizontal(id="lists"):
                with Vertical(classes="pane", id="unread-pane"):
                    yield Label("UNREAD", classes="pane-title", id="unread-title")
                    yield DataTable(id="unread-table", show_header=False, cursor_type="row")
                with Vertical(classes="pane", id="archive-pane"):
                    yield Label("ARCHIVE", classes="pane-title", id="archive-title")
                    yield DataTable(id="archive-table", show_header=False, cursor_type="row")
            with Vertical(id="reader-pane"):
                with Vertical(id="reader-bar"):
                    yield Label("", id="reader-title")
                    yield Label("", id="reader-meta")
                    yield Label(
                        r"\[Esc] close  \[o] browser  \[a/u] archive  \[t] tags  \[d+d] delete  \[w] width  \[f] display  \[Tab] switch",
                        id="reader-hints",
                    )
                with VerticalScroll(id="reader-scroll"):
                    yield Markdown("", id="reader-content")
        with Horizontal(id="search-bar"):
            yield Label("/", id="search-bar-label")
            yield SearchInput(id="search-bar-input", placeholder="search titles, tags, authors…")
        with Horizontal(id="tag-bar"):
            yield Label("Tags:", id="tag-bar-label")
            yield TagInput(id="tag-bar-input", placeholder="comma-separated tags…")
        yield Static(
            r"\[/] Search  \[q] Quit  \[s] Save  \[Tab] Switch  \[↵] Read inline  \[v] Fullscreen"
            r"  \[Esc] Close  \[R] Toggle  \[a] Archive  \[u] Unarchive"
            r"  \[t] Tag  \[o] Browser  \[d·d] Delete  \[w] Width  \[f] Display  \[r] Refresh",
            id="keys-bar",
        )

    def on_mount(self) -> None:
        for tid in ("unread-table", "archive-table"):
            t = self.query_one(f"#{tid}", DataTable)
            self._col_keys[tid] = t.add_column("title", width=None)
        self.query_one("#reader-pane").display = False
        self.query_one("#tag-bar").display = False
        self.query_one("#search-bar").display = False
        self.query_one("#unread-table").focus()
        self._load_list("unread")
        self._load_list("archive")

    # ── List loading ──────────────────────────────────────────────────────────

    @work(thread=True)
    def _load_list(self, pane: str) -> None:
        archived = pane == "archive"
        paths = self.vault.list_paths(archived=archived)
        self.app.call_from_thread(self._fill_table, pane, paths, archived)

    def _fill_table(self, pane: str, paths: list[Path], archived: bool) -> None:
        if pane == "unread":
            self._unread_paths = paths
        else:
            self._archive_paths = paths
        table = self.query_one(f"#{pane}-table", DataTable)
        table.clear()
        for path in paths:
            table.add_row(path.stem, key=str(path))
        label = "UNREAD" if pane == "unread" else "ARCHIVE"
        self.query_one(f"#{pane}-title", Label).update(f"{label} ({len(paths)})")
        self._star_scan(pane, paths, archived)

    def reload_pane(self, pane: str) -> None:
        self._load_list(pane)

    def refresh_lists(self) -> None:
        self._story_cache.clear()
        self._load_list("unread")
        self._load_list("archive")

    # ── Priority star background scan ─────────────────────────────────────────

    @work(thread=True)
    def _star_scan(self, pane: str, paths: list[Path], archived: bool) -> None:
        table_id = f"{pane}-table"
        batch: list[tuple[str, str]] = []
        for path in paths:
            key = str(path)
            story = self._story_cache.get(key) or self.vault.parse_story(path, archived)
            self._story_cache[key] = story
            if "priority" in story.tags:
                batch.append((key, story.display_title))
            if len(batch) >= 25:
                self.app.call_from_thread(self._apply_stars, table_id, list(batch))
                batch.clear()
        if batch:
            self.app.call_from_thread(self._apply_stars, table_id, batch)

    def _apply_stars(self, table_id: str, updates: list[tuple[str, str]]) -> None:
        col_key = self._col_keys.get(table_id)
        if col_key is None:
            return
        table = self.query_one(f"#{table_id}", DataTable)
        for row_key, title in updates:
            try:
                table.update_cell(row_key, col_key, f"{STAR} {title}")
            except Exception:
                pass

    # ── Lazy enrich on highlight ───────────────────────────────────────────────

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        key = str(event.row_key.value)
        if key not in self._story_cache:
            archived = event.data_table.id == "archive-table"
            self._enrich(Path(key), archived)

    @work(thread=True)
    def _enrich(self, path: Path, archived: bool) -> None:
        story = self.vault.parse_story(path, archived)
        key = str(path)
        self._story_cache[key] = story
        if "priority" in story.tags:
            table_id = "archive-table" if archived else "unread-table"
            self.app.call_from_thread(
                self._apply_stars, table_id, [(key, story.display_title)]
            )

    # ── Open reader on Enter ───────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None:
            return
        key = str(event.row_key.value)
        archived = event.data_table.id == "archive-table"
        story = self._story_cache.get(key) or self.vault.parse_story(Path(key), archived)
        self._story_cache[key] = story
        self._open_reader(story)

    def _open_reader(self, story: Story) -> None:
        self._reader_story = story
        reader_pane = self.query_one("#reader-pane")
        if not reader_pane.display:
            reader_pane.display = True
            self.query_one("#lists").styles.height = "40%"
        self.query_one("#reader-title", Label).update(story.display_title)
        self.query_one("#reader-meta", Label).update(self._reader_meta(story))
        content_widget = self.query_one("#reader-content", Markdown)
        content_widget.styles.width = READER_WIDTHS[self._reader_width_idx]
        _, padding = SPACING_OPTIONS[self._reader_spacing_idx]
        content_widget.styles.padding = padding
        content_widget.update("Loading…")
        self.query_one("#reader-scroll").focus()
        self._load_reader_content(story)

    @work(thread=True)
    def _load_reader_content(self, story: Story) -> None:
        content = self.vault.read_content(story)
        def update() -> None:
            if self._reader_story is story:
                self.query_one("#reader-content", Markdown).update(content)
        self.app.call_from_thread(update)

    def _close_reader(self) -> None:
        reader_pane = self.query_one("#reader-pane")
        if not reader_pane.display:
            return
        reader_pane.display = False
        self.query_one("#lists").styles.height = "1fr"
        self._reader_story = None
        if not isinstance(self.focused, DataTable):
            self.query_one("#unread-table").focus()

    def _reader_meta(self, story: Story) -> str:
        parts = []
        if story.domain:
            parts.append(story.domain)
        if story.authors:
            parts.append(f"by {', '.join(story.authors)}")
        if story.published and str(story.published) not in ("", "None"):
            parts.append(str(story.published))
        if story.tags:
            parts.append("  ".join(f"#{t}" for t in story.tags))
        return "  ·  ".join(parts)

    # ── Row helpers ───────────────────────────────────────────────────────────

    def remove_story_row(self, row_key: str, table_id: str) -> None:
        try:
            table = self.query_one(f"#{table_id}", DataTable)
            table.remove_row(row_key)
            self._story_cache.pop(row_key, None)
            pane = table_id.replace("-table", "")
            label = "UNREAD" if pane == "unread" else "ARCHIVE"
            self.query_one(f"#{pane}-title", Label).update(f"{label} ({table.row_count})")
        except Exception:
            pass

    def _focused_story(self) -> Story | None:
        focused = self.focused
        if not isinstance(focused, DataTable) or focused.row_count == 0:
            return None
        try:
            cell_key = focused.coordinate_to_cell_key(focused.cursor_coordinate)
            key = str(cell_key.row_key.value)
            archived = focused.id == "archive-table"
            if key not in self._story_cache:
                self._story_cache[key] = self.vault.parse_story(Path(key), archived)
            return self._story_cache.get(key)
        except Exception:
            return None

    def _active_story(self) -> Story | None:
        """Reader story if reader is focused, else highlighted list story."""
        focused = self.focused
        if focused is not None and focused.id in ("reader-scroll", "reader-content"):
            return self._reader_story
        return self._focused_story()

    def _focused_table_id(self) -> str | None:
        focused = self.focused
        return focused.id if isinstance(focused, DataTable) else None

    # ── Inline tag bar ────────────────────────────────────────────────────────

    # ── Search ────────────────────────────────────────────────────────────────

    def action_search(self) -> None:
        if self.query_one("#tag-bar").display:
            return
        self._search_active = True
        search_bar = self.query_one("#search-bar")
        search_bar.display = True
        inp = self.query_one("#search-bar-input", SearchInput)
        inp.value = ""
        inp.focus()

    def hide_search_bar(self) -> None:
        self.query_one("#search-bar").display = False
        self._search_active = False
        self._apply_search("")
        try:
            self.query_one("#unread-table").focus()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-bar-input":
            self._apply_search(event.value)

    def _apply_search(self, query: str) -> None:
        q = query.lower().strip()
        for pane, paths, archived in [
            ("unread", self._unread_paths, False),
            ("archive", self._archive_paths, True),
        ]:
            table_id = f"{pane}-table"
            table = self.query_one(f"#{table_id}", DataTable)
            table.clear(columns=True)
            col_key = table.add_column("title", width=None)
            self._col_keys[table_id] = col_key
            matches: list[Path] = []
            for path in paths:
                key = str(path)
                story = self._story_cache.get(key)
                if q:
                    haystack = path.stem.lower()
                    if story:
                        haystack += " " + story.display_title.lower()
                        haystack += " " + " ".join(story.tags).lower()
                        haystack += " " + " ".join(story.authors).lower()
                    if q not in haystack:
                        continue
                matches.append(path)
            for path in matches:
                key = str(path)
                story = self._story_cache.get(key)
                title = story.display_title if story else path.stem
                star = f"{STAR} " if story and "priority" in story.tags else ""
                table.add_row(star + title, key=key)
            label = "UNREAD" if pane == "unread" else "ARCHIVE"
            count = f"{len(matches)}/{len(paths)}" if q else str(len(paths))
            self.query_one(f"#{pane}-title", Label).update(f"{label} ({count})")

    # ── Inline tag bar ────────────────────────────────────────────────────────

    def hide_tag_bar(self) -> None:
        self.query_one("#tag-bar").display = False
        self._tagging_story = None
        if self._tag_table_id:
            try:
                self.query_one(f"#{self._tag_table_id}").focus()
            except Exception:
                pass
        self._tag_table_id = None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-bar-input":
            for tid in ("unread-table", "archive-table"):
                table = self.query_one(f"#{tid}", DataTable)
                if table.row_count > 0:
                    table.focus()
                    return
            return
        if event.input.id != "tag-bar-input":
            return
        story = self._tagging_story
        if story is None:
            self.hide_tag_bar()
            return
        tags = [t.strip() for t in event.value.split(",") if t.strip()]
        self.vault.save_tags(story, tags)
        self._update_story_display(story)
        self.hide_tag_bar()

    def _update_story_display(self, story: Story) -> None:
        """Update star in table and reader meta after tag change."""
        table_id = "archive-table" if story.is_archived else "unread-table"
        row_key = str(story.path)
        col_key = self._col_keys.get(table_id)
        if col_key is not None:
            display = f"{STAR} {story.display_title}" if "priority" in story.tags else story.display_title
            try:
                self.query_one(f"#{table_id}", DataTable).update_cell(row_key, col_key, display)
            except Exception:
                pass
        if self._reader_story is story:
            self.query_one("#reader-meta", Label).update(self._reader_meta(story))

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_switch_pane(self) -> None:
        focused = self.focused
        reader_open = self.query_one("#reader-pane").display
        if reader_open:
            if isinstance(focused, DataTable) and focused.id == "unread-table":
                self.query_one("#archive-table").focus()
            elif isinstance(focused, DataTable) and focused.id == "archive-table":
                self.query_one("#reader-scroll").focus()
            else:
                self.query_one("#unread-table").focus()
        else:
            if isinstance(focused, DataTable) and focused.id == "unread-table":
                self.query_one("#archive-table").focus()
            else:
                self.query_one("#unread-table").focus()

    def action_close_reader(self) -> None:
        self._close_reader()

    def action_open_fullscreen(self) -> None:
        story = self._active_story()
        if story is None:
            self.notify("No story selected")
            return
        self.push_screen(ReaderScreen(story, self.vault))

    def action_toggle_read(self) -> None:
        story = self._active_story()
        if story is None:
            return
        old_key = str(story.path)
        if story.is_archived:
            self.vault.unarchive(story)
            self.remove_story_row(old_key, "archive-table")
            self._story_cache[str(story.path)] = story
            self.notify(f"Moved to Unread: {story.display_title}")
            self.reload_pane("unread")
        else:
            self.vault.archive(story)
            self.remove_story_row(old_key, "unread-table")
            self._story_cache[str(story.path)] = story
            self.notify(f"Archived: {story.display_title}")
            self.reload_pane("archive")
        if self._reader_story is story:
            self.query_one("#reader-meta", Label).update(self._reader_meta(story))

    def action_archive_story(self) -> None:
        story = self._active_story()
        if story and not story.is_archived:
            old_key = str(story.path)
            self.vault.archive(story)
            self.remove_story_row(old_key, "unread-table")
            self._story_cache[str(story.path)] = story
            self.notify(f"Archived: {story.display_title}")
            if self._reader_story is story:
                self._close_reader()
            self.reload_pane("archive")

    def action_unarchive_story(self) -> None:
        story = self._active_story()
        if story and story.is_archived:
            old_key = str(story.path)
            self.vault.unarchive(story)
            self.remove_story_row(old_key, "archive-table")
            self._story_cache[str(story.path)] = story
            self.notify(f"Moved to Unread: {story.display_title}")
            if self._reader_story is story:
                self._close_reader()
            self.reload_pane("unread")

    def action_tag_story(self) -> None:
        story = self._active_story()
        if story is None:
            return
        if self.query_one("#reader-pane").display:
            # Reader is open — use modal
            self.push_screen(
                TagModal(story, self.vault),
                lambda updated: self._update_story_display(story) if updated else None,
            )
        else:
            # Lists only — use inline bar
            self._tagging_story = story
            self._tag_table_id = self._focused_table_id()
            tag_input = self.query_one("#tag-bar-input", TagInput)
            tag_input.value = ", ".join(story.tags)
            self.query_one("#tag-bar-label", Label).update(
                f"Tags [{story.display_title[:35]}]:"
            )
            self.query_one("#tag-bar").display = True
            tag_input.focus()

    def action_open_browser(self) -> None:
        story = self._active_story()
        if story and story.source:
            subprocess.run(["open", story.source])
            self.notify("Opening in browser…")

    def action_delete_story(self) -> None:
        story = self._active_story()
        if story is None:
            return
        key = str(story.path)
        if self._delete_pending == key:
            table_id = "archive-table" if story.is_archived else "unread-table"
            story.path.unlink(missing_ok=True)
            self.remove_story_row(key, table_id)
            self._delete_pending = None
            if self._reader_story is story:
                self._close_reader()
            self.notify(f"Deleted: {story.display_title}", severity="warning")
        else:
            self._delete_pending = key
            self.notify(
                f"Press D again to delete: {story.display_title[:50]}",
                severity="warning",
                timeout=3,
            )
            self.set_timer(3.0, self._clear_delete_pending)

    def _clear_delete_pending(self) -> None:
        self._delete_pending = None

    def action_cycle_width(self) -> None:
        if not self.query_one("#reader-pane").display:
            self.notify("Open an article first (Enter)")
            return
        self._reader_width_idx = (self._reader_width_idx + 1) % len(READER_WIDTHS)
        width = READER_WIDTHS[self._reader_width_idx]
        self.query_one("#reader-content", Markdown).styles.width = width
        self.notify(f"Reading width: {width}")

    def action_font_info(self) -> None:
        def on_close(result: tuple[int, int] | None) -> None:
            if result is None:
                return
            width_idx, spacing_idx = result
            self._reader_width_idx = width_idx
            self._reader_spacing_idx = spacing_idx
            reader_open = self.query_one("#reader-pane").display
            if reader_open:
                content = self.query_one("#reader-content", Markdown)
                content.styles.width = READER_WIDTHS[width_idx]
                _, padding = SPACING_OPTIONS[spacing_idx]
                content.styles.padding = padding

        self.push_screen(
            DisplayScreen(self._reader_width_idx, self._reader_spacing_idx),
            on_close,
        )

    def action_save_article(self) -> None:
        self.push_screen(SaveScreen(self.vault), self._on_article_saved)

    def action_refresh(self) -> None:
        self.refresh_lists()

    def _on_article_saved(self, story: Story | None) -> None:
        if story:
            self.notify(f"Saved: {story.display_title}")
            self.reload_pane("unread")
