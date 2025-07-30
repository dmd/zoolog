#!/usr/bin/env python3

from dateutil.parser import parse
import sys
import re
outfile = None
with open(sys.argv[1], "r") as fp:
    for line in fp.readlines():
        if re.match(r"^\d+/\d+/\d+\s+$", line):
            date = parse(line).strftime('%Y-%m-%d')
            # start a new file; add some blank to prev first
            if outfile:
                open(outfile, "a").write("\n\n")
            outfile = f"{date}-J-{date}.txt"
            open(outfile, "a").write("# " + date + " J\n")
        else:
            open(outfile, "a").write(line)
