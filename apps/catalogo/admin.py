from django.contrib import admin

from .models import CategoriaServicio, Servicio

admin.site.register(CategoriaServicio)


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "disponible")
    list_filter = ("disponible", "categoria")
    search_fields = ("nombre",)
