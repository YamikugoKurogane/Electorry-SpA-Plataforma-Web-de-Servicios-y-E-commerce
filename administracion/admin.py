from django.contrib import admin

from mainPage.models import SolicitudCotizacion
from .models import GestionEstadoCotizacion


@admin.register(SolicitudCotizacion)
class SolicitudCotizacionAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'nombre',
        'apellido',
        'correo',
        'tipo_solicitud',
        'estado_actual_display',
        'fecha_creacion',
    )

    search_fields = (
        'nombre',
        'apellido',
        'correo',
        'telefono',
    )

    list_filter = (
        'tipo_solicitud',
        'fecha_creacion',
    )

    @admin.display(description='Estado actual')
    def estado_actual_display(self, obj):
        ultima_gestion = (
            GestionEstadoCotizacion.objects
            .filter(solicitud=obj)
            .order_by('-fecha_cambio', '-id')
            .first()
        )
        if ultima_gestion is None:
            return 'Sin gestión'
        return ultima_gestion.estado


@admin.register(GestionEstadoCotizacion)
class GestionEstadoCotizacionAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'solicitud',
        'estado',
        'fecha_cambio',
        'observacion',
    )

    list_filter = (
        'estado',
        'fecha_cambio',
    )

    search_fields = (
        'solicitud__nombre',
        'solicitud__apellido',
        'solicitud__correo',
    )

    ordering = (
        '-fecha_cambio',
    )