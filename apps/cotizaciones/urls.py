from django.urls import path

from . import views

app_name = "cotizaciones"

urlpatterns = [
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/responder/", views.responder, name="responder"),
]
