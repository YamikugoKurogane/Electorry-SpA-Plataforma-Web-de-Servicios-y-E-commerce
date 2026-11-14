from django.contrib import admin

from .models import Oferta


@admin.register(Oferta)
class OfertaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "descuento", "fecha_inicio", "fecha_fin", "solo_clientes", "finalizada_en")
    list_filter = ("solo_clientes",)
    search_fields = ("titulo",)
    filter_horizontal = ("productos", "servicios")
