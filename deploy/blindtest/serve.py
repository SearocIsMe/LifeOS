#!/usr/bin/env python3
"""In-container server: uvicorn on LIFEOS_BT_PORT (8000), PVC out-dir."""
import os
import sys

sys.path.insert(0, "/app/src")

import uvicorn

from lifeos.dogfood.blindtest_app import create_blindtest_app

app = create_blindtest_app(
    out_dir=os.environ.get("LIFEOS_BT_OUT_DIR", "/data/blindtest"),
    pool_file=os.environ.get("LIFEOS_BT_POOL_FILE", "/data/LifeOS/reports/baselines"),
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("LIFEOS_BT_PORT", "8000")), log_level="info")
