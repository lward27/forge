# Wave 1.1 — Platform Bootstrap

> Parent: [Master Plan](../master_plan.md)
> Goal: Forge API running in cluster, responding to health checks, connected to its own dedicated PostgreSQL.

---

## Overview

Stand up the Forge control plane as a FastAPI service deployed via ArgoCD on the existing cluster. This wave produces a working API skeleton with health checks, a dedicated PostgreSQL instance, and database connectivity — the foundation everything else builds on.

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Platform namespace | `forge-platform` | Isolates Forge from existing `apps-prod` workloads |
| Metadata database | Dedicated PG StatefulSet in `forge-platform` namespace | Full isolation from existing workloads; this PG also serves as the shared instance for tenant databases in Wave 1.3 |
| Helm chart style | Full chart (values.yaml + templates/) | Control plane will grow to need ConfigMaps, Secrets, RBAC — not a simple deployment.yaml |
| PG chart style | Separate Helm chart (`forge-postgresql`) | Decoupled lifecycle from the API; can be managed independently |
| Python version | 3.11 | Matches existing services |
| ORM | SQLModel | Matches existing services (finance_app_database_service) |
| Image registry | `registry.lucas.engineering/forge_platform:latest` | Follows existing naming convention |

---

## Tasks

### 1. Deploy Dedicated PostgreSQL for Forge

A standalone PostgreSQL StatefulSet in the `forge-platform` namespace. Modeled after the existing `charts/postgresql/` pattern but simplified (no TimescaleDB needed).

**Chart structure:**
```
forge/
├── charts/
│   └── forge-postgresql/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── statefulset.yaml
│           ├── service.yaml
│           └── secret.yaml
```

#### `Chart.yaml`
```yaml
apiVersion: v2
name: forge-postgresql
description: Dedicated PostgreSQL instance for the Forge platform
version: 0.1.0
appVersion: "17"
```

#### `values.yaml`
```yaml
forgePostgresql:
  name: forge-postgresql

  image:
    repository: postgres
    tag: "17"
    pullPolicy: IfNotPresent

  auth:
    existingSecret: "forge-postgresql-credentials"
    database: "forge_platform"

  service:
    type: ClusterIP
    port: 5432

  persistence:
    size: 8Gi
    storageClass: local-path

  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "512Mi"
```

#### `templates/secret.yaml`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ .Values.forgePostgresql.name }}-credentials
  labels:
    app.kubernetes.io/name: {{ .Values.forgePostgresql.name }}
type: Opaque
stringData:
  POSTGRES_PASSWORD: {{ .Values.forgePostgresql.auth.postgresPassword | quote }}
  POSTGRES_DB: {{ .Values.forgePostgresql.auth.database | quote }}
  POSTGRES_USER: "postgres"
  DATABASE_URL: "postgresql://postgres:{{ .Values.forgePostgresql.auth.postgresPassword }}@{{ .Values.forgePostgresql.name }}.{{ .Release.Namespace }}.svc.cluster.local:{{ .Values.forgePostgresql.service.port }}/{{ .Values.forgePostgresql.auth.database }}"
```

#### `templates/service.yaml`
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.forgePostgresql.name }}
  labels:
    app.kubernetes.io/name: {{ .Values.forgePostgresql.name }}
spec:
  type: {{ .Values.forgePostgresql.service.type }}
  selector:
    app.kubernetes.io/name: {{ .Values.forgePostgresql.name }}
  ports:
  - port: {{ .Values.forgePostgresql.service.port }}
    targetPort: 5432
    protocol: TCP
```

#### `templates/statefulset.yaml`
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ .Values.forgePostgresql.name }}
  labels:
    app.kubernetes.io/name: {{ .Values.forgePostgresql.name }}
spec:
  serviceName: {{ .Values.forgePostgresql.name }}
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Values.forgePostgresql.name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Values.forgePostgresql.name }}
    spec:
      containers:
      - name: postgresql
        image: "{{ .Values.forgePostgresql.image.repository }}:{{ .Values.forgePostgresql.image.tag }}"
        imagePullPolicy: {{ .Values.forgePostgresql.image.pullPolicy }}
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ .Values.forgePostgresql.name }}-credentials
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: {{ .Values.forgePostgresql.name }}-credentials
              key: POSTGRES_DB
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: pgdata
          mountPath: /var/lib/postgresql/data
        resources:
          {{- toYaml .Values.forgePostgresql.resources | nindent 10 }}
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          initialDelaySeconds: 15
          periodSeconds: 30
  volumeClaimTemplates:
  - metadata:
      name: pgdata
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: {{ .Values.forgePostgresql.persistence.storageClass }}
      resources:
        requests:
          storage: {{ .Values.forgePostgresql.persistence.size }}
