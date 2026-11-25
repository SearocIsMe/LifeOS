"""Check whether an ASCII string exists in a binary (e.g. verify a CA root was flashed).

The ESP-IDF CA bundle stores subject names as raw DER; the CN appears as plain
ASCII inside the DER, so a search for the CN text works as a smoke test.

Usage:
    python scripts/bin_contains_string.py build/merged-binary.bin "Root YE"
"""

from __future__ import annotations

import argparse
import io
import sys


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("needle")
    args = ap.parse_args(argv[1:])

    with io.open(args.binary, "rb") as fh:
        blob = fh.read()

    needle = args.needle.encode("ascii")
    hits = []
    start = 0
    while True:
        idx = blob.find(needle, start)
        if idx < 0:
            break
        hits.append(idx)
        start = idx + 1

    print(f"file    : {args.binary}")
    print(f"size    : {len(blob)} bytes")
    print(f"needle  : {args.needle!r}")
    print(f"hits    : {len(hits)}")
    for h in hits[:10]:
        print(f"    offset 0x{h:08x}")

    if not hits:
        print("\nNOT FOUND -> this string is not in the image you flashed.")
        return 1

    print("\nFOUND -> the string is present in the image.")
    print("Note: CN text alone does not prove the cert is in the *bundle*;")
    print("also check build/x509_crt_bundle.S with crt_bundle_inspect.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
