# Versió i commit per al NavSidebar quan la imatge es construeix al servidor (`docker compose
# build`, sense els build args de GitHub): el compose passa el `.git` del servidor com a context
# `gitdir` i aquí se'n treuen. Sense (GitHub Actions), `gitdir` és buit i el fitxer surt buit.
FROM scratch AS gitdir

FROM python:3.10-slim-bookworm AS gitinfo
# Si no es pot instal·lar git (sense accés als repositoris de Debian), el build continua: la
# imatge només porta la data del build, com abans.
RUN (apt-get update && apt-get install -y --no-install-recommends git) \
    || echo "AVÍS: no s'ha pogut instal·lar git; la imatge no portarà la versió"; \
    rm -rf /var/lib/apt/lists/*
# Una release (commit amb etiqueta) no porta branca, com les imatges de GitHub; un altre commit
# porta la darrera release i la branca (o HEAD si no n'hi ha cap que hi apunti).
RUN --mount=type=bind,from=gitdir,target=/repo.git \
    g() { git -c safe.directory='*' --git-dir=/repo.git "$@" 2>/dev/null; }; \
    : > /deploy-git.env; \
    if commit=$(g rev-parse --verify HEAD); then \
        if version=$(g describe --tags --exact-match HEAD); then branch=; \
        else \
            version=$(g describe --tags --abbrev=0 HEAD); \
            branch=$(g symbolic-ref --short -q HEAD \
                || g for-each-ref --points-at HEAD --format='%(refname:lstrip=3)' refs/remotes | grep -vx HEAD | head -n 1); \
            branch=${branch:-HEAD}; \
        fi; \
        printf 'APP_VERSION=%s\nGIT_COMMIT=%s\nGIT_COMMIT_DATE=%s\nGIT_BRANCH=%s\n' \
            "$version" "$commit" "$(g log -1 --format=%cI HEAD)" "$branch" > /deploy-git.env; \
    fi; \
    cat /deploy-git.env

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
# Sense args (build al servidor), la versió i el commit surten de l'etapa `gitinfo`.
ARG APP_VERSION=
ARG GIT_COMMIT=
ARG GIT_COMMIT_DATE=
ARG GIT_BRANCH=
ARG BUILD_DATE=
RUN --mount=type=bind,from=gitinfo,source=/deploy-git.env,target=/tmp/deploy-git.env \
    APP_VERSION="$APP_VERSION" GIT_COMMIT="$GIT_COMMIT" GIT_COMMIT_DATE="$GIT_COMMIT_DATE" \
    GIT_BRANCH="$GIT_BRANCH" BUILD_DATE="$BUILD_DATE" \
    python -m customers.deploy_info /app/deploy_info.json /tmp/deploy-git.env

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["gunicorn", "customers.wsgi:application", "-c", "/app/gunicorn.conf.py"]


