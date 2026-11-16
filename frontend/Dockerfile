# Versió i commit per al NavSidebar quan la imatge es construeix al servidor (`docker compose
# build`, sense els build args de GitHub): el compose passa el `.git` del servidor com a context
# `gitdir` i aquí se'n treuen. Sense (GitHub Actions), `gitdir` és buit i el fitxer surt buit.
FROM scratch AS gitdir

FROM node:22-bookworm-slim AS gitinfo
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

FROM node:22-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG NUXT_PUBLIC_API_HOST=http://localhost:8000
ENV NUXT_PUBLIC_API_HOST=${NUXT_PUBLIC_API_HOST}

ARG NUXT_PUBLIC_ENV
ENV ENV=${NUXT_PUBLIC_ENV}

# El docker-compose dels clients ja envia NUXT_PUBLIC_DEFAULT_LOCALE com a build
# arg, pero fins ara el Dockerfile no el declarava i Docker el descartava en
# silenci: el build es quedava sense idioma i el defaultLocale del modul d'i18n
# quedava indefinit.
ARG NUXT_PUBLIC_DEFAULT_LOCALE=ca
ENV LANGUAGE=${NUXT_PUBLIC_DEFAULT_LOCALE}

ARG NUXT_EXTERNAL_GOT
ENV NUXT_EXTERNAL_GOT=${NUXT_EXTERNAL_GOT}

ARG VERIFACTU_ENABLED
ENV VERIFACTU_ENABLED=${VERIFACTU_ENABLED}

ARG NUXT_PUBLIC_EXPLOITATION_SITES
ENV NUXT_PUBLIC_EXPLOITATION_SITES=${NUXT_PUBLIC_EXPLOITATION_SITES}

# Nuxt 3.21 (Vite 7) supera els ~2,2 GB de heap que Node assigna per defecte en
# aquesta màquina i el build mor amb "heap out of memory". Amb 3.15 no hi arribava.
ENV NODE_OPTIONS=--max-old-space-size=4096

# Informació del deploy (versió, commit i data del build) per al NavSidebar, servida a
# /deploy-info.json. La passa .github/workflows/imatges.yml; el context del build no porta .git.
# S'escriu abans del build perquè Nitro només serveix els fitxers de public/ que hi troba en
# compilar. Sense args (build al servidor), la versió i el commit surten de l'etapa `gitinfo`.
ARG APP_VERSION=
ARG GIT_COMMIT=
ARG GIT_COMMIT_DATE=
ARG GIT_BRANCH=
ARG BUILD_DATE=
RUN --mount=type=bind,from=gitinfo,source=/deploy-git.env,target=/tmp/deploy-git.env \
    APP_VERSION="$APP_VERSION" GIT_COMMIT="$GIT_COMMIT" GIT_COMMIT_DATE="$GIT_COMMIT_DATE" \
    GIT_BRANCH="$GIT_BRANCH" BUILD_DATE="$BUILD_DATE" \
    node scripts/write-deploy-info.mjs public/deploy-info.json /tmp/deploy-git.env

RUN npm run build

FROM node:22-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000

COPY --from=builder /app/.output ./.output

# Tradueix els noms historics del .env als NUXT_PUBLIC_* que entén Nitro, de
# manera que una variable afegida al .env d'un client tingui efecte sense haver
# de tocar el seu docker-compose ni reconstruir la imatge. Veure el fitxer.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["node", ".output/server/index.mjs"]
