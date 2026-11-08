from django.contrib import admin

from .models import Adjunto, HistorialEstado, ItemSolicitud, SolicitudCotizacion


class HistorialInline(admin.TabularInline):
    model = HistorialEstado
    extra = 0
    can_delete = False
    readonly_fields = ("estado_anterior", "estado_nuevo", "usuario", "fecha", "comentario")


class ItemInline(admin.TabularInline):
    model = ItemSolicitud
    extra = 0


@admin.register(SolicitudCotizacion)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "servicio", "estado", "creada")
    list_filter = ("estado",)
    inlines = [ItemInline, HistorialInline]


admin.site.register(Adjunto)
