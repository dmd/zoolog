#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["python-dateutil"]
# ///

from dateutil.parser import parse
from pathlib import Path
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument("initial", choices=("J", "G"))
parser.add_argument("filename", type=Path)
args = parser.parse_args()

source = args.filename.read_bytes()
try:
    lines = source.decode("utf-8").splitlines(keepends=True)
except UnicodeDecodeError:
    lines = source.decode("mac_roman").splitlines(keepends=True)

outfile = None
for line in lines:
    if re.match(r"^\d+/\d+/\d+\s+$", line):
        date = parse(line).strftime('%Y-%m-%d')
        # start a new file; add some blank to prev first
        if outfile:
            open(outfile, "a").write("\n\n")
        outfile = f"{date}-{args.initial}-{date}.txt"
        open(outfile, "a").write(f"# {date} {args.initial}\n")
    else:
        open(outfile, "a").write(line)
