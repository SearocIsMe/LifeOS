# Blind-test page image (B4.1 施测页) — uv venv + uvicorn 8000
#
# Build:
#   docker build -f deploy/blindtest/Dockerfile -t 172.128.0.11:30500/dtc/lifeos-blindtest-page:0.1.0 .
# Push:
#   docker push 172.128.0.11:30500/dtc/lifeos-blindtest-page:0.1.0
# Verify in-container:
#   docker run --rm 172.128.0.11:30500/dtc/lifeos-blindtest-page:0.1.0 curl -s 127.0.0.1:8000/blindtest
FROM python:3.12-slim

# frp/frp ffmpeg not needed here; system deps for httpx (none beyond std)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# uv (same manager as the project venv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# project source ( 施测页 + 逻辑层 + 素材 )
COPY deploy/blindtest/serve.py /app/serve.py
COPY src /app/src
COPY survey /app/survey
COPY survey/manifest.json /app/survey/manifest.json

# deps via uv (same manager as project venv; no pip)
RUN uv venv /app/.venv && uv pip install --python /app/.venv/bin/python \
    fastapi "uvicorn[standard]" httpx pydantic PyYAML

# 素材池与 ledgers 在运行时挂载（PVC /data）——镜像只含源与依赖
ENV LIFEOS_BT_OUT_DIR=/data/blindtest
ENV LIFEOS_BT_PORT=8000
ENV LIFEOS_BT_POOL_FILE=/data/LifeOS/reports/baselines

EXPOSE 8000

CMD ["/app/.venv/bin/python", "/app/serve.py"]
