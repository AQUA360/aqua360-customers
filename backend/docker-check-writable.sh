#!/usr/bin/env bash
# Comprova que l'usuari del contenidor pot escriure als directoris que se li passen (i a tots els
# seus subdirectoris) abans d'arrencar res. La imatge no s'executa com a root: un volum que s'havia
# omplert quan el contenidor era root té carpetes de root on l'aplicació ja no pot desar, i l'error
# sortiria a mitja feina (collectstatic, un document, una gràfica). Aquí s'atura amb l'ordre que ho
# arregla.
set -euo pipefail

fail=0
for dir in "$@"; do
  [ -d "$dir" ] || continue
  # Si find no pot recórrer una carpeta (sense permís de lectura), la comprovació no és fiable:
  # també compta com a error, amb el missatge de find i la mateixa ordre per arreglar-ho.
  if ! bad=$(find "$dir" -type d ! -writable -print -quit); then
    echo "ERROR: no s'ha pogut comprovar tot $dir" >&2
    fail=1
    continue
  fi
  if [ -n "$bad" ]; then
    echo "ERROR: l'usuari $(id -un) ($(id -u):$(id -g)) no pot escriure a $bad" >&2
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "Els volums s'han de passar a l'usuari del contenidor. Al servidor, a la carpeta de l'stack:" >&2
  echo "  chown -R $(id -u):$(id -g) docker-data/media docker-data/static" >&2
  exit 1
fi
