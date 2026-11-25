"""Extract one certificate (by index) from a PEM chain into its own PEM file.

Used by docs/Deployment.md 附十三 / 方案 A to pull the *root* out of a live
chain so it can be appended to ESP-IDF's `cacrt_local.pem`.

Usage:
    python scripts/extract_chain_cert.py in.pem out.pem --index 2
"""

from __future__ import annotations

import argparse
import io
import sys

from cryptography import x509
from cryptography.x509.oid import NameOID


def split_pems(raw: bytes) -> list[bytes]:
    marker = b"-----END CERTIFICATE-----"
    out = []
    for chunk in raw.split(marker):
        if b"-----BEGIN CERTIFICATE-----" not in chunk:
            continue
        body = chunk.split(b"-----BEGIN CERTIFICATE-----", 1)[1].strip()
        out.append(
            b"-----BEGIN CERTIFICATE-----\n"
            + body
            + b"\n-----END CERTIFICATE-----\n"
        )
    return out


def cn_of(name: x509.Name) -> str:
    vals = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return vals[0].value if vals else "<no CN>"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--index", type=int, required=True,
                    help="0-based certificate index within the chain")
    args = ap.parse_args(argv[1:])

    with io.open(args.src, "rb") as fh:
        pems = split_pems(fh.read())

    if not 0 <= args.index < len(pems):
        print(f"index {args.index} out of range (chain has {len(pems)})",
              file=sys.stderr)
        return 2

    pem = pems[args.index]
    cert = x509.load_pem_x509_certificate(pem)

    print(f"chain        : {len(pems)} cert(s)")
    print(f"extracting   : [{args.index}]")
    print(f"  subject    : {cn_of(cert.subject)}")
    print(f"  issuer     : {cn_of(cert.issuer)}")
    print(f"  self-signed: {cert.subject == cert.issuer}")
    print(f"  isCA       : {_is_ca(cert)}")

    if not _is_ca(cert):
        print("\nWARNING: this certificate is not marked CA=true; adding it to a")
        print("trust bundle is unlikely to be valid.", file=sys.stderr)

    with io.open(args.dst, "wb") as fh:
        fh.write(pem)
    print(f"\nwritten      : {args.dst}")
    return 0


def _is_ca(cert: x509.Certificate) -> bool:
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        return bool(bc.value.ca)
    except x509.ExtensionNotFound:
        return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