```

**Internal DNS:** `forge-postgresql.forge-platform.svc.cluster.local:5432`

### 2. Scaffold the FastAPI Project

```
forge/
├── platform/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── setup.py
│   │   └── forge_platform/
│   │       ├── __init__.py
│   │       ├── __main__.py          # uvicorn entrypoint
│   │       ├── app.py               # FastAPI app creation + lifespan
│   │       ├── config.py            # Settings via pydantic-settings
│   │       ├── database.py          # SQLAlchemy engine, session factory
│   │       ├── models/
│   │       │   ├── __init__.py
│   │       │   └── base.py          # SQLModel base, metadata
│   │       └── routers/
│   │           ├── __init__.py
│   │           └── health.py        # GET /health, GET /ready
│   └── tests/
│       ├── __init__.py
│       └── test_health.py
```

**Key files:**

#### `__main__.py`
```python
import uvicorn

def main():
    uvicorn.run("forge_platform.app:app", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
```

#### `config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres@localhost:5432/forge_platform"
    app_name: str = "forge-platform"

settings = Settings()
```

#### `database.py`
```python
from sqlmodel import create_engine, Session
from forge_platform.config import settings

engine = create_engine(settings.database_url)

def get_session():
    with Session(engine) as session:
        yield session
```

#### `app.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel
from forge_platform.database import engine
from forge_platform.routers import health

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(title="Forge Platform", lifespan=lifespan)
app.include_router(health.router)
```

#### `routers/health.py`
```python
from fastapi import APIRouter, Depends
from sqlmodel import Session, text
from forge_platform.database import get_session

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/ready")
def ready(session: Session = Depends(get_session)):
    session.exec(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
```

#### `Dockerfile`
```dockerfile
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --user

COPY src/setup.py .
COPY src/forge_platform ./forge_platform
RUN pip install . --user

RUN opentelemetry-bootstrap -a install

EXPOSE 8000

ENTRYPOINT ["opentelemetry-instrument", "python", "-m", "forge_platform"]
```

#### `requirements.txt`
```
fastapi>=0.115.0
uvicorn>=0.30.0
sqlmodel>=0.0.22
psycopg2-binary>=2.9.9
pydantic-settings>=2.5.0
opentelemetry-api>=1.27.0
opentelemetry-sdk>=1.27.0
opentelemetry-exporter-otlp>=1.27.0
opentelemetry-instrumentation-fastapi>=0.48b0
```

#### `setup.py`
```python
from setuptools import setup, find_packages

setup(
    name="forge_platform",
    version="0.1.0",
    description="Forge Low-Code Platform Control Plane",
    author="Lucas Ward",
    packages=find_packages(),
)
```

### 3. Create the Forge Platform Helm Chart

```
forge/
├── charts/
│   └── forge-platform/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── deployment.yaml
│           ├── service.yaml
│           └── ingress.yaml
```

#### `Chart.yaml`
```yaml
apiVersion: v2
name: forge-platform
description: Forge Low-Code Platform Control Plane
version: 0.1.0
appVersion: "0.1.0"
```

#### `values.yaml`
```yaml
forgePlatform:
  name: forge-platform
  replicaCount: 1

  image:
    repository: registry.lucas.engineering/forge_platform
    tag: latest
    pullPolicy: Always

  service:
    type: ClusterIP
    port: 8080
    targetPort: 8000

  ingress:
    enabled: true
    className: nginx
    host: forge.lucas.engineering
    annotations:
      cert-manager.io/cluster-issuer: letsencrypt-prod

  env:
    DATABASE_URL secret sourced from `forge-platform-env`
    OTEL_SERVICE_NAME: "forge-platform"
    OTEL_EXPORTER_OTLP_ENDPOINT: "http://opentelemetry-collector.monitoring.svc.cluster.local:4317"
    OTEL_EXPORTER_OTLP_PROTOCOL: "grpc"
    OTEL_LOGS_EXPORTER: "otlp"
    OTEL_METRICS_EXPORTER: "otlp"
    OTEL_TRACES_EXPORTER: "otlp"
    OTEL_PYTHON_LOG_CORRELATION: "true"
    OTEL_RESOURCE_ATTRIBUTES: "deployment.environment=production,service.namespace=forge-platform"

  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "512Mi"
```

#### `templates/deployment.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.forgePlatform.name }}
  labels:
    app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
    app.kubernetes.io/instance: {{ .Release.Name }}
