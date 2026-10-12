"""Knowledge base built from barndobible.com's own posts and pages.

Content comes from the site's public WordPress REST API
(/wp-json/wp/v2/posts and /pages), is cleaned to text, split into
section-sized chunks (one per H2), and searched with BM25.

CLI:
    python -m app.agent.kb sync      # fetch from the site and write the cache
    python -m app.agent.kb search "spray foam timing"
"""

from __future__ import annotations

import html
import json
import logging
import math
import re
import sys
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

# Pages that are not useful as build knowledge.
SKIP_SLUGS = {"privacy-policy", "affiliate-disclosure", "contact", "blog", "services"}
MAX_CHUNK_WORDS = 450


@dataclass
class Chunk:
    id: str
    title: str  # article title
    heading: str  # section heading within the article ("" for the intro)
    url: str
    text: str


# ---------------------------------------------------------------- HTML -> text
class _TextExtractor(HTMLParser):
    """Turns WordPress block HTML into text, keeping H2 section boundaries."""

    BLOCK = {"p", "li", "h3", "h4", "tr", "figcaption", "blockquote", "br", "div"}
    SKIP = {"script", "style", "noscript", "svg", "button"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections: list[tuple[str, list[str]]] = [("", [])]
        self._buf: list[str] = []
        self._skip_depth = 0
        self._in_h2 = False
        self._h2_buf: list[str] = []
        self._cells: list[str] | None = None
        self._skip_tag: str | None = None  # element whose whole subtree is dropped (e.g. button blocks)
        self._skip_nest = 0

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            self.sections[-1][1].append(text)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if self._skip_tag:
            if tag == self._skip_tag:
                self._skip_nest += 1
            return
        if "wp-block-buttons" in (dict(attrs).get("class") or ""):
            self._skip_tag, self._skip_nest = tag, 1
            return
        if tag in self.SKIP:
            self._skip_depth += 1
            return
        if tag == "h2":
            self._flush()
            self._in_h2, self._h2_buf = True, []
        elif tag == "tr":
            self._flush()
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._buf = []
        elif tag in self.BLOCK:
            self._flush()
        if tag == "li":
            self._buf.append("- ")
        if tag in ("h3", "h4"):
            self._buf.append("### ")

    def handle_endtag(self, tag):
        if self._skip_tag:
            if tag == self._skip_tag:
                self._skip_nest -= 1
                if self._skip_nest == 0:
                    self._skip_tag = None
            return
        if tag in self.SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "h2" and self._in_h2:
            heading = re.sub(r"\s+", " ", "".join(self._h2_buf)).strip()
            self.sections.append((heading, []))
            self._in_h2 = False
        elif tag in ("td", "th") and self._cells is not None:
            self._cells.append(re.sub(r"\s+", " ", "".join(self._buf)).strip())
            self._buf = []
        elif tag == "tr" and self._cells is not None:
            row = " | ".join(c for c in self._cells if c)
            if row:
                self.sections[-1][1].append(row)
            self._cells = None
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._skip_depth or self._skip_tag:
            return
        if self._in_h2:
            self._h2_buf.append(data)
        else:
            self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def html_to_sections(raw_html: str) -> list[tuple[str, str]]:
    p = _TextExtractor()
    p.feed(raw_html)
    p.close()
    return [(h, "\n".join(lines)) for h, lines in p.sections if lines]


def _split_words(text: str, max_words: int) -> list[str]:
    words = text.split(" ")
    if len(words) <= max_words:
        return [text]
    out, cur = [], []
    for line in text.split("\n"):
        if cur and len(" ".join(cur).split()) + len(line.split()) > max_words:
            out.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def chunks_from_item(item: dict) -> list[Chunk]:
    title = html.unescape(item["title"]["rendered"]).strip()
    url = item["link"]
    chunks = []
    for i, (heading, text) in enumerate(html_to_sections(item["content"]["rendered"])):
        for j, part in enumerate(_split_words(text, MAX_CHUNK_WORDS)):
            chunks.append(Chunk(f"{item['id']}-{i}-{j}", title, html.unescape(heading), url, part))
    return chunks


# ---------------------------------------------------------------- BM25 search
_STOP = set(
    "a an and are as at be by can do does for from has have how i if in is it its my of on or "
    "so that the their there this to was what when where which who will with you your".split()
)


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for t in toks:
        if t in _STOP:
            continue
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


class KnowledgeBase:
    def __init__(self, chunks: list[Chunk] | None = None, synced_at: str | None = None, source: str = ""):
        self.synced_at = synced_at
        self.source = source
        self._lock = threading.Lock()
        self._index(chunks or [])

    def _index(self, chunks: list[Chunk]) -> None:
        docs = [tokenize(f"{c.title} {c.heading} {c.heading} {c.text}") for c in chunks]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs) or 1
        idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        tfs = [Counter(d) for d in docs]
        lens = [len(d) for d in docs]
        avg = (sum(lens) / len(lens)) if lens else 1.0
        with getattr(self, "_lock", threading.Lock()):
            self.chunks, self._idf, self._tfs, self._lens, self._avg = chunks, idf, tfs, lens, avg

    def replace(self, chunks: list[Chunk], synced_at: str, source: str) -> None:
        self._index(chunks)
        self.synced_at, self.source = synced_at, source

    def search(self, query: str, k: int = 6, k1: float = 1.5, b: float = 0.75) -> list[Chunk]:
        q = set(tokenize(query))
        if not q or not self.chunks:
            return []
        scores = []
        for i, tf in enumerate(self._tfs):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self._idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * self._lens[i] / self._avg))
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [self.chunks[i] for _, i in scores[:k]]

    @property
    def article_count(self) -> int:
        return len({c.url for c in self.chunks})

    # ---- persistence
    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"synced_at": self.synced_at, "source": self.source, "chunks": [asdict(c) for c in self.chunks]}
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)

    @classmethod
    def load(cls, path: str) -> KnowledgeBase:
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls([Chunk(**c) for c in data["chunks"]], data.get("synced_at"), data.get("source", ""))


