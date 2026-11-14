from django.urls import path

from . import views

app_name = "solicitudes"

urlpatterns = [
    path("", views.mis_solicitudes, name="mis_solicitudes"),
    path("nueva/", views.crear, name="crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/cancelar/", views.cancelar, name="cancelar"),
    path("info/<int:pk>/responder/", views.responder_info, name="info_responder"),
    path("adjuntos/<int:pk>/", views.descargar_adjunto, name="adjunto"),
]
