from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    GestionEstadoCotizacion,
    EstadoCotizacion,
)


TRANSICIONES_ESTADO = {
    EstadoCotizacion.PENDIENTE: [
        EstadoCotizacion.EN_REVISION,
    ],

    EstadoCotizacion.EN_REVISION: [
        EstadoCotizacion.COTIZADA,
    ],

    EstadoCotizacion.COTIZADA: [
        EstadoCotizacion.ACEPTADA,
        EstadoCotizacion.RECHAZADA,
    ],

    EstadoCotizacion.ACEPTADA: [
        EstadoCotizacion.FINALIZADA,
    ],

    EstadoCotizacion.RECHAZADA: [],

    EstadoCotizacion.FINALIZADA: [],
}


@transaction.atomic
def cambiar_estado_cotizacion(
    solicitud,
    nuevo_estado,
    observacion=None
):
    estado_actual = (
        GestionEstadoCotizacion.objects
        .filter(solicitud=solicitud)
        .order_by('-fecha_cambio')
        .first()
    )

    if estado_actual is None:
        estado_actual = GestionEstadoCotizacion.objects.create(
            solicitud=solicitud,
            estado=EstadoCotizacion.PENDIENTE,
            observacion='Estado inicial de la solicitud.'
        )

    estado_anterior = estado_actual.estado

    if nuevo_estado not in TRANSICIONES_ESTADO.get(
        estado_anterior,
        []
    ):
        raise ValidationError(
            f'No es posible cambiar la solicitud '
            f'desde "{estado_actual.get_estado_display()}" '
            f'a "{dict(EstadoCotizacion.choices).get(nuevo_estado, nuevo_estado)}".'
        )

    return GestionEstadoCotizacion.objects.create(
        solicitud=solicitud,
        estado=nuevo_estado,
        observacion=observacion
    )


def obtener_estado_cotizacion(solicitud):
    estado = (
        GestionEstadoCotizacion.objects
        .filter(solicitud=solicitud)
        .order_by('-fecha_cambio')
        .first()
    )

    if estado:
        return estado.estado

    return EstadoCotizacion.PENDIENTE


def obtener_estado_cotizacion_display(solicitud):
    estado = (
        GestionEstadoCotizacion.objects
        .filter(solicitud=solicitud)
        .order_by('-fecha_cambio')
        .first()
    )

    if estado:
        return estado.get_estado_display()

    return 'Pendiente'