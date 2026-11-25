"""Diagnose why the ESP32 rejects a server certificate chain.

Companion to `docs/Deployment.md` 附十三. Two facts decide the outcome:

1. `esp_crt_bundle.c::esp_crt_verify_callback()` only inspects the **first
   untrusted link** of the chain and looks it up by *raw issuer name*
   (`esp_crt_find_cert(child->issuer_raw.p, ...)`). It never builds a chain to a
   root. So the decisive names are the issuer of the deepest untrusted
   intermediate, and the *subject* names present in `cacrt_all.pem`.
2. The bundle stores subject + public key only, so a match must come from a
   certificate whose subject name is byte-identical.

Usage:
    # 1) capture the served chain (Windows)
    (echo Q | openssl s_client -connect HOST:443 -servername HOST -showcerts -tls1_2) > chain.pem 2>nul
    # 2) analyse it against a CA bundle
    python scripts/tls_chain_probe.py reports/chain.pem \
        --bundle C:/esp-all/.espressif/v6.1/esp-idf/components/mbedtls/esp_crt_bundle/cacrt_all.pem
"""

from __future__ import annotations

import argparse
import io
import sys

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtensionOID, NameOID


def _cn(name: x509.Name) -> str:
    for oid in (NameOID.COMMON_NAME, NameOID.ORGANIZATION_NAME):
        vals = name.get_attributes_for_oid(oid)
        if vals:
            return vals[0].value
    return "<no CN>"


def load_pem_certs(raw: bytes) -> list[x509.Certificate]:
    marker = b"-----END CERTIFICATE-----"
    out: list[x509.Certificate] = []
    for chunk in raw.split(marker):
        if b"-----BEGIN CERTIFICATE-----" in chunk:
            pem = chunk.split(b"-----BEGIN CERTIFICATE-----", 1)[1]
            out.append(
                x509.load_pem_x509_certificate(
                    b"-----BEGIN CERTIFICATE-----" + pem + marker
                )
            )
    return out


def describe(cert: x509.Certificate, i: int, total: int) -> None:
    print(f"\n[{i}/{total - 1}] subject = {_cn(cert.subject)}")
    print(f"          issuer  = {_cn(cert.issuer)}")
    print(f"          self-signed = {cert.subject == cert.issuer}")
    print(
        f"          validity = {cert.not_valid_before_utc:%Y-%m-%d} .. "
        f"{cert.not_valid_after_utc:%Y-%m-%d}"
    )
    try:
        san = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        print(f"          SAN = {san.value.get_values_for_type(x509.DNSName)}")
    except x509.ExtensionNotFound:
        print("          SAN = <none>")
    try:
        bc = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
        print(f"          isCA = {bc.value.ca}")
    except x509.ExtensionNotFound:
        print("          isCA = <none>")
    key = cert.public_key()
    if isinstance(key, ec.EllipticCurvePublicKey):
        print(f"          pubkey = ECDSA {key.curve.name} ({key.key_size} bits)")
    elif isinstance(key, rsa.RSAPublicKey):
        print(f"          pubkey = RSA {key.key_size} bits")
    else:
        print(f"          pubkey = {type(key).__name__}")

    try:
        for ext in cert.extensions:
            oid = ext.oid.dotted_string
            if oid == "1.3.6.1.4.1.11129.2.4.2":
                print("          CT-SCT = present (harmless)")
            elif oid == "1.3.6.1.4.1.44947.1.1.1":
                print("          OCSP-Must-Staple = present")
    except Exception:  # pragma: no cover - extension parsing is best-effort
        pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chain", help="PEM file containing the server-sent chain")
    ap.add_argument("--bundle", help="CA bundle PEM (cacrt_all.pem)")
    ap.add_argument("--host", help="hostname to check against leaf SAN")
    args = ap.parse_args(argv[1:])

    with io.open(args.chain, "rb") as fh:
        chain = load_pem_certs(fh.read())

    if not chain:
        print("no certificates parsed from the chain file", file=sys.stderr)
        return 2

    print(f"served chain: {len(chain)} certificate(s)")
    for i, cert in enumerate(chain):
        describe(cert, i, len(chain))

    leaf = chain[0]
    if args.host:
        try:
            san = leaf.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            san = []
        print(f"\nhostname check: host={args.host} SAN={san} match={args.host in san}")

    last = chain[-1]
    print("\n--- chain termination")
    print(f"deepest certificate = {_cn(last.subject)}")
    print(f"its issuer          = {_cn(last.issuer)}")
    print(f"self-signed         = {last.subject == last.issuer}")

    if args.bundle:
        with io.open(args.bundle, "rb") as fh:
            bundle = load_pem_certs(fh.read())
        subjects = {c.subject.public_bytes(): _cn(c.subject) for c in bundle}
        print(f"\n--- bundle: {len(bundle)} certificates in {args.bundle}")

        # The ESP32 callback can only ever succeed on a bundle *subject* match.
        needed = {_cn(last.issuer): last.issuer.public_bytes()}
        if last.subject == last.issuer:
            needed.pop(_cn(last.issuer), None)
        # Any intermediate issuer is also a candidate lookup key.
        for cert in chain[1:]:
            needed.setdefault(_cn(cert.issuer), cert.issuer.public_bytes())

        missing = False
        for label, raw in needed.items():
            hit = raw in subjects
            print(f"    lookup {label!r:40s} -> {'FOUND' if hit else 'MISSING'}")
            missing |= not hit
        print("\n    verdict:", "would verify" if not missing else
              "cannot verify -> 'No matching trusted root certificate found'")

        print("\n--- Let's Encrypt anchors present in the bundle")
        for cn in ("ISRG Root X1", "ISRG Root X2", "ISRG Root X2 (cross)",
                   "ISRG Root X1 (cross)"):
            print(f"    {cn!r:28s} -> {'yes' if cn in subjects.values() else 'no'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
