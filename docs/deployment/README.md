# Secure Manufacturing RAG — Kubernetes Deployment Guide (Stage A: Local)

This guide covers containerizing the Secure Manufacturing RAG API and deploying
it to a local Kubernetes cluster (kind) using Helm. It corresponds to **Stage A**
of the deployment roadmap: local-only, zero cloud cost, and structured so the
same Helm chart carries forward to Stage B (AWS EKS).

## Architecture

```
client
  |  HTTP POST /query
  v
Ingress (nginx)
  |
  v
Service (ClusterIP)
  |
  v
Pod: secure-rag (FastAPI, non-root)
  |
  v
rag_query()  [unchanged business logic]
  |- Step 0: input validation + Bedrock Guardrails (INPUT)
  |- ChromaDB similarity search (PersistentVolumeClaim)
  |- Cohere Rerank
  |- ACL-aware access control (fail closed)
  |- Claude API
  |- Step 6: output filtering + Bedrock Guardrails (OUTPUT)
  v
JSON response
```

The FastAPI layer (`app.py`) is a thin HTTP wrapper. The existing `rag_query()`
function is untouched; containerization only adds the transport layer Kubernetes
needs (an HTTP endpoint for liveness/readiness probes, and a long-running process
instead of a one-shot CLI invocation).

## Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| Docker Desktop | 29.7.2+ | Must be running before any `docker` command |
| kind | 0.32.0+ | Local Kubernetes-in-Docker |
| Helm | 4.2.4+ | Chart templating and release management |
| kubectl | 1.36.1+ | Cluster interaction |

All versions above are pinned to what was verified during Stage A implementation.
Older Docker Desktop versions (e.g. 20.10.x) are known to work but were upgraded
during this project for unrelated reasons.

## Quick Start

```bash
# 1. Build the image
docker build -t secure-rag:local .

# 2. Create the kind cluster (ingress-ready labels/port mappings must be set at
#    creation time — they cannot be added afterwards)
kind create cluster --name secure-rag --config kind-config.yaml

# 3. Load the local image into the cluster (no registry required)
kind load docker-image secure-rag:local --name secure-rag

# 4. Create the secret holding API keys and AWS credentials
kubectl create secret generic secure-rag-secrets \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --from-literal=COHERE_API_KEY="$COHERE_API_KEY" \
  --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY"

# 5. Install the Ingress Controller (kind-specific manifest)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s

# 6. Install the Helm chart
helm install secure-rag ./secure-rag-chart \
  --set env.BEDROCK_GUARDRAIL_ID="$BEDROCK_GUARDRAIL_ID"

# 7. Verify
kubectl get pods,svc,ingress,pvc
curl -H "Host: secure-rag.local" http://localhost:8080/health
```

Expected output for the health check:
```json
{"status": "ok"}
```

## Configuration

All configurable values live in `secure-rag-chart/values.yaml`.

| Key | Default | Notes |
|---|---|---|
| `replicaCount` | `1` | Single replica for Stage A; HPA/multi-replica out of scope |
| `image.repository` | `secure-rag` | Becomes an ECR URI in Stage B |
| `image.tag` | `local` | |
| `image.pullPolicy` | `IfNotPresent` | Must stay `IfNotPresent` for kind-loaded images; becomes `Always` in Stage B |
| `service.type` | `ClusterIP` | |
| `service.port` / `service.targetPort` | `80` / `8000` | |
| `ingress.enabled` | `true` | |
| `ingress.className` | `nginx` | Becomes `alb` (or similar) in Stage B |
| `ingress.host` | `secure-rag.local` | Single host, string — not a list |
| `env.BEDROCK_GUARDRAIL_ID` | `""` | Passed via `--set` at install time, not committed |
| `env.BEDROCK_GUARDRAIL_VERSION` | `DRAFT` | |
| `env.AWS_REGION` | `us-east-1` | |
| `env.CHROMA_PERSIST_DIR` | `/data/chroma` | Matches the PVC mount path |
| `secretName` | `secure-rag-secrets` | Created manually in Stage A; via External Secrets in Stage B |
| `persistence.enabled` | `true` | |
| `persistence.size` | `1Gi` | |
| `resources.requests` / `.limits` | `100m/256Mi` / `500m/512Mi` | |

Required secrets (never committed, created via `kubectl create secret`):
`ANTHROPIC_API_KEY`, `COHERE_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

## Security Notes

- **Fail closed**: the FastAPI app checks for `ANTHROPIC_API_KEY`, `COHERE_API_KEY`,
  and `BEDROCK_GUARDRAIL_ID` at startup and refuses to boot if any are missing,
  rather than failing silently on the first request.
- **Non-root container**: the runtime image creates and runs as an unprivileged
  `appuser` (uid 1000). All directories the process writes to at runtime
  (`/app` for the audit log, `/data/chroma` for the vector store) are pre-created
  and chowned to `appuser` in the Dockerfile — `COPY --chown` alone only affects
  files copied at build time, not directories written to later.
- **Secrets are never baked into the image**: API keys and AWS credentials are
  injected via a Kubernetes `Secret` (`envFrom.secretRef`), not `values.yaml` or
  the container image. `.dockerignore` excludes `.env` and the local ChromaDB
  data directory from the build context.
- **Data is not baked into the image**: ChromaDB persists to a `PersistentVolumeClaim`
  rather than the container filesystem, so adding documents does not require an
  image rebuild.

## Known Limitation (Stage A)

The PVC created by `helm install` starts empty. The application uses
`get_or_create_collection` so it starts up safely either way, but a fresh
Stage A deployment will report "no accessible documents found" until the
existing indexed data is loaded into the PVC. Loading that data was out of
scope for Stage A (containerization and local K8s deployment); it is expected
to be addressed alongside the ingestion pipeline in a later stage.

## Roadmap

- **Stage B**: Deploy to AWS EKS. Requires: `--platform linux/amd64` rebuild
  (kind runs on the same arm64 Mac as the build; EKS nodes are x86), ECR for
  the image registry, `ingress.className: alb`, and a StorageClass swap
  (kind's `local-path` → EKS `gp2`/`gp3`).
- **Stage C**: Enterprise Deployment Guide.
- **Stage D**: CI/CD pipeline.

Explicitly out of scope for Stage A: authentication in front of the API, HPA,
multi-replica, and NetworkPolicy. Single replica is sufficient to validate the
container/Helm/Ingress path without expanding scope beyond what Day 1–6 cover.
