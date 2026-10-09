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
