# Artefactos Scrum — Electorry SpA

## 1. Product Vision
Para clientes particulares y de servicios técnicos de Electorry SpA que necesitan cotizar trabajos y adquirir productos de forma ágil y transparente, **Electorry SpA (Plataforma Web de Servicios y E-commerce)** es una aplicación web modular en Django 5 y PostgreSQL que unifica catálogo, tienda con carrito, solicitudes de cotización y gestión operativa con trazabilidad y seguridad, diferenciándose por centralizar las reglas de negocio en la capa de servicios, auditar cambios clave y garantizar despliegues y respaldos reproducibles.

## 2. Product Backlog (Resumen Priorizado)
1. **Fundación, Seguridad y Roles:** Modelo de usuario con roles (`Cliente`, `Interno`, `Admin`), login con límite de intentos, permisos por rol y privacidad.
2. **Catálogo y Tienda:** Catálogo de servicios y categorías, productos, ofertas vigentes con cálculo automático del mayor descuento, carrito de sesión y ventas.
3. **Solicitudes y Cotizaciones:** Solicitudes de cotización (servicios/productos/ambos), adjuntos seguros, máquina de estados, información adicional y cotizaciones con IVA, envío y aceptación/rechazo.
4. **Pagos, Notificaciones y Auditoría:** Adaptador de pagos idempotente (sandbox/Webpay), bandeja de salida de correos (`outbox`) con reintentos y registro inmutable de auditoría.
5. **Panel, Reportes y Operación:** Panel administrativo/interno, reportes y exportación CSV, carga de contenido desde planillas, Docker/Nginx/Gunicorn, respaldos/restauración y despliegue.

## 3. Sprint Backlog (Iteraciones de 15 Días)
- **Organización:** Ciclos de 15 días gestionados mediante tablero en Trello y control de versiones en GitHub, con *Daily Scrums*, *Sprint Planning* y *Sprint Review*.
- **Enfoque por iteraciones:** Construcción incremental desde la base de datos, autenticación y arquitectura en capas hacia los flujos transaccionales completos (solicitudes, cotizaciones, tienda, ofertas, pagos), cierre de calidad/pruebas y preparación de despliegue y documentación final.

## 4. Definition of Done (DoD)
Una historia o tarea se considera **Terminada (DoD)** cuando cumple con:
- Reglas de negocio, transacciones y auditoría implementadas en la capa correspondiente (`services.py`) y vistas acotadas a orquestación.
- Permisos por rol y validaciones de entrada/seguridad aplicados.
- Migraciones de base de datos coherentes y verificadas.
- Pruebas automatizadas ejecutadas y aprobadas sin regresiones.
- Código integrado en el repositorio mediante commits trazables del responsable.

## 5. Sprint Retrospectives (Lecciones y Ajustes)
- **Qué funcionó bien:** Separar la lógica de negocio en servicios facilitó el mantenimiento y las pruebas; contar con scripts/comandos repetibles agilizó la verificación de base de datos y carga de datos.
- **Qué presentó dificultades:** Ajustes de entorno/base de datos, coordinación de documentación formal junto con el desarrollo y validación de integraciones externas en entornos restringidos.
- **Acciones aplicadas:** Estandarizar el uso de PostgreSQL en desarrollo/pruebas, unificar la documentación técnica y de entrega en el repositorio, y comprobar el sistema desplegado antes de cada instancia de evaluación.