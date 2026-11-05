# Respaldos y restauración

Tareas S3-R3 (respaldo diario ampliado) y S3-R4 (prueba de restauración en staging).

## 1. Qué se respalda

| Qué | Dónde vive | Se respalda como |
|---|---|---|
| Base de datos (usuarios, solicitudes, cotizaciones, ventas, pagos, auditoría) | PostgreSQL | `base_de_datos.dump` (formato de `pg_dump`) |
| Archivos adjuntos de las solicitudes y fotos de productos | Volumen `media` (`/media`) | `archivos_media.tar.gz` |

Cada respaldo es una carpeta `AAAAMMDD_HHMMSS` con esos dos archivos más `SHA256SUMS` (integridad) e `INFO.txt` (fecha y conteos).

## 2. Cómo funciona

- El servicio `respaldo` de `docker-compose.yml` ejecuta `deploy/backup.sh` al iniciar y luego **cada 24 horas**.
- **Retención:** `RETENCION_DIAS` (por defecto **14**; el script rechaza valores menores que **7**). Además siempre se conservan los últimos 3 respaldos (`RESPALDOS_MINIMOS`), aunque sean más viejos, para que una falla prolongada no deje al sistema sin ninguno.
- **Verificación automática:** al terminar cada respaldo se comprueba que el volcado se pueda leer (`pg_restore --list`) y que el `.tar.gz` se pueda recorrer, y se guardan las sumas SHA256.
- **Sin respaldos a medias:** si algo falla, se elimina la carpeta temporal y el script termina con error (el servicio registra «ATENCION: EL RESPALDO FALLO»).
- **Monitoreo:** el servicio `respaldo` queda `unhealthy` si el último respaldo exitoso tiene más de 26 horas (`docker ps` o `docker compose ps`).
- Los archivos de `media` se montan **solo lectura** en el servicio de respaldo: un error en el script no puede borrarlos.

Variables (en `docker-compose.yml` o el entorno): `RETENCION_DIAS`, `RESPALDOS_MINIMOS`, `BACKUP_DIR`, `MEDIA_DIR` y la conexión `PGHOST`, `PGUSER`, `PGDATABASE`, `PGPASSWORD`.

## 3. Operación diaria

```bash
docker compose ps                         # el servicio «respaldo» debe estar healthy
docker compose logs --tail 30 respaldo    # resultado del último respaldo
docker compose exec respaldo ls -1 /backups          # lista de respaldos disponibles
docker compose exec respaldo sh /deploy/backup.sh    # respaldo manual inmediato (p. ej. antes de actualizar)
```

## 4. IMPORTANTE: los respaldos no deben vivir solo en el servidor

El volumen `backups` está en el **mismo servidor** que la aplicación. Si se pierde el servidor o el disco, se pierden también los respaldos. Copia periódicamente (al menos semanal) a otro lugar: otro servidor, almacenamiento en la nube o un disco externo.

```bash
docker volume ls | grep backups        # anota el nombre exacto del volumen
docker run --rm -v NOMBRE_DEL_VOLUMEN:/b -v "$PWD":/salida alpine tar czf /salida/respaldos.tgz -C /b .
```

## 5. Restaurar

**Restaurar es destructivo:** reemplaza los datos actuales. Hazlo siempre con la aplicación detenida.

```bash
docker compose stop web correo nginx
docker compose exec respaldo ls -1 /backups                                   # elige la carpeta
docker compose run --rm -e CONFIRMAR=SI restauracion /backups/AAAAMMDD_HHMMSS
docker compose start web correo nginx
```

Variantes: agregar `--solo-bd` (solo la base) o `--solo-archivos` (solo los archivos) al final del comando.

Garantías del procedimiento:
- Exige `CONFIRMAR=SI`; sin eso se niega.
- Verifica la integridad (SHA256) **antes** de tocar nada: un respaldo dañado no se restaura.
- La base se restaura en **una sola transacción**: si algo falla, la base actual queda intacta.
- Los archivos se extraen primero a una carpeta temporal; solo si eso funciona se reemplaza el contenido de `media`.

## 6. Prueba de restauración en staging (S3-R4)

La prueba **no toca el sistema en vivo**: restaura el último respaldo en una base y una carpeta temporales y los compara con los reales.

Antes: que el staging tenga datos reales de prueba **y al menos un adjunto subido** (crear una solicitud con una foto), y que no haya usuarios conectados.

1. Hacer un respaldo manual: `docker compose exec respaldo sh /deploy/backup.sh` y comprobar que termina con `Respaldo OK`.
2. Ejecutar la prueba: `docker compose run --rm prueba_restauracion`
3. Resultado esperado (cada línea debe ser `[OK]`):
   ```
   [OK   ] Integridad (SHA256) de los archivos del respaldo
   [OK   ] Base de datos restaurada en '..._prueba_restauracion'
   [OK   ] N tablas y M filas coinciden con la base en vivo
   [OK   ] Archivos extraídos del respaldo
   [OK   ] K archivos coinciden byte a byte con los de '/media'
   RESULTADO: RESTAURACIÓN VERIFICADA
   ```
4. **Guardar la salida completa** como evidencia (captura o archivo de texto).
5. (Recomendado, una vez) Prueba de restauración real en un entorno aparte o tras un respaldo manual previo, siguiendo la sección 5, y comprobar en la aplicación que se ven las solicitudes, los adjuntos y las fotos.

Si falla alguna línea, la salida indica cuál. Una diferencia entre la base en vivo y el respaldo suele deberse a actividad posterior al respaldo: repetir sin usuarios conectados.

### Registro de evidencia (completar en staging)

| Campo | Valor |
|---|---|
| Fecha y hora | |
| Responsable | |
| Servidor / ambiente | |
| Respaldo probado (carpeta) | |
| Resultado de la prueba | ☐ RESTAURACIÓN VERIFICADA   ☐ FALLÓ |
| Tablas / filas comparadas | |
| Archivos comparados | |
| Tiempo de la prueba (`Tiempo de la prueba: … s`) | |
| Tiempo total del procedimiento de restauración real (si se hizo) | |
| Observaciones | |

## 7. Objetivos

- **RPO** (cuánto dato se puede perder): hasta 24 horas, porque el respaldo es diario. Para reducirlo hay que respaldar con más frecuencia.
- **RTO** (cuánto tarda recuperar el servicio): se mide en la prueba. Registrar el tiempo real en la tabla anterior; no se asume un valor.

## 8. Qué verifica la automatización

El flujo de integración continua (`.github/workflows/ci.yml`, trabajo «Respaldo y restauración») ejecuta en cada cambio: migraciones, un respaldo completo y la prueba de restauración contra PostgreSQL real. Así un cambio que rompa los scripts se detecta antes de llegar a staging.

## 9. Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| `ERROR: no existe la carpeta de archivos '/media'` | El volumen `media` no está montado en el servicio `respaldo` |
| `ERROR: RETENCION_DIAS debe ser 7 o más` | Valor menor que el mínimo permitido |
| `pg_dump: connection ... failed` | Credenciales de `PGUSER` / `PGPASSWORD` incorrectas o la base no está lista |
| `No se pudo crear la base temporal` (prueba) | El usuario no tiene permiso `CREATEDB` (en el compose, `electorry` sí lo tiene) |
| El servicio `respaldo` aparece `unhealthy` | El último respaldo exitoso tiene más de 26 h: revisar `docker compose logs respaldo` |
| `pg_restore` falla por la extensión `unaccent` | El PostgreSQL de destino no la tiene instalada: instalarla (o usar la imagen `postgres:16`) |
