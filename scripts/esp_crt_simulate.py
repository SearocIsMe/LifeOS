"""Report, layer by layer, whether the firmware CA bundle can resolve each
certificate's issuer by DER subject name.

IMPORTANT SCOPE LIMIT
---------------------
This tool answers ONE question: "is there a bundle entry whose subject name is
byte-identical to this certificate's issuer name?" That is exactly what
`esp_crt_find_cert()` (ESP-IDF esp_crt_bundle.c) can see.

It deliberately does NOT claim to predict the final TLS verdict, because mbedtls
first tries to build a chain from the certificates the *server sent*. Whether the
CA callback (`esp_crt_ca_cb_callback`) is consulted for a given layer depends on
how many certificates the server actually transmits. Reasoning about that
without the device is not a substitute for a real handshake test.

Usage:
    python scripts/esp_crt_simulate.py <chain.pem> <x509_crt_bundle.S|bundle>
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


class Bundle:
    """Mirror of the firmware's bundle accessors. Note: NOT the binary search."""

    def __init__(self, blob: bytes) -> None:
        self.blob = blob
        first_off = int.from_bytes(blob[0:4], "little")
        self.count = first_off // 4
        self.names: list[bytes] = []
        for i in range(self.count):
            off = int.from_bytes(blob[4 * i : 4 * i + 4], "little")
            name_len = int.from_bytes(blob[off : off + 2], "little")
            self.names.append(blob[off + 4 : off + 4 + name_len])

    def issuer_resolvable(self, issuer_der: bytes) -> list[int]:
        """Indices whose stored subject name memcmp-equals this issuer name.

        `esp_crt_find_cert()` compares `MIN(len(issuer), len(subject))` bytes,
        so a shorter stored name is a hit whenever it is a prefix.
        """
        hits = []
        for i, name in enumerate(self.names):
            n = min(len(issuer_der), len(name))
            if issuer_der[:n] == name[:n]:
                hits.append(i)
        return hits


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chain")
    ap.add_argument("bundle")
    args = ap.parse_args(argv[1:])

    with io.open(args.chain, "rb") as fh:
        chain = load_chain(fh.read())
    bundle = Bundle(_load_blob(args.bundle))

    print(f"served chain : {len(chain)} cert(s)")
    print(f"bundle       : {bundle.count} cert(s)\n")
    print("For each layer: can the bundle resolve this certificate's issuer?\n")

    unresolved = 0
    for i, cert in enumerate(chain):
        subj, iss = cn_of(cert.subject), cn_of(cert.issuer)
        issuer_der = cert.issuer.public_bytes()
        in_chain = [
            j for j, other in enumerate(chain)
            if other is not cert and other.subject.public_bytes() == issuer_der
        ]
        hits = bundle.issuer_resolvable(issuer_der)

        print(f"[{i}] {subj}  --issuer-->  {iss}")
        print(f"      issuer DER len = {len(issuer_der)}")
        print(f"      resolved inside served chain at index: "
              f"{in_chain if in_chain else 'no'}")
        print(f"      resolvable by bundle CA callback      : "
              f"{hits if hits else 'NO'}")
        if not hits and not in_chain:
            unresolved += 1
            print("      => dead end here if mbedtls reaches this layer")
        print()

    print("--- summary")
    print(f"layers the served chain itself can resolve : "
          f"{len(chain) - unresolved}/{len(chain)}")
    if unresolved:
        print(f"layers that only the bundle could resolve, but cannot : {unresolved}")
        print("\nIf the server's transmitted chain is short enough that mbedtls")
        print("reaches such a layer, verification fails with")
        print("'No matching trusted root certificate found' / -0x3000.")
    else:
        print("\nEvery layer is resolvable by name. Do NOT read this as a PASS:")
        print("signature checking and chain construction still have to succeed,")
        print("and only a real handshake can confirm that.")

    print("\nGround truth remains the device serial log: look for")
    print("  'esp-x509-crt-bundle: Certificate validated'   -> success")
    print("  'No matching trusted root certificate found'  -> this report applies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
