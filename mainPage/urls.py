from django.urls import path
from .views import *


urlpatterns = [
    path("", home, name="home"),
    path("registro/", registro_cliente_view, name="registro"),
    # Ruta para descargar la cotización en PDF [RF-28]
    path("cotizacion/<int:cotizacion_id>/pdf/", generar_cotizacion_pdf, name="exportar_cotizacion_pdf"),
]