spec:
  replicas: {{ .Values.forgePlatform.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
        app.kubernetes.io/instance: {{ .Release.Name }}
    spec:
      containers:
      - name: {{ .Values.forgePlatform.name }}
        image: "{{ .Values.forgePlatform.image.repository }}:{{ .Values.forgePlatform.image.tag }}"
        imagePullPolicy: {{ .Values.forgePlatform.image.pullPolicy }}
        ports:
        - containerPort: {{ .Values.forgePlatform.service.targetPort }}
        env:
        {{- range $key, $value := .Values.forgePlatform.env }}
        - name: {{ $key }}
          value: {{ $value | quote }}
        {{- end }}
        resources:
          {{- toYaml .Values.forgePlatform.resources | nindent 10 }}
        livenessProbe:
          httpGet:
            path: /health
            port: {{ .Values.forgePlatform.service.targetPort }}
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: {{ .Values.forgePlatform.service.targetPort }}
          initialDelaySeconds: 5
          periodSeconds: 10
```

#### `templates/service.yaml`
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.forgePlatform.name }}
  labels:
    app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
spec:
  type: {{ .Values.forgePlatform.service.type }}
  selector:
    app.kubernetes.io/name: {{ .Values.forgePlatform.name }}
  ports:
  - port: {{ .Values.forgePlatform.service.port }}
    targetPort: {{ .Values.forgePlatform.service.targetPort }}
    protocol: TCP
```

#### `templates/ingress.yaml`
```yaml
{{- if .Values.forgePlatform.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Values.forgePlatform.name }}
  annotations:
    {{- toYaml .Values.forgePlatform.ingress.annotations | nindent 4 }}
spec:
  ingressClassName: {{ .Values.forgePlatform.ingress.className }}
  rules:
  - host: {{ .Values.forgePlatform.ingress.host }}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {{ .Values.forgePlatform.name }}
            port:
              number: {{ .Values.forgePlatform.service.port }}
  tls:
  - hosts:
    - {{ .Values.forgePlatform.ingress.host }}
    secretName: {{ .Values.forgePlatform.ingress.host | replace "." "-" }}-tls
{{- end }}
```

### 4. Register with ArgoCD (lucas_engineering repo)

Two ArgoCD Applications — one for PG, one for the API. Both deploy to `forge-platform` namespace.

**Add to `charts/root-app/values.yaml`:**
```yaml
apps:
  forge-postgresql:
    enabled: true
  forge-platform:
    enabled: true
```

**Create `charts/root-app/templates/forge-postgresql.yaml`:**
```yaml
{{- if (index .Values.apps "forge-postgresql").enabled }}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: forge-postgresql
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: <forge-repo-url-tbd>
    path: charts/forge-postgresql
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: forge-platform
  syncPolicy:
    automated:
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
{{- end }}
```

> **Note:** No `prune: true` on the PG app — we don't want accidental PVC deletion.

**Create `charts/root-app/templates/forge-platform.yaml`:**
```yaml
{{- if (index .Values.apps "forge-platform").enabled }}
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: forge-platform
  namespace: argocd
  finalizers:
  - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: <forge-repo-url-tbd>
    path: charts/forge-platform
    targetRevision: HEAD
  destination:
    server: https://kubernetes.default.svc
    namespace: forge-platform
  syncPolicy:
    automated:
      selfHeal: true
      prune: true
    syncOptions:
    - CreateNamespace=true
{{- end }}
```

> **Note:** The `repoURL` will be updated once the Forge git repo is created.

### 5. Add to Tekton CI

**Add to `charts/tekton-ci/values.yaml`:**
```yaml
services:
  forge-platform:
    enabled: true
    repoURL: <forge-repo-url-tbd>
    branch: main
    imageRef: registry.lucas.engineering/forge_platform:latest
    workspaceStorageSize: 1Gi
```

### 6. Initial Build & Deploy

```bash
# 1. Build the image (from linux VM)
ssh lucas_engineering
cd /path/to/forge
# Manual docker build until Tekton is wired up:
docker build -t registry.lucas.engineering/forge_platform:latest -f platform/Dockerfile platform/
docker push registry.lucas.engineering/forge_platform:latest

# 2. Push Helm charts to forge repo + ArgoCD app configs to lucas_engineering repo
#    ArgoCD will: create namespace → deploy PG StatefulSet → deploy Forge API

# 3. Verify PG is running
kubectl get pods -n forge-platform
# forge-postgresql-0   1/1   Running

# 4. Verify API
curl https://forge.lucas.engineering/health
curl https://forge.lucas.engineering/ready
```

---

## Deploy Order

ArgoCD will handle this automatically based on readiness probes, but the logical order is:

1. **Namespace** `forge-platform` (created by ArgoCD `CreateNamespace=true`)
2. **forge-postgresql** — StatefulSet + Service + Secret (PG needs to be ready before the API)
3. **forge-platform** — Deployment + Service + Ingress (readiness probe will fail until PG is up, then pass)

The Forge API's readiness probe (`/ready`) checks database connectivity, so Kubernetes won't route traffic to it until PG is accepting connections.

---

## Platform Metadata Schema (initial)

These tables are created automatically by SQLModel on startup. They'll be extended in later waves.

```sql
-- Wave 1.1: just the platform's own health tracking
-- No tenant tables yet — those come in Wave 1.2

-- Future tables (for reference):
-- tenant              (Wave 1.2)
-- tenant_resource     (Wave 1.2)
-- tenant_database     (Wave 1.3)
-- table_definition    (Wave 1.4)
-- column_definition   (Wave 1.4)
-- constraint_def      (Wave 1.4)
```

---

## Acceptance Criteria

- [ ] Dedicated PostgreSQL running in `forge-platform` namespace (`forge-postgresql-0` pod)
- [ ] `forge_platform` database created automatically by PG container
- [ ] Forge API image builds and pushes to `registry.lucas.engineering/forge_platform:latest`
- [ ] Helm charts deploy successfully to `forge-platform` namespace via ArgoCD
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `GET /ready` returns `{"status": "ready", "database": "connected"}`
- [ ] Liveness and readiness probes passing (pod stays Running)
- [ ] OpenTelemetry traces visible in monitoring stack
- [ ] Ingress accessible at `forge.lucas.engineering`

---

## Dependencies

- **Existing cluster** with ArgoCD, Tekton, nginx ingress, cert-manager
- **Container registry** at `registry.lucas.engineering`
- **DNS** entry for `forge.lucas.engineering` (or wildcard `*.lucas.engineering`)
- **Storage class** `local-path` available for PG PVC

---

## File Inventory

| # | File | Description |
|---|------|-------------|
| 1 | `charts/forge-postgresql/Chart.yaml` | PG Helm chart metadata |
| 2 | `charts/forge-postgresql/values.yaml` | PG config (image, auth, storage) |
| 3 | `charts/forge-postgresql/templates/statefulset.yaml` | PG StatefulSet |
| 4 | `charts/forge-postgresql/templates/service.yaml` | PG Service |
| 5 | `charts/forge-postgresql/templates/secret.yaml` | PG credentials Secret |
| 6 | `charts/forge-platform/Chart.yaml` | API Helm chart metadata |
| 7 | `charts/forge-platform/values.yaml` | API config (image, env, ingress) |
| 8 | `charts/forge-platform/templates/deployment.yaml` | API Deployment |
| 9 | `charts/forge-platform/templates/service.yaml` | API Service |
| 10 | `charts/forge-platform/templates/ingress.yaml` | API Ingress |
| 11 | `platform/Dockerfile` | Container image build |
| 12 | `platform/requirements.txt` | Python dependencies |
| 13 | `platform/src/setup.py` | Package setup |
| 14 | `platform/src/forge_platform/__init__.py` | Package init |
| 15 | `platform/src/forge_platform/__main__.py` | Uvicorn entrypoint |
| 16 | `platform/src/forge_platform/app.py` | FastAPI app + lifespan |
| 17 | `platform/src/forge_platform/config.py` | Pydantic settings |
| 18 | `platform/src/forge_platform/database.py` | Engine + session |
| 19 | `platform/src/forge_platform/models/__init__.py` | Models package |
| 20 | `platform/src/forge_platform/models/base.py` | SQLModel base |
| 21 | `platform/src/forge_platform/routers/__init__.py` | Routers package |
| 22 | `platform/src/forge_platform/routers/health.py` | Health endpoints |
| 23 | `platform/tests/__init__.py` | Tests package |
| 24 | `platform/tests/test_health.py` | Health endpoint tests |

**Plus in the lucas_engineering repo (ArgoCD wiring):**
| # | File | Description |
|---|------|-------------|
| 25 | `charts/root-app/templates/forge-postgresql.yaml` | ArgoCD Application for PG |
| 26 | `charts/root-app/templates/forge-platform.yaml` | ArgoCD Application for API |
| 27 | `charts/root-app/values.yaml` (update) | Enable both forge apps |
| 28 | `charts/tekton-ci/values.yaml` (update) | Add forge-platform build |

---

## Next Wave

→ [Wave 1.2 — Tenant Management](wave1_2_tenant_management.md)
