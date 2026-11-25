"""Trim a PEM certificate chain to its first N certificates.

Used to test whether serving a shorter chain makes the ESP32 CA-bundle lookup
succeed (see docs/Deployment.md 附十三 / 方案 A).

Usage:
    python scripts/chain_trim.py <in.pem> <out.pem> --keep 3
"""

from __future__ import annotations

import argparse
import io
import sys


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--keep", type=int, required=True,
                    help="number of certificates to keep, counting from the leaf")
    args = ap.parse_args(argv[1:])

    with io.open(args.src, "rb") as fh:
        raw = fh.read()

    marker = b"-----END CERTIFICATE-----"
    pems: list[bytes] = []
    for chunk in raw.split(marker):
        if b"-----BEGIN CERTIFICATE-----" not in chunk:
            continue
        body = chunk.split(b"-----BEGIN CERTIFICATE-----", 1)[1].strip()
        pems.append(
            b"-----BEGIN CERTIFICATE-----\n"
            + body.strip()
            + b"\n-----END CERTIFICATE-----\n"
        )

    if not pems:
        print("no certificates found in source", file=sys.stderr)
        return 2

    keep = pems[: args.keep]
    with io.open(args.dst, "wb") as fh:
        fh.write(b"".join(keep))

    print(f"source chain : {len(pems)} cert(s)")
    print(f"kept         : {len(keep)} cert(s) -> {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
