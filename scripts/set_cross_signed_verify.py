"""Enable/disable CONFIG_MBEDTLS_CERTIFICATE_BUNDLE_CROSS_SIGNED_VERIFY.

Why this matters (docs/Deployment.md 附十三):
`sdkconfig` has `CROSS_SIGNED_VERIFY=y`, which switches ESP-IDF's CA bundle from
`esp_crt_verify_callback()` (a signature check) to `esp_crt_ca_cb_callback()`
(chain *construction*). It also suppresses `cacrt_local.pem` merging in
`components/mbedtls/CMakeLists.txt`.

Usage:
    python scripts/set_cross_signed_verify.py <sdkconfig> --enable
    python scripts/set_cross_signed_verify.py <sdkconfig> --disable
"""

from __future__ import annotations

import argparse
import io
import sys

KEY = "CONFIG_MBEDTLS_CERTIFICATE_BUNDLE_CROSS_SIGNED_VERIFY"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sdkconfig")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--enable", action="store_true")
    g.add_argument("--disable", action="store_true")
    args = ap.parse_args(argv[1:])

    with io.open(args.sdkconfig, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    want_on = args.enable
    found = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(KEY + "=") or stripped == f"# {KEY} is not set":
            found = True
            out.append(f"{KEY}=y" if want_on else f"# {KEY} is not set")
        else:
            out.append(line)

    if not found:
        out.append(f"{KEY}=y" if want_on else f"# {KEY} is not set")
        print(f"(appended: key was absent)")

    with io.open(args.sdkconfig, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")

    print(f"file : {args.sdkconfig}")
    print(f"state: {'ENABLED' if want_on else 'DISABLED'}")
    for line in out:
        if KEY in line:
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
