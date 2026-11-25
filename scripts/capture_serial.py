"""Capture device serial output for N seconds and highlight TLS-verification lines.

Root-cause confirmation tool for docs/Deployment.md 附十三: after adding the missing
root to the firmware CA bundle, the serial log must show
`esp-x509-crt-bundle: Certificate validated` instead of
`No matching trusted root certificate found`.

Usage:
    python scripts/capture_serial.py --port COM10 --seconds 45 --out reports/serial_tls.log
"""

from __future__ import annotations

import argparse
import io
import sys
import time

try:
    import serial  # pyserial
except ImportError:
    print("pyserial is required:  pip install pyserial", file=sys.stderr)
    raise SystemExit(2)

KEYS = (
    "esp-x509-crt-bundle",
    "Certificate validated",
    "No matching trusted root",
    "signature verification failed",
    "mbedtls_ssl_handshake",
    "EspSsl",
    "Ota:",
    "Activation",
    "activating",
    "wifi",
    "Got IP",
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM10")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--out", default="reports/serial_tls.log")
    ap.add_argument("--reset", action="store_true",
                    help="toggle DTR/RTS to reboot the device before capturing")
    args = ap.parse_args(argv[1:])

    print(f"opening {args.port} @ {args.baud} for {args.seconds:.0f}s ...")
    lines: list[str] = []
    interesting: list[str] = []

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        if args.reset:
            # ESP32 auto-reset circuit: DTR/RTS sequence used by esptool --after hard_reset
            import time as _t
            ser.setDTR(False)
            ser.setRTS(True)
            _t.sleep(0.1)
            ser.setRTS(False)
            _t.sleep(0.1)
            ser.setDTR(True)
            _t.sleep(0.05)
            ser.setDTR(False)
            print("  device reset triggered")
            lines.append("### CAPTURE STARTS AFTER RESET ###")
            pending_reset = ser.read(4096)  # drain boot noise
            del pending_reset
        ser.reset_input_buffer()
        deadline = time.time() + args.seconds
        pending = b""
        while time.time() < deadline:
            chunk = ser.read(4096)
            if not chunk:
                continue
            pending += chunk
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode("utf-8", "replace").rstrip("\r")
                lines.append(line)
                if any(k in line for k in KEYS):
                    interesting.append(line)
                    print(f"  {line}")

    with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + ("\n" if lines else ""))

    print(f"\ncaptured {len(lines)} line(s) -> {args.out}")
    print(f"interesting lines: {len(interesting)}")

    joined = "\n".join(lines)
    print("\n=== verdict ===")
    if "Certificate validated" in joined:
        print("PASS  : bundle matched and signature verified")
    elif "No matching trusted root certificate found" in joined:
        print("FAIL  : still no matching root -> the added CA was not used")
    elif "signature verification failed" in joined:
        print("FAIL  : name matched but signature check failed")
    elif "mbedtls_ssl_handshake" in joined:
        print("FAIL  : handshake failed for another reason; see log")
    else:
        print("INCONCLUSIVE: no TLS attempt captured (device may be offline /")
        print("              still connecting). Try a longer --seconds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
