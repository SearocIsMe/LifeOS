"""Verify that ESP-IDF's merged local CA bundle parses and contains a given root.

Run after appending a root to `cacrt_local.pem` (docs/Deployment.md 附十三 / 方案 A)
and after every ESP-IDF upgrade, because `install.bat` overwrites that file.

Usage:
    python scripts/verify_local_bundle.py \
        --local C:/esp-all/.espressif/v6.1/esp-idf/components/mbedtls/esp_crt_bundle/cacrt_local.pem \
        --want "Root YE"
"""

from __future__ import annotations

import argparse
import io
import sys

from cryptography import x509
from cryptography.x509.oid import NameOID


def load_pems(raw: bytes) -> list[x509.Certificate]:
    marker = b"-----END CERTIFICATE-----"
    out = []
    for chunk in raw.split(marker):
        if b"-----BEGIN CERTIFICATE-----" not in chunk:
            continue
        body = chunk.split(b"-----BEGIN CERTIFICATE-----", 1)[1].strip()
        out.append(
            x509.load_pem_x509_certificate(
                b"-----BEGIN CERTIFICATE-----\n" + body + b"\n" + marker
            )
        )
    return out


def cn_of(name: x509.Name) -> str:
    vals = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return vals[0].value if vals else "<no CN>"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", required=True, help="cacrt_local.pem path")
    ap.add_argument("--want", action="append", default=[])
    args = ap.parse_args(argv[1:])

    with io.open(args.local, "rb") as fh:
        certs = load_pems(fh.read())

    print(f"file       : {args.local}")
    print(f"parsed certs: {len(certs)}")
    for i, c in enumerate(certs):
        print(f"  [{i}] CN={cn_of(c.subject)!r} "
              f"isCA={_is_ca(c)} self-signed={c.subject == c.issuer}")

    names = {cn_of(c.subject) for c in certs}
    rc = 0
    if args.want:
        print("\n--- requested")
        for w in args.want:
            hit = w in names
            print(f"  {w!r:20s} -> {'PRESENT' if hit else 'ABSENT'}")
            rc |= 0 if hit else 1

    print("\nReminder: this file is merged by gen_crt_bundle.py into the final")
    print("x509_crt_bundle. Verify the BUILD ARTIFACT too:")
    print("  python scripts/crt_bundle_inspect.py <build>/x509_crt_bundle.S --want \"Root YE\"")
    return rc


def _is_ca(c: x509.Certificate) -> bool:
    try:
        return bool(
            c.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        )
    except x509.ExtensionNotFound:
        return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
