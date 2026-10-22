from django.contrib import admin

from .models import Cotizacion, LineaCotizacion


class LineaInline(admin.TabularInline):
    model = LineaCotizacion
    extra = 0


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ("id", "solicitud", "estado", "creada")
    list_filter = ("estado",)
    inlines = [LineaInline]
