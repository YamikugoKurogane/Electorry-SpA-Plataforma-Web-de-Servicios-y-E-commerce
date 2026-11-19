# Electorry SpA — Plataforma Web de Servicios y E-commerce

Electorry SpA es una plataforma web de servicios y e-commerce dirigida a empresas de servicios eléctricos y sus clientes. Resuelve el problema de la gestión manual de solicitudes y cotizaciones, digitalizando todo el ciclo de vida del pedido: desde que el cliente solicita un servicio, recibe una cotización, paga en línea y recibe su comprobante, todo con trazabilidad completa y sin pérdida de información.

Reconstrucción desde cero según el **ATAM v2.0**: monolito modular en capas con **Django 5 + PostgreSQL**,
autenticación por sesión con roles, adaptador de pagos, correo tolerante a fallas y despliegue reproducible.

## Módulos (`apps/`)

| App | Responsabilidad |
|---|---|
| `usuarios` | Usuario único con rol (Cliente / Interno / Admin), registro, login con límite de intentos, privacidad (rectificar/eliminar) |
| `catalogo` | Servicios y categorías (público) |
| `solicitudes` | Solicitud de cotización de un servicio, de productos o de ambos, adjuntos seguros, máquina de estados, historial |
| `cotizaciones` | Cotizaciones con líneas, IVA, envío, aceptación/rechazo del cliente |
| `tienda` | Productos, carrito (sesión), ventas y detalle |
| `ofertas` | Ofertas con vigencia sobre productos y servicios; calcula el precio vigente que se muestra y se cobra |
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

Pruebas: `DJANGO_TESTING=1 python manage.py test tests` (287 pruebas; algunas se omiten según el motor de base de datos).

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

## Ofertas e información adicional (sprint 4)

- **Ofertas** (`/panel/ofertas/`, solo administrador): descuento porcentual (1–90 %) con vigencia por fechas, sobre productos y/o servicios.
  Se pueden crear, editar y **finalizar** (termina al instante; no se puede deshacer). El cliente las ve en `/ofertas/`, en el inicio, en la
  tienda y en el catálogo. **El precio con oferta es el que se cobra** (tarjeta, carrito, venta y solicitud). Si varias ofertas afectan
  a un producto se usa la de mayor descuento (no se suman).
- **Información adicional** (en el detalle de cada solicitud): el personal pregunta; el cliente responde con texto y/o archivos
  (JPG, PNG, PDF). Se avisa por correo, queda auditado y se cierra solo si la solicitud se cancela o finaliza.

## Roles y permisos

| Pantalla / acción | Visitante | Cliente | Interno | Admin |
|---|:-:|:-:|:-:|:-:|
| Catálogo de servicios y productos, carrito | ✅ | ✅ | ✅ | ✅ |
| Crear solicitud, comprar, ver **solo lo propio** | — | ✅ | — | — |
| Panel: solicitudes, cotizaciones, clientes (lectura), ventas (lectura) | — | — | ✅ | ✅ |
| CRUD servicios/productos, **gestión de ofertas**, usuarios y roles, reportes, listado de pagos, auditoría, correos, anonimizar, cancelar/marcar pago | — | — | — | ✅ |
| Ver ofertas vigentes (las «solo clientes» requieren sesión) | ✅ | ✅ | ✅ | ✅ |
| Pedir información adicional dentro de una solicitud | — | — | ✅ | ✅ |
| Responder esa información (con archivos) en **sus** solicitudes | — | ✅ | — | — |

## Despliegue (staging y producción: mismo stack, solo cambian variables — EC-11)

```bash
export POSTGRES_PASSWORD=...  DJANGO_SECRET_KEY=...  DJANGO_ALLOWED_HOSTS=tu-dominio.cl
export DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.cl
docker compose up -d --build
docker compose exec web python manage.py createsuperuser   # primer administrador
```
Incluye: Nginx (estáticos + proxy), Gunicorn, PostgreSQL, reintento de correos cada 5 min y **respaldo diario de la
base de datos y de los archivos subidos** (retención de 14 días por defecto, mínimo 7). HTTPS: terminar TLS en el balanceador
del proveedor cloud o con certbot; la app fuerza HTTPS, cookies `Secure`/`HttpOnly` y HSTS cuando `DJANGO_DEBUG` no está activo.

### Respaldos y restauración
Procedimiento completo, prueba de restauración en staging y planilla de evidencia: **`docs/RESPALDOS.md`**.
```bash
docker compose run --rm prueba_restauracion      # prueba SIN tocar el sistema en vivo (usa el último respaldo)
docker compose stop web correo nginx             # restauración real: destructiva, con la app detenida
docker compose run --rm -e CONFIRMAR=SI restauracion /backups/AAAAMMDD_HHMMSS
docker compose start web correo nginx
```
Los respaldos viven en el mismo servidor: cópialos periódicamente a otro lugar (ver `docs/RESPALDOS.md`, sección 4).

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

## Integrantes y Roles
* **Alexis Prieto** - Scrum Master e Infraestructura (Docker, CI/CD, Seguridad, Git).
* **Rodrigo Guajardo** - Product Owner y Backend (Base de Datos PostgreSQL, Lógica de Negocio, Respaldos).
* **José Martínez** - QA y Frontend (Pruebas Unitarias, Accesibilidad, Generación de PDF).

## Metodología de Trabajo
Utilizamos el marco de trabajo **Scrum**, con Sprints de 15 días. 
* **Herramientas:** Trello para la gestión del tablero Kanban y GitHub para el control de versiones.
* **Ceremonias:** Daily Scrums diarios, Sprint Planning y Sprint Review al final de cada iteración.
* **Calidad:** El código se congela al final del Sprint y se valida con una suite de más de 287 pruebas automatizadas antes de pasar a `main`.