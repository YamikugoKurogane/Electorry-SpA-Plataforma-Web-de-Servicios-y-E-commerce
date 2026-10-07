from django.urls import path
<<<<<<< HEAD
from .views import home, registro_cliente_view, generar_cotizacion_pdf
=======
from . import views
from views import *

>>>>>>> cacbb9d79ec980d125acf6fc30e6b596a8378325

urlpatterns = [
    path("", home, name="home"),
    path("registro/", registro_cliente_view, name="registro"),
<<<<<<< HEAD
    # Ruta para descargar la cotización en PDF [RF-28]
    path("cotizacion/<int:cotizacion_id>/pdf/", generar_cotizacion_pdf, name="exportar_cotizacion_pdf"),
=======
    path("solicitar-cotizacion/", views.solicitar_cotizacion, name="solicitar_cotizacion")
>>>>>>> cacbb9d79ec980d125acf6fc30e6b596a8378325
]