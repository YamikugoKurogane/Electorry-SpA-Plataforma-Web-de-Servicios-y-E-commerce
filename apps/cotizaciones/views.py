from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.tienda.models import Venta, DetalleVenta, Producto
from apps.pagos.gateways import obtener_pasarela
from apps.pagos.gateways.base import OrdenPago
from .models import Cotizacion, EstadoCotizacion


from apps.core.permisos import SOLO_CLIENTE, TODOS_AUTENTICADOS, rol_requerido
from apps.solicitudes.services import obtener_solicitud_para

from . import services


@rol_requerido(*TODOS_AUTENTICADOS)
def detalle(request, pk):
    """Vista imprimible de una cotización. El cliente solo ve las suyas y no los borradores."""
    cot = get_object_or_404(Cotizacion.objects.select_related("solicitud__servicio").prefetch_related("lineas", "solicitud__items"), pk=pk)
    obtener_solicitud_para(request.user, cot.solicitud_id, request)
    if request.user.es_cliente and cot.estado == "BORRADOR":
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)
    return render(request, "cotizaciones/detalle.html", {"cot": cot})


@require_POST
@rol_requerido(*SOLO_CLIENTE)
def responder(request, pk):
    cot = get_object_or_404(Cotizacion.objects.select_related("solicitud"), pk=pk)
    obtener_solicitud_para(request.user, cot.solicitud_id, request)  # autorización por objeto
    accion = request.POST.get("accion")
    if accion not in ("aceptar", "rechazar"):  # nunca asumir una acción destructiva por defecto
        messages.error(request, "No pudimos registrar tu respuesta. Intenta nuevamente.")
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)
    aceptar = accion == "aceptar"
    try:
        services.responder_cotizacion(cot, request.user, aceptar, request)
        messages.success(request, "Cotización aceptada. ¡Gracias! Nos pondremos en contacto." if aceptar else "Cotización rechazada. Revisaremos tu caso.")
    except services.CotizacionError as exc:
        messages.error(request, str(exc))
    return redirect("solicitudes:detalle", pk=cot.solicitud_id)
@rol_requerido(*SOLO_CLIENTE)
def pagar_cotizacion(request, pk):
    """Crea una venta desde una cotización aceptada e inicia el pago."""
    cot = get_object_or_404(Cotizacion.objects.select_related("solicitud"), pk=pk, estado=EstadoCotizacion.ACEPTADA)
    obtener_solicitud_para(request.user, cot.solicitud_id, request)  # Seguridad: solo el dueño

    if cot.venta:
        messages.info(request, "Esta cotización ya tiene una venta asociada.")
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)

    # Crear la venta (usando el estado correcto: PENDIENTE_PAGO)
    venta = Venta.objects.create(
        cliente=request.user,
        total=cot.total,
        estado='PENDIENTE_PAGO',
        nombre_cliente=request.user.get_full_name() or request.user.username
    )
    
    # Crear o buscar un producto "fantasma" para la cotización
    producto_fantasma, _ = Producto.objects.get_or_create(
        nombre="Servicio de Cotización",
        defaults={'precio': 1, 'categoria_id': 1} 
    )

    for linea in cot.lineas.all():
        DetalleVenta.objects.create(
            venta=venta,
            producto=producto_fantasma,
            nombre_producto=linea.descripcion,
            cantidad=linea.cantidad,
            precio_unitario=linea.precio_unitario
        )
    
    cot.venta = venta
    cot.save()

    # Iniciar pago
    pasarela = obtener_pasarela()
    orden = OrdenPago(
        orden_compra=str(venta.id),
        monto=cot.total,
        sesion=request.session.session_key
    )
    
    try:
        inicio = pasarela.iniciar(orden, url_retorno=request.build_absolute_uri('/pagos/retorno/'))
        return redirect(inicio.url)
    except Exception as e:
        messages.error(request, f"Error con la pasarela: {e}")
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)

    # Crear la venta
    venta = Venta.objects.create(
        cliente=request.user,
        total=cot.total,
        estado='PENDIENTE'  # Verifica que este sea un estado válido en tu modelo Venta
    )
    
    for linea in cot.lineas.all():
        DetalleVenta.objects.create(
            venta=venta,
            descripcion=linea.descripcion,
            cantidad=linea.cantidad,
            precio_unitario=linea.precio_unitario
        )
    
    cot.venta = venta
    cot.save()

    # Iniciar pago
    pasarela = obtener_pasarela()
    orden = OrdenPago(
        orden_compra=str(venta.id),
        monto=cot.total,
        sesion=request.session.session_key
    )
    
    try:
        inicio = pasarela.iniciar(orden, url_retorno=request.build_absolute_uri('/pagos/retorno/'))
        return redirect(inicio.url)
    except Exception as e:
        messages.error(request, f"Error con la pasarela: {e}")
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)
