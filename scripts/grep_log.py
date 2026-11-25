"""Filter a log file by keywords / regex, with line numbers (UTF-8 safe on Windows).

Usage:
    python scripts/grep_log.py reports/build.log --pattern "error|FAILED|CMake" --tail 80
"""

from __future__ import annotations

import argparse
import io
import re
import sys


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--pattern", required=True, help="case-insensitive regex")
    ap.add_argument("--tail", type=int, default=80, help="max matching lines to print")
    ap.add_argument("--context", type=int, default=0,
                    help="also print N lines after each match")
    args = ap.parse_args(argv[1:])

    with io.open(args.log, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    print(f"file {args.log}: {len(lines)} line(s)")

    rx = re.compile(args.pattern, re.IGNORECASE)
    hits = [i for i, line in enumerate(lines) if rx.search(line)]
    print(f"pattern {args.pattern!r}: {len(hits)} match(es)\n")

    shown = 0
    printed: set[int] = set()
    for i in hits:
        window = range(i, min(i + 1 + args.context, len(lines)))
        for j in window:
            if j in printed or shown >= args.tail:
                continue
            printed.add(j)
            print(f"{j + 1:7d} | {lines[j]}")
            shown += 1
        if shown >= args.tail:
            print(f"\n... truncated at --tail={args.tail}")
            break

    if not hits:
        print("--- last 20 lines for context")
        for j, line in enumerate(lines[-20:], start=max(0, len(lines) - 20) + 1):
            print(f"{j:7d} | {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
