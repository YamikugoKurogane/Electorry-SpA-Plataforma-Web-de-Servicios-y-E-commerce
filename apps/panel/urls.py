from django.urls import path

from apps.reportes import views as reportes

from . import views as v

app_name = "panel"

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    # solicitudes
    path("solicitudes/", v.solicitudes_lista, name="solicitudes"),
    path("solicitudes/<int:pk>/", v.solicitud_detalle, name="solicitud_detalle"),
    # cotizaciones
    path("cotizaciones/", v.cotizaciones_lista, name="cotizaciones"),
    path("cotizaciones/nueva/<int:solicitud_id>/", v.cotizacion_form, name="cotizacion_crear"),
    path("cotizaciones/<int:pk>/editar/", v.cotizacion_form, name="cotizacion_editar"),
    path("cotizaciones/<int:pk>/enviar/", v.cotizacion_enviar, name="cotizacion_enviar"),
    # clientes
    path("clientes/", v.clientes_lista, name="clientes"),
    path("clientes/<int:pk>/", v.cliente_detalle, name="cliente_detalle"),
    path("clientes/<int:pk>/anonimizar/", v.cliente_anonimizar, name="cliente_anonimizar"),
    # servicios
    path("servicios/", v.ServicioLista.as_view(), name="servicios"),
    path("servicios/nuevo/", v.ServicioCrear.as_view(), name="servicio_crear"),
    path("servicios/<int:pk>/editar/", v.ServicioEditar.as_view(), name="servicio_editar"),
    path("servicios/<int:pk>/eliminar/", v.ServicioEliminar.as_view(), name="servicio_eliminar"),
    path("servicios/categorias/", v.CategoriaServicioLista.as_view(), name="catserv"),
    path("servicios/categorias/nueva/", v.CategoriaServicioCrear.as_view(), name="catserv_crear"),
    path("servicios/categorias/<int:pk>/editar/", v.CategoriaServicioEditar.as_view(), name="catserv_editar"),
    path("servicios/categorias/<int:pk>/eliminar/", v.CategoriaServicioEliminar.as_view(), name="catserv_eliminar"),
    # productos
    path("productos/", v.ProductoLista.as_view(), name="productos"),
    path("productos/nuevo/", v.ProductoCrear.as_view(), name="producto_crear"),
    path("productos/<int:pk>/editar/", v.ProductoEditar.as_view(), name="producto_editar"),
    path("productos/<int:pk>/eliminar/", v.ProductoEliminar.as_view(), name="producto_eliminar"),
    path("productos/categorias/", v.CategoriaProductoLista.as_view(), name="catprod"),
    path("productos/categorias/nueva/", v.CategoriaProductoCrear.as_view(), name="catprod_crear"),
    path("productos/categorias/<int:pk>/editar/", v.CategoriaProductoEditar.as_view(), name="catprod_editar"),
    path("productos/categorias/<int:pk>/eliminar/", v.CategoriaProductoEliminar.as_view(), name="catprod_eliminar"),
    # ventas
    path("ventas/", v.ventas_lista, name="ventas"),
    path("ventas/<int:pk>/", v.venta_detalle, name="venta_detalle"),
    path("ventas/<int:pk>/accion/", v.venta_accion, name="venta_accion"),
    # usuarios
    path("usuarios/", v.UsuarioLista.as_view(), name="usuarios"),
    path("usuarios/nuevo/", v.UsuarioCrear.as_view(), name="usuario_crear"),
    path("usuarios/<int:pk>/editar/", v.UsuarioEditar.as_view(), name="usuario_editar"),
    # transversales
    path("reportes/", reportes.reporte, name="reportes"),
    path("auditoria/", v.auditoria_lista, name="auditoria"),
    path("notificaciones/", v.notificaciones_lista, name="notificaciones"),
]
