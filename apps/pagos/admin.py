from django.contrib import admin

from .models import Pago


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("id", "venta", "proveedor", "estado", "monto", "creado")
    list_filter = ("estado", "proveedor")
