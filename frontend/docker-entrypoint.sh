#!/bin/sh
# Tradueix els noms "historics" de variables als que Nitro entén.
#
# Nitro només sobreescriu `runtimeConfig.public.<clau>` amb una variable
# anomenada `NUXT_PUBLIC_<CLAU>`. Els `.env` dels clients, en canvi, fan servir
# els noms que llegeix `nuxt.config.ts` en temps de compilació (`LANGUAGE`,
# `ENV`, `NUXT_EXTERNAL_GOT`...). Sense aquesta traducció, una variable afegida
# al `.env` arriba al contenidor i no té cap efecte: ni el build la veu (no és
# un build arg) ni Nitro la reconeix (nom diferent).
#
# Només s'omple el que no vingui ja definit, de manera que un `NUXT_PUBLIC_*`
# posat explícitament al docker-compose sempre mana.

set -eu

fill() {
  target="$1"
  value="$2"
  eval "current=\${$target-}"
  if [ -z "$current" ] && [ -n "$value" ]; then
    export "$target=$value"
  fi
}

fill NUXT_PUBLIC_DEFAULT_LOCALE      "${LANGUAGE-}"
fill NUXT_PUBLIC_I18N_DEFAULT_LOCALE "${NUXT_PUBLIC_DEFAULT_LOCALE-}"
fill NUXT_PUBLIC_ENV                 "${ENV-}"
fill NUXT_PUBLIC_EXTERNAL_GOT        "${NUXT_EXTERNAL_GOT-}"

# `verifactuEnabled` és un booleà al nuxt.config (`VERIFACTU_ENABLED === 'True'`)
# i Nitro espera `true`/`false` en minúscula, així que aquí es normalitza.
if [ -z "${NUXT_PUBLIC_VERIFACTU_ENABLED-}" ] && [ -n "${VERIFACTU_ENABLED-}" ]; then
  case "$VERIFACTU_ENABLED" in
    True|true|TRUE|1) export NUXT_PUBLIC_VERIFACTU_ENABLED=true ;;
    *)                export NUXT_PUBLIC_VERIFACTU_ENABLED=false ;;
  esac
fi

exec "$@"
