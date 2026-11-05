#!/bin/sh
# Prueba de restauración (S3-R4). NO toca el sistema en vivo: restaura el último respaldo en una base y una
# carpeta TEMPORALES y los compara con lo que hay en producción/staging. Ejecútala sin actividad de usuarios.
#
# Uso:  sh probar_restauracion.sh [CARPETA_DEL_RESPALDO]      (por defecto, el más reciente)
# Variables: PGHOST PGUSER PGDATABASE PGPASSWORD (el usuario debe poder crear bases), BACKUP_DIR (/backups), MEDIA_DIR (/media)
# Termina con código 0 si todo coincide y 1 si algo falla. La salida sirve como evidencia de la prueba.
set -u

DESTINO="${BACKUP_DIR:-/backups}"
MEDIA="${MEDIA_DIR:-/media}"
ORIGEN="${1:-}"
[ -n "$ORIGEN" ] || ORIGEN="$(find "$DESTINO" -mindepth 1 -maxdepth 1 -type d -name '[0-9]*_[0-9]*' | sort | tail -1)"
[ -n "$ORIGEN" ] && [ -d "$ORIGEN" ] || { echo "No hay respaldos en '$DESTINO'."; exit 2; }
VIVA="${PGDATABASE:?define PGDATABASE}"
PRUEBA="${VIVA}_prueba_restauracion"
TMP="$(mktemp -d)"
FALLAS=0
INICIO="$(date +%s)"

ok()    { echo "[OK   ] $1"; }
falla() { echo "[FALLA] $1"; FALLAS=$((FALLAS + 1)); }
limpiar() { psql -q -d postgres -c "DROP DATABASE IF EXISTS \"$PRUEBA\"" >/dev/null 2>&1; rm -rf "$TMP"; }
trap limpiar EXIT

echo "Prueba de restauración · respaldo: $ORIGEN"
[ -f "$ORIGEN/INFO.txt" ] && sed 's/^/        /' "$ORIGEN/INFO.txt"

# 1. Integridad del respaldo
if ( cd "$ORIGEN" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ); then ok "Integridad (SHA256) de los archivos del respaldo"; else falla "El respaldo está dañado (SHA256)"; fi

# 2. Restaurar la base en una base temporal
psql -q -d postgres -c "DROP DATABASE IF EXISTS \"$PRUEBA\"" -c "CREATE DATABASE \"$PRUEBA\"" >/dev/null 2>&1 \
  || { falla "No se pudo crear la base temporal '$PRUEBA' (¿el usuario tiene permiso CREATEDB?)"; exit 1; }
if pg_restore --no-owner --single-transaction -d "$PRUEBA" "$ORIGEN/base_de_datos.dump" 2>"$TMP/pg_restore.err"; then
  ok "Base de datos restaurada en '$PRUEBA'"
else
  falla "pg_restore falló: $(head -3 "$TMP/pg_restore.err" | tr '\n' ' ')"
fi

# 3. Comparar filas tabla por tabla contra la base en vivo
TABLAS="$(psql -d "$VIVA" -At -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")"
N=0; DIF=0; FILAS=0
for t in $TABLAS; do
  a="$(psql -d "$VIVA" -At -c "SELECT count(*) FROM \"$t\"")"
  b="$(psql -d "$PRUEBA" -At -c "SELECT count(*) FROM \"$t\"" 2>/dev/null)"; b="${b:-NO EXISTE}"
  N=$((N + 1)); FILAS=$((FILAS + a))
  if [ "$a" != "$b" ]; then DIF=$((DIF + 1)); echo "        diferencia en $t: en vivo=$a, respaldo=$b"; fi
done
if [ "$N" -eq 0 ]; then falla "La base en vivo no tiene tablas"; 
elif [ "$DIF" -eq 0 ]; then ok "$N tablas y $FILAS filas coinciden con la base en vivo"
else falla "$DIF de $N tablas difieren (si hubo actividad después del respaldo, repite la prueba sin usuarios conectados)"; fi

# 4. Restaurar archivos en una carpeta temporal y compararlos con los de verdad
mkdir "$TMP/media"
if tar -xzf "$ORIGEN/archivos_media.tar.gz" -C "$TMP/media" 2>"$TMP/tar.err"; then
  ok "Archivos extraídos del respaldo"
  if [ -d "$MEDIA" ]; then
    ( cd "$TMP/media" && find . -type f -exec sha256sum {} + | sort -k2 ) > "$TMP/restaurado.sha"
    ( cd "$MEDIA"     && find . -type f -exec sha256sum {} + | sort -k2 ) > "$TMP/vivo.sha"
    NR="$(grep -c . "$TMP/restaurado.sha" || true)"; NV="$(grep -c . "$TMP/vivo.sha" || true)"
    if diff "$TMP/vivo.sha" "$TMP/restaurado.sha" > "$TMP/dif.txt"; then ok "$NR archivos coinciden byte a byte con los de '$MEDIA'"
    else falla "Archivos distintos (en vivo: $NV, respaldo: $NR). Primeras diferencias: $(head -4 "$TMP/dif.txt" | tr '\n' ' ')"; fi
  else
    echo "[AVISO] '$MEDIA' no está montada: no se pudieron comparar los archivos con los originales"
  fi
else
  falla "No se pudo extraer archivos_media.tar.gz: $(head -2 "$TMP/tar.err" | tr '\n' ' ')"
fi

SEG=$(( $(date +%s) - INICIO ))
echo "Tiempo de la prueba: ${SEG} s (referencia para el tiempo de recuperación, RTO)"
if [ "$FALLAS" -eq 0 ]; then echo "RESULTADO: RESTAURACIÓN VERIFICADA"; exit 0; fi
echo "RESULTADO: FALLÓ ($FALLAS problema(s))"; exit 1
