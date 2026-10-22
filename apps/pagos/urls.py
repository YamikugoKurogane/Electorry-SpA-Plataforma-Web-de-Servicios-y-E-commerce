from django.urls import path

from . import views

app_name = "pagos"

urlpatterns = [
    path("iniciar/<int:venta_id>/", views.iniciar, name="iniciar"),
    path("retorno/", views.retorno, name="retorno"),
    path("sandbox/<str:token>/", views.sandbox, name="sandbox"),
]
