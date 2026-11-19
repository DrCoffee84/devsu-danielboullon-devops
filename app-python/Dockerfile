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

# El código queda de root (solo lectura); el usuario app solo puede escribir
# en el directorio /app, que es donde SQLite crea db.sqlite3 y su journal.
RUN python -m compileall -q /app \
 && chown "${APP_UID}:${APP_GID}" /app

USER ${APP_UID}:${APP_GID}

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,sys,urllib.request; port=os.environ.get('APP_PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/api/users/', timeout=4).status == 200 else 1)"]

# Demo: aplica migraciones al arrancar y luego levanta gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn demo.wsgi:application"]

# Producción: las migraciones van aparte (Job), sin migrate acá.
# CMD ["gunicorn", "demo.wsgi:application"]