from django.urls import path
from .views import home, registro_cliente_view

urlpatterns = [
    path("", home, name="home"),
    path("registro/", registro_cliente_view, name="registro"),
]