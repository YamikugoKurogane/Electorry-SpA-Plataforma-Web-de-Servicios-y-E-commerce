from django.contrib import admin

from .models import CategoriaProducto, DetalleVenta, Producto, Venta

admin.site.register(CategoriaProducto)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio", "activo")
    list_filter = ("activo", "categoria")
    search_fields = ("nombre",)


class DetalleInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "estado", "total", "creada")
    list_filter = ("estado",)
    inlines = [DetalleInline]
