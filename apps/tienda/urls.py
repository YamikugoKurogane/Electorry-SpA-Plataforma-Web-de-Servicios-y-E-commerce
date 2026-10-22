from django.urls import path

from . import views

app_name = "tienda"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("carrito/", views.ver_carrito, name="carrito"),
    path("carrito/agregar/<int:producto_id>/", views.carrito_agregar, name="carrito_agregar"),
    path("carrito/actualizar/<int:producto_id>/", views.carrito_actualizar, name="carrito_actualizar"),
    path("carrito/quitar/<int:producto_id>/", views.carrito_quitar, name="carrito_quitar"),
    path("comprar/", views.checkout, name="checkout"),
    path("mis-compras/", views.mis_compras, name="mis_compras"),
    path("mis-compras/<int:pk>/", views.compra_detalle, name="compra"),
    path("<slug:slug>/", views.detalle, name="detalle"),
]
