"""Decide whether a reissued certificate would be trusted by this firmware.

Checks the CA *brands* commonly sold by Chinese cloud CAs (Aliyun/Tencent) against
the roots actually compiled into the device's CA bundle.

Rationale: `esp_crt_find_cert()` matches by DER subject name only. Key type
(RSA/ECDSA) is irrelevant to the lookup; what matters is that the chain's
top-most issuer exists in the bundle byte-for-byte.

Usage:
    python scripts/cert_brand_matrix.py <build/x509_crt_bundle.S>
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "scripts")
from crt_bundle_inspect import _load_blob, parse_bundle  # noqa: E402

# Root CNs per brand. A brand is only "usable" if its root is byte-identical in
# the bundle (CN match is a necessary but not sufficient condition).
BRANDS: dict[str, list[str]] = {
    "DigiCert": [
        "DigiCert Global Root CA",
        "DigiCert Global Root G2",
        "DigiCert Global Root G3",
        "DigiCert High Assurance EV Root CA",
        "DigiCert Trusted Root G4",
        "DigiCert TLS RSA4096 Root G5",
        "DigiCert TLS ECC P384 Root G5",
    ],
    "GeoTrust": ["GeoTrust Global CA", "GeoTrust Primary Certification Authority"],
    "GlobalSign": [
        "GlobalSign Root CA",
        "GlobalSign Root R3",
        "GlobalSign Root R46",
        "GlobalSign Root E46",
    ],
    "Sectigo (USERTrust)": [
        "USERTrust RSA Certification Authority",
        "USERTrust ECC Certification Authority",
        "Sectigo Public Server Authentication Root R46",
        "Sectigo Public Server Authentication Root E46",
        "AAA Certificate Services",
    ],
    "Entrust": [
        "Entrust Root Certification Authority - G2",
        "Entrust Root Certification Authority - EC1",
    ],
    "Certum": ["Certum Trusted Network CA", "Certum Trusted Network CA 2"],
    "Google Trust Services": [
        "GTS Root R1",
        "GTS Root R2",
        "GTS Root R3",
        "GTS Root R4",
    ],
    "Amazon": ["Amazon Root CA 1", "Amazon Root CA 2", "Amazon Root CA 3", "Amazon Root CA 4"],
    "Let's Encrypt (ISRG)": [
        "ISRG Root X1",
        "ISRG Root X2",
        "Root YE",
        "Root YR",
    ],
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    args = ap.parse_args(argv[1:])

    blob = _load_blob(args.bundle)
    present = {n for n, _ in parse_bundle(blob)}
    print(f"bundle: {args.bundle}")
    print(f"compiled certificates: {len(present)}\n")

    for brand, roots in BRANDS.items():
        hits = [r for r in roots if r in present]
        misses = [r for r in roots if r not in present]
        verdict = "USABLE" if hits else "NOT USABLE"
        print(f"{brand:24s} {verdict}")
        for r in hits:
            print(f"    + {r}")
        for r in misses:
            print(f"    - {r}  (absent)")

    print("\nNOTE: a present root is necessary but not sufficient. After any")
    print("reissue, verify the real chain with:")
    print("    python scripts/crt_name_compare.py new_chain.pem <bundle>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
