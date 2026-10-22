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

Pruebas: `DJANGO_TESTING=1 python manage.py test tests` (91 pruebas).

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
