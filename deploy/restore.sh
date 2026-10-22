#!/bin/sh
# Restaura un respaldo. Uso: sh deploy/restore.sh /backups/electorry_YYYYMMDD_HHMMSS.dump
# Con PGHOST/PGUSER/PGDATABASE/PGPASSWORD definidos. DETENER la app antes de restaurar.
set -eu
[ $# -eq 1 ] || { echo "Uso: $0 archivo.dump"; exit 1; }
pg_restore --clean --if-exists --no-owner --dbname="$PGDATABASE" "$1"
echo "Restauración completada desde $1"
