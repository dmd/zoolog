#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Build the static data bundle for the Zoolog PWA.

Reads every ../posts/*.txt entry, decodes quoted-printable, parses the
date/category header, and emits:

  data/posts.json  - array of entries [{i, d, c, b}, ...] sorted oldest-first
  data/meta.json   - counts, category breakdown, date range, build time

The PWA loads posts.json once, builds a client-side search index, and caches
it for offline use. No server required.
"""
import json
import quopri
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT.parent / "posts"
DATA_DIR = ROOT / "data"

# Letter token in the filename / header -> canonical category code.
# Checked in priority order. AHNS must win over the single letters because an
# AHNS filename also contains the child-initial fields. The header letter in the
# body (e.g. "# 2017-09-05 S") is a child's initial, NOT the category, so we rely
# on the filename for the category and only use the header for the date.
CATEGORY_PRIORITY = ("AHNS", "J", "G", "D", "A")

HEADER_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def decode_qp(raw: str) -> str:
    """Decode quoted-printable; fall back to the raw text on failure."""
    try:
        return quopri.decodestring(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return raw


def category_from_filename(name: str) -> str | None:
    parts = Path(name).stem.split("-")
    for cat in CATEGORY_PRIORITY:
        if cat in parts:
            return cat
    return None


def parse_entry(path: Path):
    """Return (date_str, category, body) or None if unparseable."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = decode_qp(raw)
    lines = text.strip("\n").split("\n")
    if not lines:
        return None

    first = lines[0].strip()
    date_str = None

    if first.startswith("#"):
        m = HEADER_RE.search(first)
        if m:
            date_str = m.group(1)
        body_lines = lines[1:]
    else:
        body_lines = lines

    # The leading filename date is the authoritative entry date.
    fm = DATE_RE.match(path.name)
    if fm:
        date_str = f"{fm.group(1)}-{fm.group(2)}-{fm.group(3)}"

    category = category_from_filename(path.name)

    if not date_str or not category:
        return None

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    body = "\n".join(body_lines).strip()
    return date_str, category, body


def main() -> int:
    if not POSTS_DIR.exists():
        print(f"Posts directory not found: {POSTS_DIR}")
        return 1

    entries = []
    skipped = 0
    for path in sorted(POSTS_DIR.glob("*.txt")):
        parsed = parse_entry(path)
        if parsed is None:
            skipped += 1
            continue
        date_str, category, body = parsed
        entries.append({"d": date_str, "c": category, "b": body})

    # Oldest-first, stable across rebuilds. Assign ids after sorting.
    entries.sort(key=lambda e: (e["d"], e["c"]))
    for i, e in enumerate(entries):
        e_with_id = {"i": i, "d": e["d"], "c": e["c"], "b": e["b"]}
        entries[i] = e_with_id

    DATA_DIR.mkdir(exist_ok=True)
    posts_path = DATA_DIR / "posts.json"
    posts_path.write_text(
        json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    counts: dict[str, int] = {}
    for e in entries:
        counts[e["c"]] = counts.get(e["c"], 0) + 1

    meta = {
        "count": len(entries),
        "categories": counts,
        "date_range": {
            "start": entries[0]["d"] if entries else None,
            "end": entries[-1]["d"] if entries else None,
        },
        "built": datetime.now().isoformat(timespec="seconds"),
    }
    (DATA_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    size_mb = posts_path.stat().st_size / (1024 * 1024)
    print(f"Wrote {len(entries)} entries ({size_mb:.2f} MB) to {posts_path}")
    print(f"Skipped {skipped} unparseable files")
    print(f"Categories: {counts}")
    print(f"Date range: {meta['date_range']['start']} .. {meta['date_range']['end']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
