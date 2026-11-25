"""Switch ESP-IDF's default log verbosity between INFO and DEBUG.

Needed for docs/Deployment.md 附十三 第 0 步: only DEBUG makes
`esp_crt_bundle.c` print "N certificates in bundle" and "Certificate matched
with ...", which is what distinguishes a name-lookup failure from a signature
failure on the DEVICE (not on the host).

Usage:
    python scripts/set_log_level_debug.py <sdkconfig> --level debug
    python scripts/set_log_level_debug.py <sdkconfig> --level info
"""

from __future__ import annotations

import argparse
import io
import re
import sys

LEVELS = {"none": 0, "error": 1, "warn": 2, "info": 3, "debug": 4, "verbose": 5}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sdkconfig")
    ap.add_argument("--level", choices=sorted(LEVELS), required=True)
    args = ap.parse_args(argv[1:])

    with io.open(args.sdkconfig, encoding="utf-8") as fh:
        text = fh.read()

    target = args.level.upper()
    value = LEVELS[args.level]

    # Flip the choice booleans.
    for name in ("NONE", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE"):
        key = f"CONFIG_LOG_DEFAULT_LEVEL_{name}"
        if name == target:
            text = re.sub(rf"^# {key} is not set$", f"{key}=y", text, flags=re.M)
            text = re.sub(rf"^{key}=n$", f"{key}=y", text, flags=re.M)
        else:
            text = re.sub(rf"^{key}=y$", f"# {key} is not set", text, flags=re.M)

    text = re.sub(
        r"^CONFIG_LOG_DEFAULT_LEVEL=\d+$",
        f"CONFIG_LOG_DEFAULT_LEVEL={value}",
        text,
        flags=re.M,
    )

    with io.open(args.sdkconfig, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    print(f"{args.sdkconfig}: default log level -> {args.level} ({value})")
    for line in text.splitlines():
        if "LOG_DEFAULT_LEVEL" in line:
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
