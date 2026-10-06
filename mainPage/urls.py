from django.urls import path
from . import views
from views import *


urlpatterns = [
    path("", home, name="home"),
    path("registro/", registro_cliente_view, name="registro"),
    path("solicitar-cotizacion/", views.solicitar_cotizacion, name="solicitar_cotizacion")
]