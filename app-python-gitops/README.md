# app-python-gitops

Manifiestos Kustomize de `app-python` y cómo los despliega el CD.

```
base/                 Deployment, Service, HPA, PDB, ServiceAccount, ConfigMap
overlays/local/       laboratorio en Docker Desktop (secretGenerator, tag latest)
overlays/dev/         entorno dev  → namespace app-python-dev
overlays/prod/        entorno prod → namespace app-python-prod
```

| | dev | prod |
|---|---|---|
| Réplicas (HPA) | 1–3 | 3–10, scale-down estabilizado 5 min |
| PDB | `maxUnavailable: 1` | `minAvailable: 2` |
| Recursos | los de la base | 250m/256Mi → 1 CPU/512Mi |
| Spread | por nodo | por nodo y por zona |
| Secretos | ExternalSecret `app-python/dev` | ExternalSecret `app-python/prod` |
| Red | deny-all + solo ingress-nginx → 8000 | igual |
| TLS | cert-manager `letsencrypt-staging` | cert-manager `letsencrypt-prod` |

Requisitos en el cluster de dev/prod: ingress-nginx, cert-manager con los
ClusterIssuer nombrados, y External Secrets Operator con un
`ClusterSecretStore` llamado `vault-backend`. Los hosts `*.example.com` de los
Ingress son placeholders.

## Flujo de CD (1 build → N deploys)

```
push master → CI (build + push ghcr.io/drcoffee84/devsu-danielboullon-devops:<sha7>)
            → CD: resolve → deploy dev (auto) → deploy prod (espera aprobación)
```

- CI construye la imagen una sola vez. CD nunca construye: promueve el mismo
  tag (y por lo tanto el mismo digest) de dev a prod.
- Antes de aplicar, el CD corre `kustomize edit set image` **solo en el overlay
  del entorno** y en el runner (no commitea). La base no se toca.
- Cada entorno tiene su propio tag desplegado; dev puede ir adelante de prod.
- Nunca se usa `latest` en dev ni prod: el CD rechaza cualquier tag que no sea
  un SHA hex y verifica que exista en GHCR antes de desplegar.
- Si el rollout no queda sano en 5 min, el CD hace `kubectl rollout undo` y
  el job falla.

## Activar los aprobadores de prod

1. GitHub → repo → **Settings → Environments → New environment** → `dev`.
   Sin reglas de protección. Cargá el secret `KUBE_CONFIG` y, si querés, la variable `APP_URL`.
2. **New environment** → `prod`:
   - **Required reviewers**: agregá hasta 6 personas o equipos.
     (Opcional: **Prevent self-review** para que quien dispara no pueda aprobar.)
   - **Deployment branches and tags** → *Selected branches* → `master`.
   - Secret `KUBE_CONFIG` y variable `APP_URL` del cluster de prod.
3. `KUBE_CONFIG` es el kubeconfig en base64: `base64 -w0 kubeconfig-prod.yaml`.
   Usá un ServiceAccount con permisos acotados a su namespace, no el admin del cluster.

Sin `KUBE_CONFIG`, el CD renderiza, valida y sube los manifiestos como
artifact, pero **no aplica** y deja un warning. Sin Required reviewers, prod se
despliega sin pedir aprobación.

Si los paquetes de GHCR son privados, el cluster necesita un `imagePullSecret`
para `ghcr.io`.

## Qué tag está desplegado

```bash
# Imagen actual
kubectl get deploy app-python -n app-python-prod \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

# Historial: cada revisión guarda tag, actor y run en change-cause
kubectl rollout history deployment/app-python -n app-python-prod
```

Sin acceso al cluster: **Actions → CD** (el summary de cada run muestra imagen
y digest) o la página del environment en **Code → Deployments**.

Tags disponibles en GHCR:

```bash
gh api /users/drcoffee84/packages/container/devsu-danielboullon-devops/versions \
  --jq '.[].metadata.container.tags[]' | grep -v latest | head
```

## Rollback

Vuelve a desplegar una imagen que ya está en GHCR, sin reconstruirla:

```bash
gh workflow run CD --ref master -f environment=prod -f image_tag=<sha7-anterior>
```

O desde la UI: **Actions → CD → Run workflow** → `prod` + tag. Pasa por la
misma aprobación del Environment `prod`. Los manifiestos salen de `master`
actual y solo cambia la imagen.

Rollback de emergencia directo en el cluster (sin pipeline):

```bash
kubectl rollout undo deployment/app-python -n app-python-prod            # revisión anterior
kubectl rollout undo deployment/app-python -n app-python-prod --to-revision=<N>
```

El próximo deploy desde el CD vuelve a dejar el cluster como dice git más el tag elegido.

## Limitaciones conocidas de la app (no del despliegue)

- SQLite en `emptyDir`: cada pod tiene su propia base y se pierde al reiniciar.
  Para prod real hace falta una base externa (p. ej. Postgres/RDS).
- `DEBUG=True` y `ALLOWED_HOSTS=[]` están fijos en `settings.py`; por eso las
  probes y el Ingress fuerzan `Host: localhost`.
- La imagen corre `migrate` al arrancar; en prod las migraciones deberían ir en un Job aparte.
