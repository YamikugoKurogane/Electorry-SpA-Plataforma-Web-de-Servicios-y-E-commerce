from django.urls import path  # type: ignore[reportMissingImports]
from . import views

urlpatterns = [
    # Vista Principal Admin
    path('', views.homeAdmin, name='homeAdmin'),
    
    # ============================================================
    # RUTAS MANTENEDOR DE SERVICIOS FOTOVOLTAICOS [HU-11]
    # ============================================================
    path('servicios/', views.servicio_listar, name='servicio_listar'),
    path('servicios/crear/', views.servicio_crear, name='servicio_crear'),
    path('servicios/editar/<int:pk>/', views.servicio_editar, name='servicio_editar'),
    path('servicios/eliminar/<int:pk>/', views.servicio_eliminar, name='servicio_eliminar'),
    
    # Rutas de Gestión de Cotizaciones
    path('solicitud/<int:solicitud_id>/cambiar-estado/', views.cambiar_estado_solicitud, name='cambiar_estado_solicitud'),
    path('solicitud/<int:solicitud_id>/detalle/', views.detalle_solicitud_cotizacion, name='detalle_solicitud_cotizacion'),
]