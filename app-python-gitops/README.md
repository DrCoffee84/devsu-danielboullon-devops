# app-python-gitops

Manifiestos Kustomize de `app-python` y cómo se operan.
En una empresa sería un repo aparte. Acá está junto para que sea fácil de evaluar.

```
base/             Deployment, Service, HPA, PDB, ServiceAccount, ConfigMap
overlays/local/   Docker Desktop: Postgres propio, secretGenerator, tag latest
overlays/dev/     namespace app-python-dev
overlays/prod/    namespace app-python-prod
```

## Diferencias entre ambientes

| | dev | prod |
|---|---|---|
| Réplicas (HPA) | 1–3 | 3–10 |
| PDB | `maxUnavailable: 1` | `minAvailable: 2` |
| Recursos | los de la base | más CPU y memoria |
| Spread | por nodo | por nodo y por zona |
| Secretos | Vault `app-python/dev` | Vault `app-python/prod` |
| TLS | Let's Encrypt staging | Let's Encrypt prod |

Igual en los dos: base gestionada, NetworkPolicy, mismo flujo de deploy.

Requisitos del cluster: ingress-nginx, cert-manager y External Secrets con un `ClusterSecretStore` llamado `vault-backend`.

## Cómo despliega el CD

```
push master → CI: build + push ghcr.io/drcoffee84/devsu-danielboullon-devops:<sha7>
            → CD: verificar imagen → deploy dev (auto) → deploy prod (aprobación)
```

Cada deploy:

1. `kustomize edit set image` en el overlay del ambiente.
2. Commit `chore(<env>): set image tag <sha7> [skip ci]` a `master`.
3. `kustomize build` y sube el manifiesto como artifact.
4. Si el Environment tiene `KUBE_CONFIG`: `kubectl apply` y `rollout status`.

- La base nunca se toca. Solo cambia el `newTag` del overlay.
- dev puede ir adelante de prod.
- Si el rollout no queda sano en 5 minutos, el job falla.

## Configurar los Environments

En GitHub → Settings → Environments:

- `dev`: sin reglas. Secret `KUBE_CONFIG` y variable `APP_URL`.
- `prod`: Required reviewers, solo rama `master`, secret `KUBE_CONFIG` y variable `APP_URL`.

`KUBE_CONFIG` es el kubeconfig en base64 (`base64 -w0 kubeconfig.yaml`).
Sin `KUBE_CONFIG` el CD hace todo menos aplicar.

## Qué versión corre en cada ambiente

Está en Git: el `newTag` de `overlays/<env>/kustomization.yaml`.

```bash
git log --oneline -- app-python-gitops/overlays/prod   # historial de deploys de prod
```

En el cluster:

```bash
kubectl get deploy app-python -n app-python-prod \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

## Rollback

Relanzar el CD con un tag anterior. Pasa por la misma aprobación y queda commiteado:

```bash
gh workflow run CD --ref master -f environment=prod -f image_tag=<sha7-anterior>
```

Emergencia, directo en el cluster:

```bash
kubectl rollout undo deployment/app-python -n app-python-prod
```

El próximo deploy vuelve a dejar el cluster como dice Git.

## Base de datos y migraciones

- La app usa `DATABASE_URL`. Local: StatefulSet de Postgres. dev/prod: base gestionada.
- Las migraciones las corre el initContainer `migrate` antes de cada pod.
- Tienen que ser compatibles hacia atrás: en un rollout conviven pods viejos y nuevos.

## Health checks

- `/healthz` (startup y liveness): el proceso responde. No toca la base.
- `/readyz` (readiness): además hay conexión a la base.
- Responden antes de validar `ALLOWED_HOSTS` → el kubelet llega con la IP del pod.
