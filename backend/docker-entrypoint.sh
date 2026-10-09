#!/usr/bin/env bash
set -euo pipefail

host="${DATABASE_HOST:-db}"
port="${DATABASE_PORT:-5432}"
user="${DATABASE_USER:-postgres}"

until pg_isready -h "$host" -p "$port" -U "$user" >/dev/null 2>&1; do
  echo "Esperant PostgreSQL ($host:$port)..."
  sleep 1
done

python manage.py fix_document_sign_migration_history
python manage.py migrate --noinput
python manage.py run_pending_scripts
if [ "${COLLECTSTATIC_ON_STARTUP:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi
python manage.py compilemessages
exec "$@"
