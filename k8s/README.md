# k8s/ - LifeOS cluster manifests (ADR-0004)

Gate 0 acceptance path since 2026-09-16 (HANDOVER §5-§7). docker-compose.yml is
demoted to a local dev fallback.

## Layout

| file | content |
|---|---|
| `10-namespace.yaml` | namespace `lifeos-dev` |
| `20-postgres.secret.example.yaml` | Secret TEMPLATE (placeholders) - real secret created out-of-band |
| `create-secrets.sh` | create/rotate `lifeos-postgres` + `lifeos-ai-stack` secrets (passwords generated in-shell, never printed) |
| `30-postgres.yaml` | postgres 16 + pgvector StatefulSet pinned to `aisi-w7` + headless/client Services |
| `40-dev-stack.yaml` | dev/inference ai-stack StatefulSet (`dtc-w1`, drift `dtc-w2`) + Services + NodePort 30793-30795 |
| `50-work-pvc.yaml` | RWX work volume `lifeos-work-rwx` (huawei-sc, 50Gi) |
| `kustomization.yaml` | `kubectl apply -k k8s/` (everything except Secrets) |

## Bootstrap (secrets BEFORE apply - postgres mounts lifeos-postgres)

```bash
kubectl apply -f k8s/10-namespace.yaml
bash k8s/create-secrets.sh          # random hex passwords, never printed/committed
kubectl apply -k k8s/
kubectl -n lifeos-dev wait --for=condition=ready pod -l app=lifeos-postgres --timeout=180s
# after any password exposure: bash k8s/create-secrets.sh --rotate
```

## Cluster conventions honored (from phases/phase-0/k8s-pod-example/)

- GPU resource name `nvidia.com/gpu.shared` (requests=limits), `runtimeClassName: nvidia`
- node placement via affinity (postgres: required `aisi-w7`; ai-stack: required
  `dtc-w1`+`dtc-w2`, preferred `dtc-w1`)
- containers run as root (`runAsUser/Group: 0`); images from internal registry
  `172.128.0.11:30500/dtc/...` (`IfNotPresent`)
- storage `huawei-sc` RWX; `emptyDir medium: Memory` 16Gi at `/dev/shm`
- Secret via Opaque + `stringData`, injected with `secretKeyRef` (names only in git)

## Verification

```bash
kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- nvidia-smi   # expect 3x H200
kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- bash -lc \
  "cd /data/LifeOS && alembic -c alembic.ini upgrade head && python -m pytest tests -q"
```
