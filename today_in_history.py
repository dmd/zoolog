#!/usr/bin/env -S uv run --script
# /// script
# dependencies = []
# ///

"""Show zoolog posts from this day in previous years."""

import quopri
import sys
from datetime import date
from pathlib import Path

POSTS_DIR = Path(__file__).parent / "posts"

today = date.today()
if len(sys.argv) > 1:
    # Allow overriding with MM-DD or YYYY-MM-DD
    arg = sys.argv[1]
    parts = arg.split("-")
    if len(parts) == 2:
        today = today.replace(month=int(parts[0]), day=int(parts[1]))
    elif len(parts) == 3:
        today = date(int(parts[0]), int(parts[1]), int(parts[2]))

month_day = today.strftime("%m-%d")

matches = []
for f in sorted(POSTS_DIR.glob("*.txt")):
    # Filename: YYYY-MM-DD-X-YYYY-MM-DD.txt — use first date
    name = f.stem
    parts = name.split("-")
    if len(parts) >= 4:
        file_md = f"{parts[1]}-{parts[2]}"
        if file_md == month_day:
            year = parts[0]
            author = parts[3]
            matches.append((year, author, f))

if not matches:
    print(f"No posts found for {today.strftime('%B %d')}.")
    sys.exit(0)

print(f"=== Today in History: {today.strftime('%B %d')} ===\n")
for year, author, path in matches:
    raw = path.read_bytes()
    content = quopri.decodestring(raw).decode("utf-8").strip()
    # Skip the header line (e.g. "# 2013-09-06 A")
    lines = content.split("\n")
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else content
    years_ago = today.year - int(year)
    print(f"--- {year} ({years_ago} year{'s' if years_ago != 1 else ''} ago) [{author}] ---")
    print(body)
    print()
