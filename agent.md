# agent.md: contexto para las próximas iteraciones

Instrucciones para cualquier agente de IA que trabaje en este ejercicio. Leelo antes de tocar nada.

## Qué es esto

Ejercicio técnico de DevOps para una entrevista de trabajo (Devsu). El candidato es Daniel, DevOps. Repo público: `devsu-danielboullon-devops` (carpeta hermana de este archivo).

**El objetivo no es el software perfecto: es conseguir el trabajo.** Cada cosa que se agrega es algo que Daniel tiene que poder defender en la entrevista. Lo simple, claro y explicable siempre gana sobre lo completo.

> Ojo: `d:\Downloads\CLAUDE.md` es de **otro proyecto** ("Recorridos"). No aplica acá. Ignoralo.

## Reglas

1. **Simple.** Manifiestos simples donde solo cambia la imagen. Nada de parches raros, trucos ni herramientas nuevas sin preguntar (no Helm, no Argo CD, no escáneres extra).
2. **Humano.** `docs/razonamiento.md` está escrito por Daniel, en primera persona y en rioplatense con voseo. No lo reescribas. Si proponés texto, que sea en su voz, corto y marcado como propuesta para que él decida.
3. **No tocar código ni manifiestos.** Ya se tocaron bastante. Lo que no cierre se escribe como "asumo esto" en el README, corto, y la versión robusta va a `../posiblespreguntas.md`, que es donde Daniel se explaya.
4. **No hacer commit ni push** salvo que lo pida explícitamente. La rama principal es `master` (no `main`).
5. **La app es "del dev".** `app-python/` se toca lo mínimo (ya se tocaron settings, un middleware de health y tests). Lo de DevOps vive en `app-python-gitops/` y `.github/workflows/`.
6. **Docs = código.** Si cambia un workflow o un manifiesto, el README y el `app-python-gitops/README.md` tienen que decir lo mismo. Una contradicción entre docs y código es lo peor que le puede ver un corrector.
7. **No inventar comportamiento técnico.** Si no estás seguro, marcalo como "a verificar" en vez de afirmarlo.

## Mapa del repo

```
app-python/                  Django 4.2 + DRF, Dockerfile (multi-stage, no-root, gunicorn), Dockerfile.test
  demo/health.py             middleware /healthz (liveness) y /readyz (readiness, chequea la DB)
  demo/settings.py           DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS, DATABASE_URL (si falta, SQLite)
app-python-gitops/           simula un repo gitops aparte
  base/                      Deployment (initContainer migrate), Service, HPA, PDB, SA, ConfigMap
  overlays/local/            Docker Desktop: Postgres StatefulSet + secretGenerator, tag latest
  overlays/dev|prod/         ExternalSecret (Vault), NetworkPolicy, Ingress con cert-manager
.github/workflows/
  ci.yml                     ruff → bandit + secretos → tests/coverage → build → Trivy → push GHCR (tag sha7)
  cd.yml                     workflow_run del CI → resuelve tag → deploy dev → deploy prod (aprobación)
  _deploy.yml                reusable: set image en overlay → commit [skip ci] → render → apply si hay KUBE_CONFIG
docs/
  enunciado.md               el enunciado original
  razonamiento.md            bitácora de decisiones de Daniel (su voz)
  screenshots/
```

Fuera del repo (carpeta padre):

- `fino.md`: repaso contra el enunciado, inconsistencias y lo que falta, priorizado.
- `posiblespreguntas.md`: preguntas de entrevista con ideas de respuesta y la versión robusta de cada supuesto.

Este `agent.md` está en la raíz del repo (sin commitear).

## Decisiones tomadas (no relitigar)

- App elegida: Python.
- GitHub Actions + GHCR. Imagen pública, sin `imagePullSecret`.
- **1 build → N deploys**: el CD nunca construye, promueve el mismo tag de SHA.
- Trunk-based sobre `master`: dev automático, prod con Required reviewers del Environment.
- Kustomize con base y overlays; **un namespace por ambiente** (`app-python-<env>`), definido en el overlay, no en la base.
- GitOps: el CD **commitea** el `newTag` en el overlay, así Git es la fuente de verdad. Argo CD sería el siguiente paso, **sin auto-sync** (sync disparado por el pipeline).
- Health checks separados: liveness no toca la DB, readiness sí.
- Migraciones en initContainer (sabiendo que un Job sería mejor a escala).
- Postgres en el cluster solo en local; en dev/prod, base gestionada con `DATABASE_URL` desde Vault.
- IaC (punto extra): no hecha, justificada.

## Estado al 2026-11-23

Pendientes (detalle en `../fino.md`):

- [x] README reescrito corto (decisión → por qué), con "Dónde está cada cosa", "Cumplimiento" y "Supuestos". Sin las features que el CD no tiene.
- [x] `app-python-gitops/README.md` actualizado al flujo que commitea el tag.
- [x] Razonamiento: corregidos `[skip ci]` y `Dockerfile.test`; agregados `TODO: poner imagen`.
- [x] dev con `minReplicas: 1`: queda como supuesto en el README ("para ahorrar"). No se tocó el YAML.
- [x] Host de prod alineado: Ingress y `DJANGO_ALLOWED_HOSTS` usan `app-python.example.com`.
- [ ] Daniel saca las capturas de los `TODO: poner imagen` del razonamiento.
- [ ] Corrida completa CI → CD dev → aprobación → prod con los commits del bot, linkeada en los docs (los overlays todavía tienen `88dc298`).
- [ ] Evidencia del HPA escalando (captura con carga).
- [ ] Opcional: CI en `pull_request`; test de despliegue con kind en el runner.

## Cómo verificar cosas sin romper nada

```bash
# render de un overlay (no aplica nada)
kubectl kustomize app-python-gitops/overlays/local
kubectl kustomize app-python-gitops/overlays/prod

# laboratorio local (Docker Desktop + ingress-nginx + metrics-server)
kubectl apply -f app-python-gitops/overlays/local/namespace.yaml
kubectl apply -k app-python-gitops/overlays/local
kubectl get pods,hpa,pdb,ingress -n app-python-local
curl http://app-python.localhost/readyz
```

El entorno es Windows (PowerShell y Git Bash). En PowerShell usar `curl.exe`, no `curl`.

## Estilo de lo que escribas

- Español rioplatense con voseo, frases cortas, sin marketing.
- Explicá el porqué en una línea, no en un párrafo.
- Si proponés un cambio, decí cuántas líneas o archivos son. Si es más de un archivo nuevo, preguntá antes.
- Antes de proponer algo nuevo, preguntate: "¿Daniel lo puede explicar en 30 segundos en la entrevista?". Si no, no va.
