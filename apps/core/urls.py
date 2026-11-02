from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("privacidad/", views.privacidad, name="privacidad"),
    path("terminos-venta/", views.terminos_venta, name="terminos_venta"),
    path("terminos-de-venta/", views.terminos_venta, name="terminos_de_venta"),
    path("terminos/", views.terminos_venta, name="terminos"),
    path("salud/", views.salud, name="salud"),
]
