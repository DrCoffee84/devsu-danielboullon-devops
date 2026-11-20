ARG PYTHON_VERSION=3.11
ARG GUNICORN_VERSION=23.0.0
ARG APP_UID=10001
ARG APP_GID=10001

# =============================================================================
# Stage 1: builder
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /build
COPY requirements.txt .

ARG GUNICORN_VERSION
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install -r requirements.txt "gunicorn==${GUNICORN_VERSION}"


# =============================================================================
# Stage 2: runtime
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="demo-devops-python" \
      org.opencontainers.image.description="API Django REST de usuarios (demo DevOps)" \
      org.opencontainers.image.authors="Daniel Boullon"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_PORT=8000 \
    DATABASE_NAME=/data/db.sqlite3 \
    GUNICORN_CMD_ARGS="--bind=0.0.0.0:8000 --workers=2 --threads=2 --timeout=30 --graceful-timeout=20 --worker-tmp-dir=/dev/shm --access-logfile=- --error-logfile=-"

ARG APP_UID
ARG APP_GID
RUN groupadd --system --gid "${APP_GID}" app \
 && useradd --system --uid "${APP_UID}" --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY manage.py ./
COPY demo/ ./demo/
COPY api/ ./api/

# El código queda de root (solo lectura). El usuario app solo escribe en /data,
# que es donde va SQLite cuando no hay DATABASE_URL (uso local con docker run).
RUN python -m compileall -q /app \
 && mkdir -p /data \
 && chown "${APP_UID}:${APP_GID}" /data

USER ${APP_UID}:${APP_GID}

EXPOSE 8000

# /healthz no toca la base: solo dice si el proceso responde.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,sys,urllib.request; port=os.environ.get('APP_PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=4).status == 200 else 1)"]

# Las migraciones no corren al arrancar: en Kubernetes las hace un initContainer
# y en local se corren a mano (ver README).
CMD ["gunicorn", "demo.wsgi:application"]