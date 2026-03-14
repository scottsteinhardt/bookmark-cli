from dataclasses import dataclass

import httpx
import trafilatura


@dataclass
class ArticleData:
    title: str
    url: str
    content: str
    author: str = ""
    description: str = ""
    published: str = ""


def fetch_article(url: str) -> ArticleData:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        html = response.text

    content = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    ) or ""

    metadata = trafilatura.extract_metadata(html, default_url=url)

    title = author = description = published = ""
    if metadata:
        title = metadata.title or ""
        author = metadata.author or ""
        description = metadata.description or ""
        published = metadata.date or ""

    if not title:
        title = url

    return ArticleData(
        title=title,
        url=url,
        content=content,
        author=author,
        description=description,
        published=published,
    )
