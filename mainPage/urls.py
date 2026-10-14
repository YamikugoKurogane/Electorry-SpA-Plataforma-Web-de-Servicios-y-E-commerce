from django.urls import path  # type: ignore
from . import views
from .views import *


urlpatterns = [
    path("", home, name="home"),
    path("registro/", registro_cliente_view, name="registro"),
    # Ruta para descargar la cotización en PDF [RF-28]
    path("cotizacion/<int:cotizacion_id>/pdf/", generar_cotizacion_pdf, name="exportar_cotizacion_pdf"),
    # Mantenedor de productos
    path("admin/productos/", views.admin_productos, name="admin_productos"),
    path("admin/productos/crear/", views.crear_producto, name="crear_producto"),
    path(
        "admin/productos/<int:producto_id>/editar/",
        views.editar_producto,
        name="editar_producto",
    ),
    path(
        "admin/productos/<int:producto_id>/desactivar/",
        views.desactivar_producto,
        name="desactivar_producto",
    ),
    # Mantenedor de servicios
    path("admin/servicios/", views.admin_servicios, name="admin_servicios"),
    path("admin/servicios/crear/", views.crear_servicio, name="crear_servicio"),
    path(
        "admin/servicios/<int:servicio_id>/editar/",
        views.editar_servicio,
        name="editar_servicio",
    ),
    path(
        "admin/servicios/<int:servicio_id>/desactivar/",
        views.desactivar_servicio,
        name="desactivar_servicio",
    ),
]
