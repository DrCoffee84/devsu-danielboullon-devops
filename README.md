# devsu-danielboullon-devops

Ejercicio práctico DevOps de Devsu con la app `demo-devops-python` (Django + DRF): dockerizada, con pipeline CI/CD en GitHub Actions y desplegada en Kubernetes con Kustomize.

- Enunciado: [docs/enunciado.md](docs/enunciado.md)
- Cómo fui pensando cada decisión: [docs/razonamiento.md](docs/razonamiento.md)

## Estructura

```
app-python/            app Django + Dockerfile + Dockerfile.test
app-python-gitops/     manifiestos Kustomize (simula un repo gitops aparte)
  base/                Deployment, Service, HPA, PDB, ServiceAccount, ConfigMap
  overlays/local/      laboratorio en Docker Desktop (con Postgres)
  overlays/dev/        namespace app-python-dev
  overlays/prod/       namespace app-python-prod
.github/workflows/     ci.yml, cd.yml, _deploy.yml
docs/                  enunciado, razonamiento y capturas
```

## Diagramas

### Flujo CI/CD

```mermaid
flowchart LR
    dev[push a master] --> ci

    subgraph ci[CI · ci.yml]
        lint[Lint<br/>ruff] --> sast[SAST + secretos<br/>bandit, git grep]
        sast --> test[Tests + coverage ≥ 80%<br/>Dockerfile.test]
        test --> build[Docker build]
        build --> scan[Trivy<br/>CRITICAL]
        scan --> push[Push a GHCR<br/>tag = sha7]
    end

    push --> cd

    subgraph cd[CD · cd.yml]
        resolve[Resolver tag<br/>y verificar en GHCR] --> ddev[Deploy dev<br/>automático]
        ddev --> dprod[Deploy prod<br/>aprobación manual]
    end
```

### Despliegue en Kubernetes

```mermaid
flowchart LR
    user[Cliente] --> ing[Ingress nginx<br/>app-python.localhost]
    ing --> svc[Service<br/>ClusterIP :80]
    svc --> p1[Pod api :8000]
    svc --> p2[Pod api :8000]
    p1 --> db[(Postgres<br/>StatefulSet + PVC)]
    p2 --> db
    hpa[HPA<br/>CPU 70% / mem 80%] -.escala.-> deploy[Deployment]
    deploy --> p1
    deploy --> p2
    cm[ConfigMap] -.envFrom.-> p1
    sec[Secret] -.envFrom.-> p1
    pdb[PDB] -.protege.-> deploy
```

En dev/prod Postgres es una base gestionada (ej: RDS) y no vive en el cluster.

## App

Cambios mínimos sobre la app original, solo para que pueda correr en Kubernetes:

| Variable | Uso | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | clave de Django | obligatoria |
| `DJANGO_DEBUG` | modo debug | `False` |
| `DJANGO_ALLOWED_HOSTS` | hosts aceptados, separados por coma | `localhost,127.0.0.1` |
| `DATABASE_URL` | Postgres (`postgres://user:pass@host:5432/db`) | sin valor → SQLite |
| `DATABASE_NAME` | archivo SQLite si no hay `DATABASE_URL` | `/data/db.sqlite3` en la imagen |

| Endpoint | Para qué |
|---|---|
| `/healthz` | liveness: el proceso responde, no toca la base |
| `/readyz` | readiness: además hay conexión a la base (503 si no) |

Los dos los resuelve un middleware antes de validar `ALLOWED_HOSTS`, porque el kubelet manda la IP del pod como Host.

## Docker

[app-python/Dockerfile](app-python/Dockerfile)

- Multi-stage: `builder` instala dependencias en un venv; `runtime` es `python:3.11-slim-bookworm` y solo copia el venv y el código.
- `requirements.txt` se copia primero para aprovechar la caché de capas.
- Corre con gunicorn (no con `runserver`), en el puerto 8000.
- Usuario no-root (UID 10001). El código es de root y de solo lectura; solo `/data` es escribible.
- `HEALTHCHECK` contra `/healthz`.
- No corre migraciones al arrancar: en Kubernetes las hace un initContainer.

Los tests se corren con [app-python/Dockerfile.test](app-python/Dockerfile.test), así el pipeline no depende del lenguaje.

Correrlo local con SQLite en un volumen:

```bash
cd app-python
docker build -t app-python .
docker volume create app-data
docker run --rm -v app-data:/data -e DJANGO_SECRET_KEY=dev app-python python manage.py migrate
docker run --rm -p 8000:8000 -v app-data:/data -e DJANGO_SECRET_KEY=dev app-python
curl http://localhost:8000/healthz
```

