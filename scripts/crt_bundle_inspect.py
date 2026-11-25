"""Inspect the CA anchors actually compiled into the firmware's x509_crt_bundle.

The ESP-IDF bundle format (gen_crt_bundle.py) is:
    uint32 count            (number of certificates, first entry)
    uint32 offset[N]        (absolute offsets into the blob, 0-terminated)
    per cert: uint16 subj_len | uint16 key_len | subject DER | pubkey DER
There is no validity window and no issuer - only subject name + public key.

Usage:
    python scripts/crt_bundle_inspect.py <x509_crt_bundle file> [--want "ISRG Root X1"]
"""

from __future__ import annotations

import argparse
import io
import struct
import sys

from cryptography import x509
from cryptography.x509.oid import NameOID


_CN_OID = b"\x06\x03U\x04\x03"  # OID 2.5.4.3 (commonName)

# ASN.1 string tags that may carry a commonName value.
_STR_TAGS = {0x0C: "utf-8", 0x13: "ascii", 0x16: "ascii", 0x14: "latin-1"}


def _cn(der: bytes) -> str:
    """Best-effort CN extraction from a raw subject Name DER.

    ESP-IDF stores only the encoded Name (not a full certificate), so we walk
    the TLV ourselves instead of using `x509.Name.from_der` (not public API).
    """
    idx = der.find(_CN_OID)
    if idx < 0:
        return "<no CN>"
    pos = idx + len(_CN_OID)
    if pos + 1 >= len(der):
        return "<no CN>"
    tag, length = der[pos], der[pos + 1]
    start = pos + 2
    if length & 0x80:  # long form length
        nbytes = length & 0x7F
        length = int.from_bytes(der[start : start + nbytes], "big")
        start += nbytes
    raw = der[start : start + length]
    return raw.decode(_STR_TAGS.get(tag, "utf-8"), "replace")


def parse_bundle(blob: bytes) -> list[tuple[str, int]]:
    """Parse the ESP-IDF bundle format (see esp_crt_bundle.c).

    All integers are little-endian:
        uint32 offsets[N]   ; offsets[0] == N*4 == start of the first certificate
        per cert: uint16 name_len | uint16 key_len | name DER | pubkey DER
    """
    if len(blob) < 8:
        raise ValueError("blob too small to be a certificate bundle")
    first_off = int.from_bytes(blob[0:4], "little")
    if first_off < 4 or first_off % 4:
        raise ValueError(
            f"implausible bundle header: offsets[0]={first_off} "
            "(expected a multiple of 4)"
        )
    count = first_off // 4
    if first_off > len(blob):
        raise ValueError(f"bundle header larger than blob ({first_off} > {len(blob)})")

    out: list[tuple[str, int]] = []
    for i in range(count):
        off = int.from_bytes(blob[4 * i : 4 * i + 4], "little")
        if off + 4 > len(blob):
            break
        name_len = int.from_bytes(blob[off : off + 2], "little")
        key_len = int.from_bytes(blob[off + 2 : off + 4], "little")
        subject = blob[off + 4 : off + 4 + name_len]
        out.append((_cn(subject), key_len))
    return out


def _load_blob(path: str) -> bytes:
    """Accept either the raw bundle or the generated `x509_crt_bundle.S`."""
    with io.open(path, "rb") as fh:
        raw = fh.read()
    if raw.lstrip()[:1] != b"/" and raw.lstrip()[:1] != b"." and b".byte" not in raw[:2000]:
        return raw
    if b".byte" not in raw:
        return raw
    import re

    vals: list[int] = []
    for line in raw.splitlines():
        if not line.lstrip().startswith(b".byte"):
            continue
        for token in line.split(b".byte", 1)[1].split(b","):
            token = token.strip().decode("ascii", "ignore").replace("0x", "")
            token = token.split("/*")[0].strip()
            if not token:
                continue
            try:
                vals.append(int(token, 16))
            except ValueError:
                continue
    if len(vals) < 8:
        raise ValueError(f"could not recover bundle bytes from {path}")
    return bytes(vals)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", help="raw x509_crt_bundle or build/x509_crt_bundle.S")
    ap.add_argument("--want", action="append", default=[])
    args = ap.parse_args(argv[1:])

    blob = _load_blob(args.bundle)

    print(f"file      : {args.bundle}")
    print(f"size      : {len(blob)} bytes")
    entries = parse_bundle(blob)
    print(f"certificates actually compiled in: {len(entries)}")

    names = [n for n, _ in entries]
    print("\n--- first 5 subject CN")
    for n, klen in entries[:5]:
        print(f"    {n!r} (pubkey {klen} B)")
    print("\n--- ISRG anchors")
    for cn in ("ISRG Root X1", "ISRG Root X2"):
        print(f"    {cn!r:16s} -> {'PRESENT' if cn in names else 'ABSENT'}")

    if args.want:
        print("\n--- requested lookups")
        for w in args.want:
            print(f"    {w!r:40s} -> {'PRESENT' if w in names else 'ABSENT'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
