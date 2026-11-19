# Documento de Inicio de Proyecto — Electorry SpA

## 1. Propósito y Contexto
Electorry SpA es una empresa orientada a la prestación de servicios eléctricos y comercialización de productos/insumos relacionados. El proyecto consiste en la reconstrucción desde cero de su plataforma web de servicios y e-commerce bajo un enfoque de monolito modular en capas con Django 5 y PostgreSQL, guiado por evaluación arquitectónica (ATAM v2.0), control de acceso por roles, gestión de solicitudes y cotizaciones, ofertas vigentes, pagos idempotentes, bandeja de correos con reintentos, auditoría inmutable y despliegue reproducible.

## 2. Problema de Negocio
La gestión fragmentada o manual entre la consulta/solicitud de servicios técnicos, el catálogo de productos con ofertas vigentes, la emisión/seguimiento de cotizaciones y la compra directa genera fricción para el cliente y poca trazabilidad operativa para el equipo interno y administrativo.

## 3. Objetivos del Proyecto
- Entregar una plataforma web unificada que soporte catálogo público, tienda con carrito y compra, solicitudes de cotización con historial y adjuntos, y cotizaciones con cálculo de IVA, envío y aceptación/rechazo.
- Aplicar una arquitectura en capas (`plantillas/vistas -> services.py -> ORM -> PostgreSQL`) que centralice las reglas de negocio, transacciones y auditoría.
- Asegurar trazabilidad, seguridad por roles (`Visitante`, `Cliente`, `Interno`, `Admin`), respaldo/restauración verificada y despliegue operativo en entorno público.

## 4. Alcance
### Incluido
- Gestión de usuarios con roles, autenticación por sesión con límite de intentos y opciones de privacidad (rectificar/eliminar/anonimizar según corresponda).
- Catálogo de servicios y categorías, tienda de productos, carrito de compras y ventas con detalle.
- Solicitudes de cotización (servicios, productos o ambos), adjuntos seguros, máquina de estados, solicitud de información adicional y cotizaciones con líneas, IVA, envío y aceptación/rechazo.
- Ofertas con vigencia porcentual sobre productos y servicios (aplicando la de mayor descuento vigente sin acumular).
- Adaptador de pagos (sandbox / Webpay) con idempotencia, outbox de notificaciones con reintentos, auditoría inmutable, reportes (incluyendo CSV) y panel de gestión.
- Despliegue en nube/hosting y procedimientos documentados de respaldo y restauración.

### Excluido / Fuera de alcance inicial
- Integración productiva directa con pasarelas adicionales no implementadas en el núcleo actual (por ejemplo, conector productivo completo de Mercado Pago más allá de la interfaz extensible del adaptador).
- Aplicaciones móviles nativas independientes.

## 5. Equipo y Stakeholders
- **Alexis Prieto:** Scrum Master e Infraestructura (Docker, CI/CD, Seguridad, Git).
- **Rodrigo Guajardo:** Product Owner y Backend (Base de Datos PostgreSQL, Lógica de Negocio, Respaldos).
- **José Martínez:** QA y Frontend (Pruebas Unitarias, Accesibilidad, Generación de PDF).
- **Stakeholders:** Clientes de Electorry SpA, personal interno, administración y comisión evaluadora académica.

## 6. Supuestos, Riesgos y Restricciones
- **Restricciones:** Equipo de 3 integrantes, plazos académicos del semestre y dependencias de entornos/servicios externos.
- **Riesgos principales:** Diferencias entre motores de base de datos en pruebas locales, latencia o *cold start* en hosting gratuito, y coordinación de entregas y documentación.
- **Mitigaciones:** Uso de PostgreSQL 16 en desarrollo/pruebas cuando aplique, verificación automatizada de BD (`verificar_bd`), suite de pruebas automatizadas y pruebas previas del sistema desplegado.