"""Compare chain issuer DER names against the firmware CA-bundle subject DER names.

`esp_crt_find_cert()` (ESP-IDF esp_crt_bundle.c) does:
    memcmp(issuer, esp_crt_get_name(cert), MIN(issuer_len, cert_name_len))
inside a **binary search** over a list sorted by DER name bytes. Therefore a
byte-level mismatch (different string types, different attribute order, extra
AVA) makes the lookup miss even when the CN looks identical.

Usage:
    python scripts/crt_name_compare.py <chain.pem> <x509_crt_bundle.S|bundle>
"""

from __future__ import annotations

import argparse
import io
import sys

from cryptography import x509
from cryptography.x509.oid import NameOID

sys.path.insert(0, "scripts")
from crt_bundle_inspect import _load_blob, parse_bundle  # noqa: E402


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


def cn_of(name: x509.Name) -> str:
    vals = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return vals[0].value if vals else "<no CN>"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chain")
    ap.add_argument("bundle")
    args = ap.parse_args(argv[1:])

    with io.open(args.chain, "rb") as fh:
        chain = load_chain(fh.read())

    blob = _load_blob(args.bundle)
    entries = parse_bundle(blob)  # (CN, key_len) in bundle order
    # Recover raw subject DER for each bundle entry, in order.
    first_off = int.from_bytes(blob[0:4], "little")
    count = first_off // 4
    bundle_names: list[bytes] = []
    for i in range(count):
        off = int.from_bytes(blob[4 * i : 4 * i + 4], "little")
        name_len = int.from_bytes(blob[off : off + 2], "little")
        bundle_names.append(blob[off + 4 : off + 4 + name_len])

    print(f"chain certs  : {len(chain)}")
    print(f"bundle certs : {len(bundle_names)}")

    sorted_by_der = bundle_names == sorted(bundle_names)
    print(f"bundle sorted by DER: {sorted_by_der}")
    if not sorted_by_der:
        print("  !! binary search is undefined for an unsorted list")

    print("\n--- exact DER name comparison (issuer vs bundle subject)")
    for i, cert in enumerate(chain):
        issuer_der = cert.issuer.public_bytes()
        label = f"{cn_of(cert.subject)} --issuer--> {cn_of(cert.issuer)}"
        exact = [j for j, b in enumerate(bundle_names) if b == issuer_der]
        prefix = [
            j
            for j, b in enumerate(bundle_names)
            if b[: min(len(b), len(issuer_der))]
            == issuer_der[: min(len(b), len(issuer_der))]
        ]
        print(f"\n  [{i}] {label}")
        print(f"      issuer DER len = {len(issuer_der)}")
        if exact:
            print(f"      EXACT byte match in bundle at index {exact}")
        elif prefix:
            print(f"      PREFIX-only match at index {prefix}")
            print("      (memcmp(x, y, MIN(len)) == 0 -> ESP-IDF accepts it)")
        else:
            print("      NO match -> esp_crt_find_cert() returns NULL")
            want = cn_of(cert.issuer)
            cands = [j for j, (n, _) in enumerate(entries) if n == want]
            if cands:
                for j in cands:
                    print(f"      bundle[{j}] CN={want!r} "
                          f"DER len={len(bundle_names[j])} "
                          f"-> content differs")
                    print(f"        issuer: {issuer_der[:48].hex()}...")
                    print(f"        bundle: {bundle_names[j][:48].hex()}...")
            else:
                print(f"      bundle has no subject CN={want!r} at all")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
