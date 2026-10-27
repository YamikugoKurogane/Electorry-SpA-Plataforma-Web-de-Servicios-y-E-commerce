# Electorry SpA — Plataforma Web de Servicios y E-commerce

Reconstrucción desde cero según el **ATAM v2.0**: monolito modular en capas con **Django 5 + PostgreSQL**,
autenticación por sesión con roles, adaptador de pagos, correo tolerante a fallas y despliegue reproducible.

## Módulos (`apps/`)

| App | Responsabilidad |
|---|---|
| `usuarios` | Usuario único con rol (Cliente / Interno / Admin), registro, login con límite de intentos, privacidad (rectificar/eliminar) |
| `catalogo` | Servicios y categorías (público) |
| `solicitudes` | Solicitud de cotización, adjuntos seguros, máquina de estados, historial |
| `cotizaciones` | Cotizaciones con líneas, IVA, envío, aceptación/rechazo del cliente |
| `tienda` | Productos, carrito (sesión), ventas y detalle |
| `pagos` | Adaptador de pasarela (`sandbox`, `webpay`), intentos de pago idempotentes |
| `notificaciones` | Bandeja de salida de correo con reintentos (outbox) |
| `auditoria` | Registro inmutable de quién/cuándo/qué cambió |
| `reportes` | Reportes de solicitudes, cotizaciones y ventas + CSV |
| `panel` | Panel administrativo (vistas del personal) |
| `api` | API REST pública de solo lectura (catálogo) |
| `core` | Permisos por rol, utilidades, errores, healthcheck, datos demo |

**Capas:** plantillas/vistas → `services.py` (reglas de negocio, transacciones, auditoría) → ORM → PostgreSQL.
Las vistas solo orquestan; la lógica vive en `services.py` (RNF-MAN-01).

## Puesta en marcha local (≤ 10 min)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # DJANGO_DEBUG=1, SQLite si no defines DATABASE_URL
python manage.py migrate
python manage.py seed_demo      # crea datos demo y muestra las contraseñas generadas
python manage.py runserver
```
Con PostgreSQL: define `DATABASE_URL=postgres://usuario:clave@localhost:5432/electorry`.

Pruebas: `DJANGO_TESTING=1 python manage.py test tests` (105 pruebas; algunas se omiten según el motor de base de datos).

## Base de datos en desarrollo (PostgreSQL)

Cada integrante usa **su propia base local**. No compartan una base entre personas: se pisarían datos y migraciones.

```powershell
# 1. Levantar PostgreSQL 16 (requiere Docker Desktop)
docker compose -f docker-compose.dev.yml up -d
docker ps                               # electorry-db debe aparecer como "healthy"

# 2. Configurar el proyecto (el .env.example ya trae DATABASE_URL apuntando a esta base)
copy .env.example .env

# 3. Crear tablas y datos de demostración
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo              # guarda las contraseñas que imprime
python manage.py makemigrations --check --dry-run    # debe decir "No changes detected"

# 4. Verificar que realmente usa PostgreSQL y que la base rechaza datos inválidos
python manage.py verificar_bd --exigir-postgres

# 5. Correr las pruebas
$env:DJANGO_TESTING="1"; python manage.py test tests
```

`verificar_bd` comprueba el motor, la versión, la codificación, las migraciones y que la base **rechaza** datos
inválidos (correo duplicado, cantidades en 0, token de pago repetido, borrar registros en uso, bloqueo de filas).
No deja datos en la base. Salida esperada: todas las líneas en `[OK]` y «Base de datos verificada correctamente».

**Empezar de cero:** `docker compose -f docker-compose.dev.yml down -v` y repetir desde el paso 1.
**Ver las tablas:** `docker exec -it electorry-db psql -U electorry -d electorry -c "\dt"`

