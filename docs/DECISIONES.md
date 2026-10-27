# Decisiones y supuestos

## Decisiones del ATAM aplicadas
| ID | Decisión | Dónde se ve |
|---|---|---|
| D1 | Monolito modular en capas | `apps/*` con `services.py` por módulo |
| D2 | Django MVT + DRF | `apps/api` (solo lectura, con límite de tasa) |
| D3 | PostgreSQL | `DATABASE_URL`; `docker-compose.yml`; CI contra Postgres |
| D4 | Sesión con roles (sin JWT) | `apps/usuarios`, `apps/core/permisos.py` |
| D5 | Pasarela por adaptador | `apps/pagos/gateways/` |
| D6 | Nginx + Gunicorn; archivos abstraídos | `deploy/`; adjuntos solo vía vista autorizada |
| D7 | Local → staging → producción por variables | `config/settings.py`, `.env.example`, `docker-compose.yml` |
| D8 | Correo tolerante a fallas | `apps/notificaciones` (outbox + reintentos) |

## Supuestos que conviene validar con el propietario
1. **Estados:** se agregó `Cancelada` (terminal) a los seis del documento. El cliente acepta/rechaza la cotización desde su cuenta (rechazar devuelve la solicitud a «En revisión»).
2. **IVA 19 %** sobre cotizaciones (neto + IVA); los productos se publican con IVA incluido. Montos en CLP enteros.
3. **Roles:** el usuario «Interno» no gestiona catálogo, usuarios, reportes ni auditoría (matriz en README).
4. **Eliminación de datos:** se *anonimiza* al cliente (y se borran sus adjuntos) conservando el historial comercial sin datos personales.
5. **Sin inventario:** fuera de alcance según el caso; los productos solo tienen «activo».
6. **Restablecer contraseña por correo** no está en los RF; un administrador puede fijar una nueva desde «Usuarios y roles».
7. **Metas numéricas** (p95, RPO/RTO, 99 %) son las propuestas del ATAM, pendientes de validación.

## Límites conocidos
- p95 ≤ 2 s con 30 usuarios concurrentes: el diseño lo favorece (consultas constantes, paginación, índices; probado con `assertNumQueries`), pero **no se ejecutó una prueba de carga real**. Pendiente (p. ej. Locust) en staging.
- Webpay sin probar contra Transbank (ver README).
- Ley 21.719: se implementó aviso, consentimiento, rectificación y supresión; la revisión legal del texto del aviso queda a cargo de Electorry.

## Hallazgos de la integración con PostgreSQL (S2-R1)
- Las pruebas pasan sobre PostgreSQL 16.2 y SQLite. `verificar_bd` comprueba integridad y bloqueo de filas.
- La búsqueda distinguía tildes en PostgreSQL («instalacion» no encontraba «Instalación»). Se corrigió con la extensión `unaccent`
  (`apps/core/busqueda.py`). **Pendiente de verificar con la extensión real** en Docker (`postgres:16`); en desarrollo se validó la
  forma de la consulta emulando la función.
- SQLite no ignora mayúsculas en letras con tilde: solo afecta al desarrollo local.
