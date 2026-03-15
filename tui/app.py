#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "textual>=1.0.0",
# ]
# ///
"""Zoolog TUI - Terminal interface for browsing family journal entries."""

import re
import sqlite3
import quopri
import sys
from datetime import datetime, timedelta
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import (
    Footer,
    Header,
    Input,
    Markdown,
    OptionList,
    Select,
    Static,
)
from textual.widgets.option_list import Option

# ---------------------------------------------------------------------------
# Database helpers (adapted from web/app.py)
# ---------------------------------------------------------------------------

POSTS_DIR = Path(__file__).parent.parent / "posts"
DB_URI = "file:zoolog_tui?mode=memory&cache=shared"
_PERSISTENT_CONN: sqlite3.Connection | None = None


def _ensure_conn() -> sqlite3.Connection:
    global _PERSISTENT_CONN
    if _PERSISTENT_CONN is None:
        _PERSISTENT_CONN = sqlite3.connect(DB_URI, uri=True, check_same_thread=False)
        _PERSISTENT_CONN.row_factory = sqlite3.Row
    return _PERSISTENT_CONN


def get_db() -> sqlite3.Connection:
    _ensure_conn()
    conn = sqlite3.connect(DB_URI, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _clean(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


def _extract(filename: str, content: str) -> dict | None:
    parts = filename.replace(".txt", "").split("-")
    if len(parts) < 6:
        return None
    date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    cat = "US"
    if "AHNS" in filename:
        cat = "AHNS"
    elif "J" in filename:
        cat = "J"
    elif "-D-" in filename:
        cat = "D"
    elif "-A-" in filename:
        cat = "A"

    try:
        decoded = quopri.decodestring(content.encode("utf-8")).decode("utf-8")
    except Exception:
        decoded = content

    lines = decoded.strip().split("\n")
    skip = 1 if lines and lines[0].startswith("#") else 0
    body = "\n".join(lines[skip:]).strip()
    title = (body[:50].replace("\n", " ").strip() + ("..." if len(body) > 50 else "")) if body else f"{date_str} {cat}"
    excerpt = body[:200] + ("..." if len(body) > 200 else "")
    return dict(
        filename=filename, date=dt, category=cat, title=title,
        content=body, clean_title=_clean(title), clean_content=_clean(body),
        excerpt=excerpt, year=dt.year, month=dt.month, day=dt.day,
    )


def create_db(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL, date TEXT NOT NULL, category TEXT NOT NULL,
        title TEXT, content TEXT, clean_title TEXT, clean_content TEXT,
        excerpt TEXT, year INTEGER, month INTEGER, day INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    try:
        c.execute("ALTER TABLE posts ADD COLUMN clean_title TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE posts ADD COLUMN clean_content TEXT")
    except sqlite3.OperationalError:
        pass
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
        filename, clean_title, clean_content, category,
        content='posts', content_rowid='id')""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
        INSERT INTO posts_fts(rowid, filename, clean_title, clean_content, category)
        VALUES (new.id, new.filename, new.clean_title, new.clean_content, new.category); END""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
        INSERT INTO posts_fts(posts_fts, rowid, filename, clean_title, clean_content, category)
        VALUES('delete', old.id, old.filename, old.clean_title, old.clean_content, old.category); END""")
    c.execute("""CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
        INSERT INTO posts_fts(posts_fts, rowid, filename, clean_title, clean_content, category)
        VALUES('delete', old.id, old.filename, old.clean_title, old.clean_content, old.category);
        INSERT INTO posts_fts(rowid, filename, clean_title, clean_content, category)
        VALUES (new.id, new.filename, new.clean_title, new.clean_content, new.category); END""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_posts_year_month ON posts(year, month)")
    conn.commit()


def index_posts() -> bool:
    if not POSTS_DIR.exists():
        return False
    conn = _ensure_conn()
    create_db(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM posts")
    conn.commit()
    files = sorted(POSTS_DIR.glob("*.txt"))
    n = 0
    for f in files:
        try:
            info = _extract(f.name, f.read_text("utf-8"))
            if info:
                cur.execute(
                    "INSERT INTO posts (filename,date,category,title,content,clean_title,clean_content,excerpt,year,month,day) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (info["filename"], info["date"].isoformat(), info["category"],
                     info["title"], info["content"], info["clean_title"],
                     info["clean_content"], info["excerpt"],
                     info["year"], info["month"], info["day"]),
                )
                n += 1
                if n % 1000 == 0:
                    conn.commit()
        except Exception:
            pass
    conn.commit()
    return True


def sanitize_fts(q: str) -> str:
    if not q:
        return q
    for ch in ['*', '(', ')', ':', '"', '-']:
        q = q.replace(ch, ' ')
    for op in ['AND', 'OR', 'NOT', 'NEAR']:
        q = q.replace(f' {op} ', ' ').replace(f' {op.lower()} ', ' ')
    return ' '.join(q.split())


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def query_posts(search="", category="", start_date="", end_date="", limit=200, offset=0):
    conn = get_db()
    cur = conn.cursor()
    conds, params = [], []
    if category:
        if category == "US":
            conds.append("posts.category IN (?,?)")
            params += ["A", "D"]
        else:
            conds.append("posts.category = ?")
            params.append(category)
    if start_date:
        conds.append("posts.date >= ?")
        params.append(start_date)
    if end_date:
        try:
            nd = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            conds.append("posts.date < ?")
            params.append(nd.strftime("%Y-%m-%d"))
        except ValueError:
            conds.append("posts.date <= ?")
            params.append(end_date)

    if search:
        sq = sanitize_fts(search)
        if not sq:
            conn.close()
            return [], 0
        wc = ("AND " + " AND ".join(conds)) if conds else ""
        q = f"SELECT posts.* FROM posts_fts JOIN posts ON posts.id=posts_fts.rowid WHERE posts_fts MATCH ? {wc} ORDER BY date ASC LIMIT ? OFFSET ?"
        cur.execute(q, [sq] + params + [limit, offset])
        rows = cur.fetchall()
        cq = f"SELECT COUNT(*) FROM posts_fts JOIN posts ON posts.id=posts_fts.rowid WHERE posts_fts MATCH ? {wc}"
        cur.execute(cq, [sq] + params)
    else:
        wc = ("WHERE " + " AND ".join(conds)) if conds else ""
        q = f"SELECT * FROM posts {wc} ORDER BY date ASC LIMIT ? OFFSET ?"
        cur.execute(q, params + [limit, offset])
        rows = cur.fetchall()
        cq = f"SELECT COUNT(*) FROM posts {wc}"
        cur.execute(cq, params)

    total = cur.fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_post(post_id: int) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts WHERE id=?", [post_id])
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_stats() -> dict:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM posts")
    total = cur.fetchone()[0]
    cur.execute("SELECT category, COUNT(*) FROM posts GROUP BY category")
    cats = dict(cur.fetchall())
    cur.execute("SELECT MIN(date), MAX(date) FROM posts")
    dr = cur.fetchone()
    conn.close()
    return {"total": total, "cats": cats, "min": dr[0] if dr[0] else "", "max": dr[1] if dr[1] else ""}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_COLORS = {"A": "green", "D": "cyan", "AHNS": "magenta", "J": "yellow", "US": "blue"}
CATEGORIES = [("All", ""), ("A+D", "US"), ("A", "A"), ("D", "D"), ("AHNS", "AHNS"), ("Uncle J", "J")]


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class ZoologApp(App):
    TITLE = "Zoolog"
    SUB_TITLE = "Family Journal Browser"

    CSS = """
    #filter-bar {
        height: 3;
        dock: top;
        padding: 0 1;
        background: $boost;
        layout: horizontal;
    }
    #filter-bar > * {
        margin: 0 1 0 0;
    }
    #search-input {
        width: 30;
    }
    #category-select {
        width: 16;
    }
    #date-from {
        width: 16;
    }
    #date-to {
        width: 16;
    }
    #main-area {
        height: 1fr;
        layout: horizontal;
    }
    #post-list {
        width: 1fr;
        min-width: 40;
        border: solid $primary;
    }
    #viewer-panel {
        width: 2fr;
        border: solid $secondary;
        padding: 1 2;
    }
    #viewer-meta {
        color: $text-muted;
        height: auto;
        margin-bottom: 1;
    }
    #viewer-body {
        height: auto;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $boost;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("j", "next_post", "Next", show=True),
        Binding("k", "prev_post", "Prev", show=True),
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "blur", "Back", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Search...", id="search-input")
            yield Select(CATEGORIES, value="", id="category-select", allow_blank=False)
            yield Input(placeholder="From YYYY-MM-DD", id="date-from")
            yield Input(placeholder="To YYYY-MM-DD", id="date-to")
        with Horizontal(id="main-area"):
            yield OptionList(id="post-list")
            with VerticalScroll(id="viewer-panel"):
                yield Static("Select a post to view", id="viewer-meta")
                yield Markdown("", id="viewer-body")
        yield Static("Loading...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._search = ""
        self._category = ""
        self._date_from = ""
        self._date_to = ""
        self._posts: list[dict] = []
        self._debounce_timer = None
        self.load_posts()

    @work(thread=True)
    def load_posts(self) -> None:
        posts, total = query_posts(
            search=self._search,
            category=self._category,
            start_date=self._date_from,
            end_date=self._date_to,
        )
        self.call_from_thread(self._update_list, posts, total)

    def _update_list(self, posts: list[dict], total: int) -> None:
        self._posts = posts
        ol = self.query_one("#post-list", OptionList)
        ol.clear_options()
        for p in posts:
            cat = p["category"]
            color = CATEGORY_COLORS.get(cat, "white")
            date_str = p["date"][:10]
            prompt = f"[{color}]{cat:>4}[/{color}] {date_str}  {p['title'][:55]}"
            ol.add_option(Option(prompt, id=str(p["id"])))

        stats = get_stats()
        cats = stats["cats"]
        parts = []
        for c in ["A", "D", "AHNS", "J"]:
            if c in cats:
                color = CATEGORY_COLORS[c]
                parts.append(f"[{color}]{c}:{cats[c]}[/{color}]")
        shown = len(posts)
        range_str = f"{stats['min'][:10]}..{stats['max'][:10]}" if stats["min"] else ""
        self.query_one("#status-bar", Static).update(
            f" {shown}/{total} posts | Total: {stats['total']} | {' '.join(parts)} | {range_str}"
        )

    # -- Filter events -------------------------------------------------------

    @on(Input.Changed, "#search-input")
    def _search_changed(self, event: Input.Changed) -> None:
        self._search = event.value.strip()
        self._debounced_load()

    def _debounced_load(self) -> None:
        if self._debounce_timer:
            self._debounce_timer.stop()
        self._debounce_timer = self.set_timer(0.3, self.load_posts)

    @on(Select.Changed, "#category-select")
    def _cat_changed(self, event: Select.Changed) -> None:
        self._category = event.value if event.value != Select.BLANK else ""
        self.load_posts()

    @on(Input.Submitted, "#date-from")
    def _from_changed(self, event: Input.Submitted) -> None:
        self._date_from = event.value.strip()
        self.load_posts()

    @on(Input.Submitted, "#date-to")
    def _to_changed(self, event: Input.Submitted) -> None:
        self._date_to = event.value.strip()
        self.load_posts()

    # -- Post selection ------------------------------------------------------

    @on(OptionList.OptionHighlighted, "#post-list")
    def _post_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option and event.option.id:
            self._show_post(int(event.option.id))

    @work(thread=True)
    def _show_post(self, post_id: int) -> None:
        post = get_post(post_id)
        if post:
            self.call_from_thread(self._render_post, post)

    def _render_post(self, post: dict) -> None:
        meta = self.query_one("#viewer-meta", Static)
        body = self.query_one("#viewer-body", Markdown)
        cat = post["category"]
        color = CATEGORY_COLORS.get(cat, "white")
        meta.update(f"[bold]{post['date'][:10]}[/bold]  [{color}][{cat}][/{color}]  [dim]{post['filename']}[/dim]")
        content = post["content"] or ""
        if self._search:
            terms = self._search.split()
            for t in terms:
                pattern = re.compile(re.escape(t), re.IGNORECASE)
                content = pattern.sub(lambda m: f"**{m.group()}**", content)
        body.update(content)
        self.query_one("#viewer-panel", VerticalScroll).scroll_home()

    # -- Key actions ---------------------------------------------------------

    def action_next_post(self) -> None:
        focused = self.focused
        if focused and focused.id in ("search-input", "date-from", "date-to"):
            return
        ol = self.query_one("#post-list", OptionList)
        ol.action_cursor_down()

    def action_prev_post(self) -> None:
        focused = self.focused
        if focused and focused.id in ("search-input", "date-from", "date-to"):
            return
        ol = self.query_one("#post-list", OptionList)
        ol.action_cursor_up()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_blur(self) -> None:
        self.query_one("#post-list", OptionList).focus()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("Indexing posts...")
    if not index_posts():
        print(f"Posts directory not found: {POSTS_DIR}", file=sys.stderr)
        sys.exit(1)
    stats = get_stats()
    print(f"Indexed {stats['total']} posts ({stats['min'][:10]}..{stats['max'][:10]})")
    app = ZoologApp()
    app.run()


if __name__ == "__main__":
    main()
