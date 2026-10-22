from django.urls import path

from . import views

app_name = "solicitudes"

urlpatterns = [
    path("", views.mis_solicitudes, name="mis_solicitudes"),
    path("nueva/", views.crear, name="crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("adjuntos/<int:pk>/", views.descargar_adjunto, name="adjunto"),
]
