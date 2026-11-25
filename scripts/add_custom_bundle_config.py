"""Add `CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE*` entries to sdkconfig.defaults.

Why this instead of `cacrt_local.pem`: `components/mbedtls/CMakeLists.txt` only
appends `cacrt_local.pem` when `CROSS_SIGNED_VERIFY` is *disabled*, and this
firmware enables it. `CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE` is the supported
hook and it does not depend on that option.

Usage:
    python scripts/add_custom_bundle_config.py <sdkconfig.defaults> [--path certs]
"""

from __future__ import annotations

import argparse
import io
import sys

MARKER = "# ---- extra trust roots for our server chain ----"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("defaults", help="path to sdkconfig.defaults")
    ap.add_argument("--path", default="certs",
                    help="bundle path relative to the PROJECT ROOT (default: certs)")
    args = ap.parse_args(argv[1:])

    with io.open(args.defaults, encoding="utf-8") as fh:
        text = fh.read()

    if "CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE" in text:
        print("already configured; nothing to do")
        return 0

    block = (
        f"\n{MARKER}\n"
        f"# certs/README.md explains why these roots are needed.\n"
        f"CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE=y\n"
        f'CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE_PATH="{args.path}"\n'
    )

    new_text = text.rstrip("\n") + "\n" + block
    with io.open(args.defaults, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)

    print(f"updated: {args.defaults}")
    print(f"  CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE=y")
    print(f'  CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE_PATH="{args.path}"')

    # echo the tail so the caller can eyeball the result
    print("\n--- tail")
    for line in new_text.splitlines()[-8:]:
        print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
