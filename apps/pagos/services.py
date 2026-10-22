"""Flujo de pago desacoplado del proveedor (D5, EC-02, EC-03, EC-06).

Garantías:
- La venta existe y queda «pendiente de pago» antes de hablar con la pasarela.
- Una falla del proveedor no pierde el pedido: se puede reintentar.
- La confirmación es idempotente: confirmar dos veces no duplica nada.
"""
import logging

from django.db import transaction

from apps.auditoria import services as auditoria
from apps.tienda import services as ventas

from .gateways import obtener_pasarela
from .gateways.base import OrdenPago, PasarelaError
from .models import EstadoPago, Pago

log = logging.getLogger("electorry.pagos")


def iniciar_pago(venta, url_retorno, pasarela=None):
    """Crea un intento de pago y devuelve (pago, inicio) o (pago, None) si el proveedor falla."""
    if not venta.pagable:
        raise ventas.VentaError("Esta compra no admite pago.")
    pasarela = pasarela or obtener_pasarela()
    # 1) Se registra el intento ANTES de llamar al proveedor (queda auditable aunque falle).
    pago = Pago.objects.create(venta=venta, proveedor=pasarela.nombre, monto=venta.total)
    orden = OrdenPago(orden_compra=f"V{venta.pk}-P{pago.pk}", monto=venta.total, sesion=f"cli{venta.cliente_id}")
    # 2) Llamada externa FUERA de cualquier transacción, con timeout.
    try:
        inicio = pasarela.iniciar(orden, url_retorno)
    except PasarelaError as exc:
        log.error("Falla al iniciar pago %s: %s", pago.pk, exc)
        pago.estado = EstadoPago.ERROR
        pago.detalle = {"error": str(exc)[:300]}
        pago.save(update_fields=["estado", "detalle", "actualizado"])
        return pago, None
    pago.token = inicio.token
    pago.save(update_fields=["token", "actualizado"])
    return pago, inicio


def confirmar_pago(token, pasarela=None, cancelado=False, request=None):
    """Procesa el retorno del cliente. Idempotente. Devuelve el Pago o None si el token no existe."""
    pasarela = pasarela or obtener_pasarela()
    with transaction.atomic():
        pago = (
            Pago.objects.select_for_update().select_related("venta").filter(token=token, proveedor=pasarela.nombre).first()
        )
        if pago is None:
            return None
        if pago.final:  # reintento / doble clic / recarga de la página de retorno
            return pago
        if cancelado:
            pago.estado = EstadoPago.RECHAZADO
            pago.detalle = {"motivo": "anulado por el cliente"}
            pago.save(update_fields=["estado", "detalle", "actualizado"])
            _auditar(pago, request)
            return pago
        try:
            resultado = pasarela.confirmar(token)
        except PasarelaError as exc:
            log.error("Falla al confirmar pago %s: %s", pago.pk, exc)
            pago.detalle = {"error": str(exc)[:300]}
            pago.save(update_fields=["detalle", "actualizado"])
            return pago  # sigue INICIADO: el cliente puede reintentar la confirmación
        pago.detalle = resultado.detalle
        pago.referencia = resultado.referencia[:100]
        if resultado.aprobado:
            pago.estado = EstadoPago.APROBADO
            pago.save()
            ventas.marcar_pagada(pago.venta_id, referencia=f"{pago.proveedor}:{pago.referencia}", request=request)
        else:
            pago.estado = EstadoPago.RECHAZADO
            pago.save()
        _auditar(pago, request)
        return pago


def _auditar(pago, request):
    auditoria.registrar(
        usuario=pago.venta.cliente, accion=auditoria.Accion.PAGO, entidad="pago", entidad_id=pago.pk,
        descripcion=f"Pago {pago.pk} de {pago.venta.codigo}: {pago.estado}", despues={"estado": pago.estado, "proveedor": pago.proveedor}, request=request,
    )
