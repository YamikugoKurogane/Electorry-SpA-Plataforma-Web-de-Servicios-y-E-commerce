import logging

from django.db import transaction
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.core.utils import formatear_clp
from apps.notificaciones import services as notif

from .models import DetalleVenta, EstadoVenta, Producto, Venta

log = logging.getLogger("electorry.ventas")


class VentaError(Exception):
    pass


@transaction.atomic
def crear_venta(*, cliente, lineas, datos_entrega, request=None):
    """Crea la venta y su detalle de forma atómica (EC-02).

    El precio se toma SIEMPRE de la base de datos, nunca del navegador.
    """
    if not lineas:
        raise VentaError("Tu carrito está vacío.")
    ids = [l["producto"].pk for l in lineas]
    productos = {p.pk: p for p in Producto.objects.filter(pk__in=ids, activo=True, categoria__activa=True)}
    if len(productos) != len(set(ids)):
        raise VentaError("Alguno de los productos ya no está disponible. Revisa tu carrito.")
    venta = Venta.objects.create(
        cliente=cliente,
        nombre_cliente=datos_entrega["nombre_cliente"],
        direccion_entrega=datos_entrega["direccion_entrega"],
        telefono_contacto=datos_entrega["telefono_contacto"],
    )
    total = 0
    detalles = []
    for l in lineas:
        p = productos[l["producto"].pk]
        detalles.append(
            DetalleVenta(venta=venta, producto=p, nombre_producto=p.nombre, cantidad=l["cantidad"], precio_unitario=p.precio)
        )
        total += p.precio * l["cantidad"]
    DetalleVenta.objects.bulk_create(detalles)
    venta.total = total
    venta.save(update_fields=["total", "actualizada"])
    auditoria.registrar(
        usuario=cliente, accion=auditoria.Accion.CREAR, entidad="venta", entidad_id=venta.pk,
        descripcion=f"{venta.codigo} por {formatear_clp(total)}", despues={"estado": venta.estado, "total": total}, request=request,
    )
    return venta


@transaction.atomic
def marcar_pagada(venta_id, *, usuario=None, referencia="", request=None):
    """Idempotente: si ya está pagada no hace nada (reintentos seguros, EC-02)."""
    venta = Venta.objects.select_for_update().get(pk=venta_id)
    if venta.estado == EstadoVenta.PAGADA:
        return venta
    if venta.estado == EstadoVenta.CANCELADA:
        raise VentaError("La venta está cancelada.")
    venta.estado = EstadoVenta.PAGADA
    venta.pagada_en = timezone.now()
    venta.save(update_fields=["estado", "pagada_en", "actualizada"])
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.PAGO, entidad="venta", entidad_id=venta.pk,
        descripcion=f"{venta.codigo} pagada ({referencia or 'sin referencia'})",
        antes={"estado": EstadoVenta.PENDIENTE_PAGO}, despues={"estado": EstadoVenta.PAGADA}, request=request,
    )
    notif.notificar(
        venta.cliente.email,
        f"Pago confirmado: {venta.codigo}",
        f"Hola {venta.nombre_cliente or venta.cliente.first_name},\n\nConfirmamos el pago de tu compra {venta.codigo} "
        f"por {formatear_clp(venta.total)}. Te contactaremos para coordinar la entrega.\n\nElectorry SpA",
        evento="venta_pagada",
    )
    notif.notificar_interno(f"Nueva venta pagada {venta.codigo}", f"Total: {formatear_clp(venta.total)}", evento="venta_nueva")
    return venta


@transaction.atomic
def cancelar_venta(venta_id, usuario, request=None):
    venta = Venta.objects.select_for_update().get(pk=venta_id)
    if venta.estado != EstadoVenta.PENDIENTE_PAGO:
        raise VentaError("Solo se pueden cancelar ventas pendientes de pago.")
    venta.estado = EstadoVenta.CANCELADA
    venta.save(update_fields=["estado", "actualizada"])
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CAMBIO_ESTADO, entidad="venta", entidad_id=venta.pk,
        descripcion=f"{venta.codigo} cancelada", antes={"estado": EstadoVenta.PENDIENTE_PAGO}, despues={"estado": EstadoVenta.CANCELADA}, request=request,
    )
    return venta


def ventas_visibles_para(usuario):
    """Filtrado por propietario (S1)."""
    qs = Venta.objects.select_related("cliente")
    return qs if usuario.es_personal else qs.filter(cliente=usuario)