| Síntoma | Causa probable |
|---|---|
| `connection refused` | El contenedor no corre, o otro PostgreSQL ya usa el puerto 5432 (cámbialo a `5433:5432` y ajusta `DATABASE_URL`) |
| `password authentication failed` | Contraseña distinta, o caracteres especiales sin codificar en `DATABASE_URL` |
| Sigue usando SQLite | El `.env` no está junto a `manage.py` o `DATABASE_URL` está comentada (`verificar_bd` lo avisa) |
| Falla solo en las pruebas | Diferencia real entre SQLite y PostgreSQL: repórtala, no ajustes la prueba para esconderla |

## Cargar el contenido real (servicios y productos)

Las planillas están en `contenido/` (ver `contenido/LEEME.md`). Se llenan con Excel y se cargan con un comando repetible:

```powershell
python manage.py importar_contenido contenido --simular   # valida y muestra qué haría, sin guardar
python manage.py importar_contenido contenido             # guarda
```
Si una fila tiene errores no se guarda nada y se listan con su número de línea. Si el nombre ya existe, se actualiza (no duplica).

**Búsqueda sin tildes:** en PostgreSQL, la migración `core.0001` activa la extensión `unaccent` para que «instalacion» encuentre
«Instalación». En la imagen `postgres:16` de Docker está disponible. Si el servidor no la tiene, la migración no falla y la
búsqueda sigue funcionando, solo que distinguiendo tildes.

## Roles y permisos

| Pantalla / acción | Visitante | Cliente | Interno | Admin |
|---|:-:|:-:|:-:|:-:|
| Catálogo de servicios y productos, carrito | ✅ | ✅ | ✅ | ✅ |
| Crear solicitud, comprar, ver **solo lo propio** | — | ✅ | — | — |
| Panel: solicitudes, cotizaciones, clientes (lectura), ventas (lectura) | — | — | ✅ | ✅ |
| CRUD servicios/productos, usuarios y roles, reportes, auditoría, correos, anonimizar, cancelar/marcar pago | — | — | — | ✅ |

## Despliegue (staging y producción: mismo stack, solo cambian variables — EC-11)

```bash
export POSTGRES_PASSWORD=...  DJANGO_SECRET_KEY=...  DJANGO_ALLOWED_HOSTS=tu-dominio.cl
export DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.cl
docker compose up -d --build
docker compose exec web python manage.py createsuperuser   # primer administrador
```
Incluye: Nginx (estáticos + proxy), Gunicorn, PostgreSQL, reintento de correos cada 5 min y **respaldo diario**
con retención de 14 días. HTTPS: terminar TLS en el balanceador del proveedor cloud o con certbot; la app
fuerza HTTPS, cookies `Secure`/`HttpOnly` y HSTS cuando `DJANGO_DEBUG` no está activo.

**Restauración** (probar al menos una vez antes del cierre — RNF-FIA-03):
```bash
docker compose stop web nginx correo
docker compose exec respaldo ls /backups
docker compose run --rm -v $PWD/deploy/restore.sh:/restore.sh:ro respaldo sh /restore.sh /backups/electorry_XXXXXXXX_XXXXXX.dump
docker compose start web nginx correo
```

## Pasarela de pago (D5)
`PAYMENT_GATEWAY=sandbox` (simulada, solo si `DEBUG`/`PAYMENT_SANDBOX_PERMITIDO`) o `webpay` (Transbank REST;
por defecto ambiente de integración con credenciales públicas). Para Mercado Pago: crear
`apps/pagos/gateways/mercadopago.py` que implemente `PasarelaPago` y registrarlo en `gateways/__init__.py`.
No se toca el módulo de ventas (EC-03). **El adaptador Webpay no pudo probarse contra Transbank en el entorno de
desarrollo (sin red): valídalo en su ambiente de integración antes de producción.**

## Variables de entorno
Ver `.env.example`. Obligatoria en producción: `DJANGO_SECRET_KEY` (la app no arranca sin ella).

## Documentación
- `docs/TRAZABILIDAD.md` — RF / RNF / HU / escenarios → código y pruebas.
- `docs/DECISIONES.md` — decisiones D1–D8 y supuestos.
