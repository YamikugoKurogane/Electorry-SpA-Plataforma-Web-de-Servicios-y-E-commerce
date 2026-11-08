#!/bin/sh
# Respaldo diario de Electorry: base de datos (PostgreSQL) + archivos subidos (adjuntos de clientes y fotos de productos).
#
# Variables de entorno (todas con valor por defecto salvo la conexión a PostgreSQL):
#   PGHOST PGUSER PGDATABASE PGPASSWORD   conexión (las lee pg_dump)
#   BACKUP_DIR         carpeta donde se guardan los respaldos       (/backups)
#   MEDIA_DIR          carpeta de archivos subidos                  (/media)
#   RETENCION_DIAS     días que se conserva cada respaldo           (14; mínimo permitido: 7)
#   RESPALDOS_MINIMOS  cantidad que NUNCA se borra, aunque sea vieja (3)
#
# Cada respaldo es una carpeta AAAAMMDD_HHMMSS con: base_de_datos.dump, archivos_media.tar.gz, SHA256SUMS e INFO.txt.
# Si algo falla no queda un respaldo a medias y el script termina con error.
set -eu

DESTINO="${BACKUP_DIR:-/backups}"
MEDIA="${MEDIA_DIR:-/media}"
RETENCION="${RETENCION_DIAS:-14}"
MINIMOS="${RESPALDOS_MINIMOS:-3}"

case "$RETENCION$MINIMOS" in ''|*[!0-9]*) echo "ERROR: RETENCION_DIAS y RESPALDOS_MINIMOS deben ser números enteros"; exit 2;; esac
[ "$RETENCION" -ge 7 ] || { echo "ERROR: RETENCION_DIAS debe ser 7 o más (recibido: $RETENCION)"; exit 2; }
[ -d "$MEDIA" ] || { echo "ERROR: no existe la carpeta de archivos '$MEDIA'. Revisa MEDIA_DIR o el volumen montado."; exit 3; }

SELLO="$(date +%Y%m%d_%H%M%S)"
FINAL="$DESTINO/$SELLO"
TEMPORAL="$DESTINO/.en_curso_$SELLO"
mkdir -p "$DESTINO"
mkdir "$TEMPORAL"
trap 'rm -rf "$TEMPORAL"' EXIT

echo "[$(date '+%F %T')] Respaldo $SELLO"
echo " - base de datos..."
pg_dump --format=custom --no-owner --file="$TEMPORAL/base_de_datos.dump"
pg_restore --list "$TEMPORAL/base_de_datos.dump" > /dev/null     # el archivo debe poder leerse

echo " - archivos subidos..."
tar -czf "$TEMPORAL/archivos_media.tar.gz" -C "$MEDIA" .
tar -tzf "$TEMPORAL/archivos_media.tar.gz" > /dev/null

( cd "$TEMPORAL" && sha256sum base_de_datos.dump archivos_media.tar.gz > SHA256SUMS )
{
  echo "fecha=$(date '+%Y-%m-%dT%H:%M:%S%z')"
  echo "base_de_datos=${PGDATABASE:-}"
  echo "archivos_en_media=$(tar -tzf "$TEMPORAL/archivos_media.tar.gz" | grep -vc '/$' || true)"
} > "$TEMPORAL/INFO.txt"

mv "$TEMPORAL" "$FINAL"
trap - EXIT
date +%s > "$DESTINO/ULTIMO_OK"          # lo lee el healthcheck del servicio de respaldo
echo "Respaldo OK: $FINAL ($(du -sh "$FINAL" | cut -f1))"

# ---- Retención: borra lo más antiguo que RETENCION_DIAS, pero siempre conserva los últimos RESPALDOS_MINIMOS
LISTA="$(find "$DESTINO" -mindepth 1 -maxdepth 1 -type d -name '[0-9]*_[0-9]*' | sort)"
TOTAL="$(printf '%s\n' "$LISTA" | grep -c . || true)"
for viejo in $(find "$DESTINO" -mindepth 1 -maxdepth 1 -type d -name '[0-9]*_[0-9]*' -mtime +"$RETENCION" | sort); do
  [ "$TOTAL" -gt "$MINIMOS" ] || break
  rm -rf "$viejo"
  TOTAL=$((TOTAL - 1))
  echo "Retención: eliminado $viejo"
done
echo "Respaldos conservados: $TOTAL"
