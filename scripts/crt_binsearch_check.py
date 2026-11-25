"""Replay ESP-IDF's BINARY search (`esp_crt_find_cert`) against a real bundle.

This is the decisive check for "the CA IS in the bundle but TLS still fails":
`esp_crt_find_cert()` bisects the offset list and compares with

    memcmp(issuer, subject, MIN(issuer_len, subject_len))

If gen_crt_bundle.py's sort order does not agree with that comparison, the
bisection walks past the entry and returns NULL -- even though a linear scan
would find it.

Usage:
    python scripts/crt_binsearch_check.py <bundle> --issuer-from <chain.pem> --index 1
    python scripts/crt_binsearch_check.py <bundle> --name "Root YE"
"""

from __future__ import annotations

import argparse
import io
import sys

from cryptography import x509
from cryptography.x509.oid import NameOID

sys.path.insert(0, "scripts")
from crt_bundle_inspect import _load_blob  # noqa: E402


def load_chain(path: str) -> list[x509.Certificate]:
    with io.open(path, "rb") as fh:
        raw = fh.read()
    marker = b"-----END CERTIFICATE-----"
    out = []
    for chunk in raw.split(marker):
        if b"-----BEGIN CERTIFICATE-----" in chunk:
            body = chunk.split(b"-----BEGIN CERTIFICATE-----", 1)[1].strip()
            out.append(
                x509.load_pem_x509_certificate(
                    b"-----BEGIN CERTIFICATE-----\n" + body + b"\n" + marker
                )
            )
    return out


class Bundle:
    def __init__(self, blob: bytes) -> None:
        self.blob = blob
        off0 = int.from_bytes(blob[0:4], "little")
        self.count = off0 // 4
        self.names: list[bytes] = []
        self.offsets: list[int] = []
        for i in range(self.count):
            off = int.from_bytes(blob[4 * i : 4 * i + 4], "little")
            self.offsets.append(off)
            nlen = int.from_bytes(blob[off : off + 2], "little")
            self.names.append(blob[off + 4 : off + 4 + nlen])

    def binsearch(self, issuer: bytes) -> int | None:
        """Literal port of esp_crt_find_cert()'s bisection."""
        start, end = 0, self.count - 1
        middle = (start + end) // 2
        steps = []
        while start <= end:
            name = self.names[middle]
            n = min(len(issuer), len(name))
            a, b = issuer[:n], name[:n]
            cmp_res = (a > b) - (a < b)
            steps.append((middle, cmp_res))
            if cmp_res == 0:
                self._steps = steps
                return middle
            if cmp_res < 0:
                end = middle - 1
            else:
                start = middle + 1
            middle = (start + end) // 2
        self._steps = steps
        return None

    def linear(self, issuer: bytes) -> list[int]:
        hits = []
        for i, name in enumerate(self.names):
            n = min(len(issuer), len(name))
            if issuer[:n] == name[:n]:
                hits.append(i)
        return hits


def cn(der: bytes) -> str:
    idx = der.find(b"\x06\x03U\x04\x03")
    if idx < 0:
        return "<no CN>"
    pos = idx + 5
    if pos + 1 >= len(der):
        return "<no CN>"
    tag, ln = der[pos], der[pos + 1]
    start = pos + 2
    if ln & 0x80:
        nb = ln & 0x7F
        ln = int.from_bytes(der[start : start + nb], "big")
        start += nb
    return der[start : start + ln].decode("utf-8", "replace")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--issuer-from", help="PEM chain whose cert[index].issuer to test")
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--name", help="find a bundle entry by CN and test its own subject")
    args = ap.parse_args(argv[1:])

    b = Bundle(_load_blob(args.bundle))
    print(f"bundle: {args.bundle}")
    print(f"certs : {b.count}")

    # sanity: is the list actually monotonic under the same comparator?
    bad = []
    for i in range(1, b.count):
        left, right = b.names[i - 1], b.names[i]
        if (left > right) - (left < right) >= 0:
            bad.append(i)
    print(f"monotonic under memcmp: {not bad}"
          + (f"  (violations at {bad[:10]})" if bad else ""))

    if args.issuer_from:
        chain = load_chain(args.issuer_from)
        cert = chain[args.index]
        issuer = cert.issuer.public_bytes()
        label = f"{cn(cert.subject.public_bytes())} -> issuer {cn(issuer)}"
    elif args.name:
        idx = next((i for i, n in enumerate(b.names) if cn(n) == args.name), None)
        if idx is None:
            print(f"\n{args.name!r} not in bundle", file=sys.stderr)
            return 2
        issuer = b.names[idx]
        label = f"{args.name!r} self-subject"
    else:
        print("need --issuer-from or --name", file=sys.stderr)
        return 2

    print(f"\ntarget: {label}")
    print(f"issuer DER len: {len(issuer)}")

    bs = b.binsearch(issuer)
    lin = b.linear(issuer)

    print("\n--- bisection trace (index, cmp to issuer)")
    for m, c in getattr(b, "_steps", []):
        print(f"    middle={m:4d} cmp={c:+d}  CN={cn(b.names[m])!r}")

    print(f"\nbinary search result : {bs if bs is not None else 'NULL (MISS)'}")
    print(f"linear  scan  result : {lin if lin else 'none'}")

    if bs is None and lin:
        print("\n>>> BUG PATTERN: entry present but bisection misses it.")
        print("    The bundle's sort order disagrees with esp_crt_find_cert()'s")
        print("    MIN(len) memcmp, so the search walks past the entry.")
        return 1
    if bs is not None:
        print("\n>>> bisection finds the entry; name lookup is NOT the problem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
