"""List every subject CN actually compiled into the firmware CA bundle.

Used to decide which commercial CA brands an ESP32 device will trust,
without guessing from `cacrt_all.pem`.

Usage:
    python scripts/crt_bundle_list.py <build/x509_crt_bundle.S> [--filter SUBSTR]
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "scripts")
from crt_bundle_inspect import _load_blob, parse_bundle  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--filter", default=None, help="case-insensitive substring filter")
    args = ap.parse_args(argv[1:])

    blob = _load_blob(args.bundle)
    entries = parse_bundle(blob)
    names = [n for n, _ in entries]

    print(f"total compiled certificates: {len(names)}")

    if args.filter:
        needle = args.filter.lower()
        hits = [n for n in names if needle in n.lower()]
        print(f"filter {args.filter!r}: {len(hits)} match(es)")
        for n in sorted(hits):
            print(f"    {n}")
        return 0

    print("\n--- all subject CN (bundle order, i.e. DER-sorted)")
    for i, n in enumerate(names):
        print(f"{i:4d}  {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
