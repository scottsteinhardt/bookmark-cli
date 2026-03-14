import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import frontmatter


@dataclass
class Story:
    path: Path
    title: str
    source: str = ""
    authors: list[str] = field(default_factory=list)
    published: str = ""
    created: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    is_archived: bool = False

    @property
    def display_title(self) -> str:
        return self.title or self.path.stem

    @property
    def domain(self) -> str:
        if self.source:
            try:
                return urlparse(self.source).netloc.removeprefix("www.")
            except Exception:
                pass
        return ""

    @property
    def custom_tags(self) -> list[str]:
        return [t for t in self.tags if t != "clippings"]


class Vault:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.unread_dir = vault_path / "Unread"
        self.archive_dir = vault_path / "Archive"

    def list_paths(self, archived: bool = False) -> list[Path]:
        """Return paths sorted by modification time. Very fast — no file reads."""
        directory = self.archive_dir if archived else self.unread_dir
        return sorted(directory.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    def parse_story(self, path: Path, is_archived: bool) -> Story:
        return self._parse_story(path, is_archived)

    def _parse_story(self, path: Path, is_archived: bool) -> Story:
        try:
            # Read only the first 4KB — enough for frontmatter, avoids loading large HTML bodies
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(4096)
            post = frontmatter.loads(head)
            if post.metadata:
                title = post.metadata.get("title", path.stem)
                source = post.metadata.get("source", "")
                author_raw = post.metadata.get("author", [])
                if isinstance(author_raw, str):
                    author_raw = [author_raw]
                authors = [re.sub(r"\[\[(.+?)\]\]", r"\1", str(a)) for a in author_raw]
                tags_raw = post.metadata.get("tags", [])
                if isinstance(tags_raw, str):
                    tags_raw = [tags_raw]
                tags = [str(t) for t in tags_raw]
                return Story(
                    path=path,
                    title=str(title) if title else path.stem,
                    source=str(source) if source else "",
                    authors=authors,
                    published=str(post.metadata.get("published", "")),
                    created=str(post.metadata.get("created", "")),
                    description=str(post.metadata.get("description", "")),
                    tags=tags,
                    is_archived=is_archived,
                )
            else:
                # Old format: # Title\nSource: URL\n---\ncontent
                content = path.read_text(encoding="utf-8", errors="replace")
                title = path.stem
                source = ""
                for line in content.splitlines()[:10]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                    elif line.lower().startswith("source:"):
                        source = line[7:].strip()
                return Story(
                    path=path,
                    title=title,
                    source=source,
                    is_archived=is_archived,
                )
        except Exception:
            return Story(path=path, title=path.stem, is_archived=is_archived)

    def read_content(self, story: Story) -> str:
        try:
            post = frontmatter.load(str(story.path))
            return post.content
        except Exception:
            return story.path.read_text(encoding="utf-8", errors="replace")

    def archive(self, story: Story) -> None:
        dest = self._unique_path(self.archive_dir, story.path.name)
        story.path.rename(dest)
        story.path = dest
        story.is_archived = True

    def unarchive(self, story: Story) -> None:
        dest = self._unique_path(self.unread_dir, story.path.name)
        story.path.rename(dest)
        story.path = dest
        story.is_archived = False

    def save_tags(self, story: Story, tags: list[str]) -> None:
        story.tags = tags
        try:
            post = frontmatter.load(str(story.path))
            post.metadata["tags"] = tags
            with open(story.path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
        except Exception:
            pass

    def save_new(
        self,
        title: str,
        source: str,
        content: str,
        author: str = "",
        description: str = "",
        published: str = "",
    ) -> Story:
        safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)[:100].strip() or "Untitled"
        path = self._unique_path(self.unread_dir, safe_name + ".md")
        tags = ["clippings"]
        post = frontmatter.Post(
            content,
            title=title,
            source=source,
            author=[f"[[{author}]]"] if author else [],
            published=published,
            created=str(date.today()),
            description=description,
            tags=tags,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        return Story(
            path=path,
            title=title,
            source=source,
            authors=[author] if author else [],
            created=str(date.today()),
            description=description,
            tags=tags,
            is_archived=False,
        )

    def _unique_path(self, directory: Path, filename: str) -> Path:
        path = directory / filename
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        counter = 1
        while path.exists():
            path = directory / f"{stem} ({counter}){suffix}"
            counter += 1
        return path