## Pipeline

### CI — [ci.yml](.github/workflows/ci.yml)

Corre en cada push a `master`.

| Paso | Herramienta |
|---|---|
| Code build | `docker build` |
| Static code analysis | ruff (lint) y bandit (SAST) |
| Escaneo de secretos | chequeo de `.env` versionado y patrones con `git grep` |
| Unit tests + coverage | pytest + pytest-cov en `Dockerfile.test`, mínimo 80% |
| Vulnerability scan | Trivy, falla con CVE críticos |
| Build & push | GHCR, tag = short SHA (y `latest`) |

Los reportes (junit, coverage) quedan como artifact del run.

Corrida en verde: https://github.com/DrCoffee84/devsu-danielboullon-devops/actions/runs/44578179451

### CD — [cd.yml](.github/workflows/cd.yml) + [_deploy.yml](.github/workflows/_deploy.yml)

- **1 build → N deploys**: el CD nunca construye, promueve la misma imagen de dev a prod.
- Se dispara cuando el CI termina bien en `master`.
- dev se despliega automático; prod espera aprobación en el Environment `prod` de GitHub.
- Solo acepta tags SHA (nunca `latest`) y verifica que existan en GHCR.
- Pasos: `kustomize edit set image` en el overlay → render → `kubectl diff` → `apply` → `rollout status` → smoke test.
- Si el rollout falla, hace `kubectl rollout undo` automático.
- Rollback manual: `workflow_dispatch` con un tag anterior.
- Si el Environment no tiene `KUBE_CONFIG`, renderiza y sube los manifiestos como artifact, pero no aplica.

Detalle de configuración y rollback: [app-python-gitops/README.md](app-python-gitops/README.md)

## Kubernetes

| Recurso | Para qué |
|---|---|
| Namespace | uno por ambiente (`app-python-<ambiente>`), con Pod Security `restricted` |
| Deployment | 2 réplicas, rolling update sin indisponibilidad, initContainer de migraciones, probes `/healthz` y `/readyz`, no-root, rootfs de solo lectura |
| Service | ClusterIP, puerto 80 → 8000 |
| HPA | escalado horizontal por CPU y memoria (2–5 en base, 3–10 en prod) |
| PDB | asegura pods disponibles durante drains |
| ConfigMap | `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` |
| Secret | `DJANGO_SECRET_KEY`, `DATABASE_URL` (secretGenerator en local, ExternalSecret desde Vault en dev/prod) |
| Ingress | nginx; TLS con cert-manager en dev/prod |
| NetworkPolicy | deny-all y solo entra tráfico desde ingress-nginx (dev/prod) |
| ServiceAccount | sin token montado |
| StatefulSet `postgres` | solo en local, con PVC de 1Gi |

### Correrlo en local (Docker Desktop)

Requisitos: Kubernetes de Docker Desktop, ingress-nginx y metrics-server (para el HPA).

```bash
kubectl apply -f app-python-gitops/overlays/local/namespace.yaml
kubectl apply -k app-python-gitops/overlays/local
kubectl get pods -n app-python-local
curl http://app-python.localhost/api/users/
```

## URL pública

No hay. El despliegue se hizo en un cluster local de Docker Desktop, que el enunciado permite. La evidencia está en [docs/razonamiento.md](docs/razonamiento.md#3-kubernetes).

## Lo que no se cumplió y por qué

- **IaC en un proveedor público (punto extra)**: no se hizo. Prioricé la imagen, Kubernetes y el pipeline.
- **Deploy desde el pipeline a un cluster real**: el CD está completo, pero el cluster es local y GitHub Actions no llega a él. Sin `KUBE_CONFIG`, el job renderiza y valida sin aplicar.

## Para producción

- **DNS y TLS**: los hosts `*.example.com` de dev/prod son de ejemplo. Con un dominio real, cert-manager emite el certificado con Let's Encrypt (ya configurado en los Ingress).
- **Base de datos**: Postgres gestionado (ej: RDS) con backups y la URL en Vault.
- **Migraciones**: hoy corren en un initContainer. Con más tráfico las pasaría a un Job o a un paso del CD antes del rollout.
- **Permisos del CD**: un ServiceAccount con permisos acotados a su namespace, no el admin del cluster.
- **GitOps**: un controlador como Argo CD o Flux en lugar del `kubectl apply` del pipeline.
- **Observabilidad**: métricas, logs centralizados y alertas sobre `/readyz` y los errores 5xx.
