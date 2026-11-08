#!/bin/sh
# Restaura un respaldo creado por backup.sh. ES DESTRUCTIVO: reemplaza los datos actuales.
#
# Uso:    CONFIRMAR=SI sh restore.sh CARPETA_DEL_RESPALDO [--solo-bd | --solo-archivos]
# Ej.:    CONFIRMAR=SI sh restore.sh /backups/20261102_030000
#
# Variables: PGHOST PGUSER PGDATABASE PGPASSWORD (destino), MEDIA_DIR (carpeta de archivos, /media).
# Antes de restaurar verifica la integridad del respaldo (SHA256). La base se restaura en UNA sola transacción:
# si algo falla, la base actual queda intacta.
set -eu

ORIGEN="${1:-}"
MODO="${2:-todo}"
MEDIA="${MEDIA_DIR:-/media}"

uso() { echo "Uso: CONFIRMAR=SI sh restore.sh CARPETA_DEL_RESPALDO [--solo-bd | --solo-archivos]"; exit 2; }
[ -n "$ORIGEN" ] && [ -d "$ORIGEN" ] || uso
case "$MODO" in todo|--solo-bd|--solo-archivos) ;; *) uso;; esac
[ "${CONFIRMAR:-}" = "SI" ] || { echo "Esto REEMPLAZA los datos actuales de '${PGDATABASE:-?}' y '$MEDIA'. Repite el comando con CONFIRMAR=SI."; exit 2; }

echo "Verificando integridad de $ORIGEN ..."
( cd "$ORIGEN" && sha256sum -c SHA256SUMS ) || { echo "ERROR: el respaldo está dañado. No se restauró nada."; exit 3; }

if [ "$MODO" != "--solo-archivos" ]; then
  echo "Restaurando la base de datos '${PGDATABASE:-}' ..."
  pg_restore --clean --if-exists --no-owner --single-transaction -d "${PGDATABASE:?define PGDATABASE}" "$ORIGEN/base_de_datos.dump"
fi

if [ "$MODO" != "--solo-bd" ]; then
  echo "Restaurando archivos en '$MEDIA' ..."
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  tar -xzf "$ORIGEN/archivos_media.tar.gz" -C "$TMP"          # si falla aquí, no se tocó nada
  mkdir -p "$MEDIA"
  find "$MEDIA" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  cp -a "$TMP"/. "$MEDIA"/
fi
echo "Restauración completada desde $ORIGEN"
