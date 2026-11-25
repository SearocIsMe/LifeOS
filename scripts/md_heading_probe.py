"""Print the heading outline of a Markdown file (UTF-8 safe on Windows cmd).

Usage:
    python scripts/md_heading_probe.py demo/esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md
"""

from __future__ import annotations

import io
import sys


def main(argv: list[str]) -> int:
    path = argv[1]
    with io.open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    print(f"file       : {path}")
    print(f"total lines: {len(lines)}")
    print("\n--- headings")
    for i, line in enumerate(lines, 1):
        if line.startswith("#"):
            print(f"{i:6d}  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
