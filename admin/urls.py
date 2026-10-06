from django.urls import path

from . import views


urlpatterns = [
    path(
        'solicitudes/<int:solicitud_id>/estado/',
        views.cambiar_estado_solicitud,
        name='cambiar_estado_solicitud'
    ),
    path(
        'solicitudes/<int:solicitud_id>/',
        views.detalle_solicitud_cotizacion,
        name='detalle_solicitud_cotizacion'
    ),
]