FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    pkg-config \
    gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.ubuntu.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app/

RUN chmod +x /app/docker-entrypoint.sh \
    && chmod +x /app/docker-celery-worker.sh /app/docker-celery-beat.sh

# Informació del deploy (versió, commit i data del build) per al NavSidebar. La passa
# .github/workflows/imatges.yml; el context del build no porta .git ni la imatge té git.
# Sense args (build al servidor) només es registra la data del build.
ARG APP_VERSION=
ARG GIT_COMMIT=
ARG GIT_COMMIT_DATE=
ARG GIT_BRANCH=
ARG BUILD_DATE=
RUN APP_VERSION="$APP_VERSION" GIT_COMMIT="$GIT_COMMIT" GIT_COMMIT_DATE="$GIT_COMMIT_DATE" \
    GIT_BRANCH="$GIT_BRANCH" BUILD_DATE="$BUILD_DATE" \
    python -m customers.deploy_info /app/deploy_info.json

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["gunicorn", "customers.wsgi:application", "-c", "/app/gunicorn.conf.py"]


