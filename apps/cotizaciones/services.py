import logging

from django.db import transaction
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.core.utils import formatear_clp
from apps.notificaciones import services as notif
from apps.solicitudes import services as solicitudes
from apps.solicitudes.models import Estado

from .models import Cotizacion, EstadoCotizacion, LineaCotizacion

log = logging.getLogger("electorry.cotizaciones")


class CotizacionError(Exception):
    pass


def _guardar_lineas(cotizacion, lineas):
    cotizacion.lineas.all().delete()
    nuevas = [
        LineaCotizacion(cotizacion=cotizacion, descripcion=l["descripcion"], cantidad=l["cantidad"], precio_unitario=l["precio_unitario"])
        for l in lineas
    ]
    if not nuevas:
        raise CotizacionError("La cotización debe tener al menos una línea.")
    LineaCotizacion.objects.bulk_create(nuevas)


@transaction.atomic
def crear_cotizacion(*, solicitud, usuario, lineas, validez_hasta=None, observaciones="", request=None):
    if solicitud.estado in (Estado.CANCELADA, Estado.FINALIZADA):
        raise CotizacionError("No se puede cotizar una solicitud cancelada o finalizada.")
    cot = Cotizacion.objects.create(
        solicitud=solicitud, creada_por=usuario, validez_hasta=validez_hasta, observaciones=observaciones
    )
    _guardar_lineas(cot, lineas)
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CREAR, entidad="cotizacion", entidad_id=cot.pk,
        descripcion=f"{cot.codigo} para {solicitud.codigo}", despues={"lineas": len(lineas)}, request=request,
    )
    return cot


@transaction.atomic
def actualizar_cotizacion(cotizacion, *, usuario, lineas, validez_hasta=None, observaciones="", request=None):
    cotizacion = Cotizacion.objects.select_for_update().get(pk=cotizacion.pk)
    if not cotizacion.editable:
        raise CotizacionError("Solo se pueden editar cotizaciones en borrador.")
    antes = {"validez_hasta": cotizacion.validez_hasta, "observaciones": cotizacion.observaciones, "neto": cotizacion.neto}
    cotizacion.validez_hasta = validez_hasta
    cotizacion.observaciones = observaciones
    cotizacion.save()
    _guardar_lineas(cotizacion, lineas)
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.EDITAR, entidad="cotizacion", entidad_id=cotizacion.pk,
        descripcion=f"{cotizacion.codigo} editada", antes=antes,
        despues={"validez_hasta": validez_hasta, "observaciones": observaciones, "neto": cotizacion.neto}, request=request,
    )
    return cotizacion


@transaction.atomic
def enviar_cotizacion(cotizacion, usuario, request=None):
    """Envía la cotización al cliente y deja la solicitud en «Cotizada» (RF-08, RF-11)."""
    cotizacion = Cotizacion.objects.select_for_update().select_related("solicitud").get(pk=cotizacion.pk)
    if cotizacion.estado != EstadoCotizacion.BORRADOR:
        raise CotizacionError("Esta cotización ya fue enviada.")
    if not cotizacion.lineas.exists():
        raise CotizacionError("La cotización no tiene líneas.")
    solicitud = cotizacion.solicitud
    # Las cotizaciones anteriores vigentes quedan reemplazadas.
    Cotizacion.objects.filter(solicitud=solicitud, estado=EstadoCotizacion.ENVIADA).update(estado=EstadoCotizacion.REEMPLAZADA)
    cotizacion.estado = EstadoCotizacion.ENVIADA
    cotizacion.enviada_en = timezone.now()
    cotizacion.save()

    if solicitud.estado == Estado.PENDIENTE:
        solicitud = solicitudes.cambiar_estado(solicitud, Estado.EN_REVISION, usuario, "Revisión iniciada", request)
    if solicitud.estado == Estado.EN_REVISION:
        solicitudes.cambiar_estado(solicitud, Estado.COTIZADA, usuario, f"Se envió {cotizacion.codigo}", request)

    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.ENVIAR, entidad="cotizacion", entidad_id=cotizacion.pk,
        descripcion=f"{cotizacion.codigo} enviada a {solicitud.email_contacto}", request=request,
    )
    cot = Cotizacion.objects.prefetch_related("lineas").get(pk=cotizacion.pk)
    detalle = "\n".join(f"- {l.descripcion} x{l.cantidad}: {formatear_clp(l.subtotal)}" for l in cot.lineas.all())
    vigencia = f"\nVálida hasta: {cot.validez_hasta:%d-%m-%Y}" if cot.validez_hasta else ""
    notif.notificar(
        solicitud.email_contacto,
        f"Cotización {cot.codigo} para tu solicitud {solicitud.codigo}",
        f"Hola {solicitud.nombre_contacto},\n\nEsta es tu cotización:\n\n{detalle}\n\n"
        f"Neto: {formatear_clp(cot.neto)}\nIVA: {formatear_clp(cot.iva)}\nTotal: {formatear_clp(cot.total)}{vigencia}\n\n"
        f"Ingresa a tu cuenta para aceptarla o rechazarla.\n\nElectorry SpA",
        evento="cotizacion_enviada",
    )
    return cot


@transaction.atomic
def responder_cotizacion(cotizacion, cliente, aceptar, request=None):
    """El cliente acepta o rechaza una cotización enviada."""
    cotizacion = Cotizacion.objects.select_for_update().select_related("solicitud").get(pk=cotizacion.pk)
    if cotizacion.solicitud.cliente_id != cliente.pk:
        raise CotizacionError("No puedes responder esta cotización.")
    if cotizacion.estado != EstadoCotizacion.ENVIADA:
        raise CotizacionError("Esta cotización ya no está vigente.")
    if cotizacion.validez_hasta and cotizacion.validez_hasta < timezone.localdate():
        raise CotizacionError("Esta cotización venció. Solicita una nueva.")
    cotizacion.estado = EstadoCotizacion.ACEPTADA if aceptar else EstadoCotizacion.RECHAZADA
    cotizacion.respondida_en = timezone.now()
    cotizacion.save()
    solicitud = cotizacion.solicitud
    if aceptar:
        solicitudes.cambiar_estado(solicitud, Estado.ACEPTADA, cliente, f"Aceptó {cotizacion.codigo}", request)
    else:
        solicitudes.cambiar_estado(solicitud, Estado.EN_REVISION, cliente, f"Rechazó {cotizacion.codigo}", request)
    auditoria.registrar(
        usuario=cliente, accion=auditoria.Accion.CAMBIO_ESTADO, entidad="cotizacion", entidad_id=cotizacion.pk,
        descripcion=f"{cotizacion.codigo} {'aceptada' if aceptar else 'rechazada'}", request=request,
    )
    notif.notificar_interno(
        f"{cotizacion.codigo} {'aceptada' if aceptar else 'rechazada'}",
        f"El cliente {solicitud.nombre_contacto} {'aceptó' if aceptar else 'rechazó'} la cotización de {solicitud.codigo}.",
        evento="cotizacion_respondida",
    )
    return cotizacion
