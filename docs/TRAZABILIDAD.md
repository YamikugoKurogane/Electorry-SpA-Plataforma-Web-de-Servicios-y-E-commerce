# Matriz de trazabilidad

## Requisitos funcionales
| RF | HU | Implementación | Pruebas (`tests/`) |
|---|---|---|---|
| RF-01 Registro/login/validación | HU-01 | `usuarios/forms.py`, `views.py` | `test_usuarios.RegistroLoginTests` |
| RF-02 Catálogo de servicios | HU-02, 03 | `catalogo/` | `test_panel_reportes.CatalogoPublicoTests` |
| RF-03 Solicitud de cotización + adjuntos | HU-04 | `solicitudes/forms.py`, `services.crear_solicitud` | `test_solicitudes.CrearSolicitudTests` |
| RF-04 Cliente consulta sus solicitudes | HU-05 | `solicitudes/views.py` (`mis_solicitudes`, `detalle`) | `AutorizacionPorObjetoTests`, `EstadosTests` |
| RF-05 Gestión de solicitudes e historial | HU-06, 07 | `panel/views.py`, `solicitudes/services.cambiar_estado` | `EstadosTests` |
| RF-06 CRUD servicios | HU-08 | `panel` (`Servicio*`) | `PanelCrudTests` |
| RF-07 Clientes e historial | HU-09, 11 | `panel` (`clientes_lista`, `cliente_detalle`) | `PanelCrudTests.test_clientes_historial` |
| RF-08 Cotizaciones | HU-10 | `cotizaciones/` | `test_cotizaciones` |
| RF-09 Reportes | HU-12 | `reportes/` | `ReportesTests` |
| RF-10 Usuarios, roles y permisos | — | `usuarios`, `core/permisos.py`, `panel` | `PanelCrudTests`, `AutorizacionPorObjetoTests` |
| RF-11 Notificaciones por correo | — | `notificaciones/` | `NotificacionesTests` |
| RF-12 Productos y categorías | — | `tienda/`, `panel` (`Producto*`) | `PanelCrudTests.test_crud_productos` |
| RF-13 Compra y pago (pendiente hasta confirmar) | — | `tienda/`, `pagos/` | `test_tienda_pagos` |
| RF-14 Ventas y detalle | — | `tienda/models.py`, `panel` | `CarritoCheckoutTests` |
| RF-15 Auditoría | HU-06 | `auditoria/` (escrita en `services`) | `EstadosTests`, `PanelCrudTests` |

## Requisitos no funcionales
| RNF | Implementación | Verificación |
|---|---|---|
| PER-01/03 | Paginación, estáticos por Nginx, escalado vertical | Diseño; **carga real pendiente** |
| PER-02 | `select_related`/`prefetch_related`, índices | `assertNumQueries` (catálogo y cotizaciones) |
| SEG-01 | Hash Django, bloqueo por intentos (`IntentoLogin`) | `test_bloqueo_por_intentos_repetidos` |
| SEG-02 | `rol_requerido`, `solicitudes_visibles_para` | `AutorizacionPorObjetoTests`, ventas ajenas |
| SEG-03 | Validación en servidor, ORM, escape, CSRF | pruebas de formularios |
| SEG-04 | `solicitudes/validators.py`, nombres aleatorios, descarga autorizada | pruebas de adjuntos |
| SEG-05 | `settings.py` (HTTPS, cookies Secure/HttpOnly, HSTS) | `check --deploy` en CI |
| SEG-06 | Sin campos de tarjeta; Webpay solo guarda campos no sensibles | `test_no_se_almacenan_datos_de_tarjeta` |
| SEG-07 | Aviso, consentimiento, perfil, anonimización | `PrivacidadTests` |
| SEG-08 | Todo por variables de entorno; sin `SECRET_KEY` no arranca | `settings.py` |
| FIA-01 | `templates/4xx/500`, logging a consola/archivo | `test_pagina_404_controlada` |
| FIA-02 | `transaction.atomic`, `CheckConstraint`, FKs `PROTECT` | `test_falla_al_crear_detalle_*`, `test_historial_atomico_*` |
| FIA-03 | `deploy/backup.sh` (diario, verificado, 14 días), `restore.sh` | **Restauración por probar en staging** |
| DIS-01/02 | `restart: unless-stopped`, healthcheck `/salud/`, aislamiento de integraciones | `test_falla_de_correo_*`, `test_falla_de_pasarela_*` |
| AUD-01 | `HistorialEstado` + `RegistroAuditoria` en la misma transacción | `test_flujo_completo_con_historial` |
| USA-01 | Formulario mínimo, responsivo, validación en línea | UAT pendiente (≤ 5 min) |
| MAN-01 | `services.py` por app | revisión de código |
| MAN-02 | 91 pruebas + `.github/workflows/ci.yml` en cada PR | CI |
| MAN-03 | README, docs/ | — |
| POR-01/02 | CSS responsivo; Docker + variables de entorno | — |

## Escenarios de calidad
EC-01 `AutorizacionPorObjetoTests` · EC-02 `PagoTests` (idempotencia, atomicidad) · EC-03 `test_cambiar_de_pasarela_no_toca_ventas` ·
EC-04 diseño (UAT pendiente) · EC-05 `assertNumQueries` · EC-06 `NotificacionesTests`, `test_falla_de_pasarela_*` ·
EC-07 `deploy/backup.sh` · EC-08 `EstadosTests` · EC-09 `TRANSICIONES` en un solo diccionario · EC-10 pruebas de adjuntos · EC-11 `docker-compose.yml` + CI.