# ---------------------------------------------------------------- fetching
def fetch_items(base_url: str, client: httpx.Client | None = None) -> list[dict]:
    """All published posts and pages from the site's public REST API."""
    http = client or httpx.Client(timeout=30, headers={"User-Agent": "BarndoAgent-KB/1.0"})
    items: list[dict] = []
    for kind in ("posts", "pages"):
        page = 1
        while True:
            r = http.get(
                f"{base_url.rstrip('/')}/wp-json/wp/v2/{kind}",
                params={"per_page": 50, "page": page, "_fields": "id,slug,link,title,content"},
            )
            if r.status_code == 400 and page > 1:  # past the last page
                break
            r.raise_for_status()
            batch = r.json()
            items.extend(i for i in batch if i.get("slug") not in SKIP_SLUGS)
            if page >= int(r.headers.get("X-WP-TotalPages", "1")):
                break
            page += 1
    return items


def build_chunks(items: list[dict]) -> list[Chunk]:
    out: list[Chunk] = []
    for item in items:
        out.extend(chunks_from_item(item))
    return out


def sync(kb: KnowledgeBase, base_url: str, cache_path: str, client: httpx.Client | None = None) -> int:
    items = fetch_items(base_url, client)
    chunks = build_chunks(items)
    if not chunks:
        raise RuntimeError("Site returned no content; keeping the previous knowledge base")
    kb.replace(chunks, datetime.now(UTC).isoformat(timespec="seconds"), base_url)
    kb.save(cache_path)
    log.info("Knowledge base synced: %d articles, %d chunks", kb.article_count, len(chunks))
    return len(chunks)


# ---------------------------------------------------------------- shared instance
_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        from app.config import get_settings

        _kb = KnowledgeBase.load(get_settings().kb_cache_path)
    return _kb


def reset_kb() -> None:
    global _kb
    _kb = None


if __name__ == "__main__":
    from app.config import get_settings

    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    if len(sys.argv) > 1 and sys.argv[1] == "sync":
        kb = get_kb()
        n = sync(kb, s.kb_source_url, s.kb_cache_path)
        print(f"Synced {kb.article_count} articles into {n} chunks -> {s.kb_cache_path}")
    elif len(sys.argv) > 2 and sys.argv[1] == "search":
        for c in get_kb().search(" ".join(sys.argv[2:]), k=5):
            print(f"- {c.title} > {c.heading}\n  {c.url}\n  {c.text[:160]}...\n")
    else:
        print('usage: python -m app.agent.kb sync | search "query"')
