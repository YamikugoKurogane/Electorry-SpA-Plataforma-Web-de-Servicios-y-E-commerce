#!/bin/sh
# Respaldo lógico de PostgreSQL. Uso: PGHOST/PGUSER/PGDATABASE/PGPASSWORD definidos.
set -eu
DESTINO="${BACKUP_DIR:-/backups}"
RETENCION="${RETENCION_DIAS:-14}"
mkdir -p "$DESTINO"
ARCHIVO="$DESTINO/electorry_$(date +%Y%m%d_%H%M%S).dump"
pg_dump --format=custom --no-owner --file="$ARCHIVO"
# Verifica que el archivo sea legible antes de dar el respaldo por válido
pg_restore --list "$ARCHIVO" > /dev/null
echo "Respaldo OK: $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))"
find "$DESTINO" -name 'electorry_*.dump' -mtime +"$RETENCION" -delete
