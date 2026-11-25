"""Print full DNs (all AVAs) of each certificate in a PEM chain.

Needed to identify *who* operates an unfamiliar CA (e.g. `YE2` / `Root YE`)
instead of guessing from the CN alone.

Usage:
    python scripts/chain_dn_dump.py reports/tokynflow_chain.pem
"""

from __future__ import annotations

import argparse
import io
import sys

from cryptography import x509


def load_chain(raw: bytes) -> list[x509.Certificate]:
    marker = b"-----END CERTIFICATE-----"
    out = []
    for chunk in raw.split(marker):
        if b"-----BEGIN CERTIFICATE-----" in chunk:
            body = chunk.split(b"-----BEGIN CERTIFICATE-----", 1)[1]
            out.append(
                x509.load_pem_x509_certificate(
                    b"-----BEGIN CERTIFICATE-----" + body + marker
                )
            )
    return out


def fmt(name: x509.Name) -> str:
    parts = []
    for ava in name:
        oid = ava.oid
        key = {
            "2.5.4.3": "CN",
            "2.5.4.6": "C",
            "2.5.4.7": "L",
            "2.5.4.8": "ST",
            "2.5.4.10": "O",
            "2.5.4.11": "OU",
            "1.2.840.113549.1.9.1": "emailAddress",
        }.get(oid.dotted_string, oid.dotted_string)
        parts.append(f"{key}={ava.value}")
    return ", ".join(parts)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chain")
    args = ap.parse_args(argv[1:])

    with io.open(args.chain, "rb") as fh:
        chain = load_chain(fh.read())

    print(f"chain certs: {len(chain)}")
    for i, c in enumerate(chain):
        print(f"\n[{i}]")
        print(f"  subject : {fmt(c.subject)}")
        print(f"  issuer  : {fmt(c.issuer)}")
        print(f"  serial  : {c.serial_number}")
        print(f"  ski     : {_ski(c)}")
        print(f"  aki     : {_aki(c)}")
    return 0


def _ski(c: x509.Certificate) -> str:
    try:
        ext = c.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
        return ext.value.digest.hex()
    except x509.ExtensionNotFound:
        return "<none>"


def _aki(c: x509.Certificate) -> str:
    try:
        ext = c.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
        return (ext.value.key_identifier or b"").hex() or "<empty>"
    except x509.ExtensionNotFound:
        return "<none>"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
