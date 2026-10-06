from django.contrib import admin

from .models import (
    SolicitudCotizacion,
    GestionEstadoCotizacion
)


@admin.register(SolicitudCotizacion)
class SolicitudCotizacionAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'nombre',
        'apellido',
        'correo',
        'tipo_solicitud',
        'estado_actual_display',
    )

    search_fields = (
        'nombre',
        'apellido',
        'correo',
        'telefono',
    )

    list_filter = (
        'tipo_solicitud',
    )


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