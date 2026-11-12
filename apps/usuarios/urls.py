from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("ingresar/", views.IngresarView.as_view(), name="login"),
    path("salir/", views.salir, name="logout"),
    path("registro/", views.registro, name="registro"),
    path("recuperar/", views.recuperar_password, name="recuperar_password"),
    path("restablecer/<uidb64>/<token>/", views.restablecer_confirmar, name="restablecer_confirmar"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/contrasena/", views.cambiar_password, name="cambiar_password"),
    path("perfil/eliminar/", views.eliminar_cuenta, name="eliminar_cuenta"),
]
