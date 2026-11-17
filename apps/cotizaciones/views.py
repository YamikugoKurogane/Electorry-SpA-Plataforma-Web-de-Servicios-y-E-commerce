from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permisos import SOLO_CLIENTE, TODOS_AUTENTICADOS, rol_requerido
from apps.solicitudes.services import obtener_solicitud_para

from . import services
from .models import Cotizacion
from .pdf import generar_pdf


@rol_requerido(*TODOS_AUTENTICADOS)
def detalle(request, pk):
    """Vista imprimible de una cotización. El cliente solo ve las suyas y no los borradores."""
    cot = get_object_or_404(Cotizacion.objects.select_related("solicitud__servicio").prefetch_related("lineas", "solicitud__items"), pk=pk)
    obtener_solicitud_para(request.user, cot.solicitud_id, request)
    if request.user.es_cliente and cot.estado == "BORRADOR":
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)
    return render(request, "cotizaciones/detalle.html", {"cot": cot})


@rol_requerido(*TODOS_AUTENTICADOS)
def descargar_pdf(request, pk):
    """Descarga la cotización en PDF, generada en el servidor. Mismas reglas de acceso que la vista de detalle."""
    cot = get_object_or_404(Cotizacion.objects.select_related("solicitud__servicio").prefetch_related("lineas", "solicitud__items"), pk=pk)
    obtener_solicitud_para(request.user, cot.solicitud_id, request)
    if request.user.es_cliente and cot.estado == "BORRADOR":
        return redirect("solicitudes:detalle", pk=cot.solicitud_id)
    respuesta = HttpResponse(generar_pdf(cot), content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="{cot.codigo}.pdf"'
    respuesta["Cache-Control"] = "private, no-store"  # contiene datos personales y montos
    return respuesta


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
