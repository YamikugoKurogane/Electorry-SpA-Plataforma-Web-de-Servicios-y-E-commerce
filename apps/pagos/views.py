from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.permisos import SOLO_CLIENTE, rol_requerido
from apps.tienda.models import Venta

from . import services
from .gateways import obtener_pasarela
from .gateways.sandbox import SandboxGateway
from .models import EstadoPago


@rol_requerido(*SOLO_CLIENTE)
@require_http_methods(["GET", "POST"])
def iniciar(request, venta_id):
    """Inicia (o reintenta) el pago. Solo el dueño de la venta (S1)."""
    venta = get_object_or_404(Venta, pk=venta_id, cliente=request.user)
    if not venta.pagable:
        messages.info(request, "Esta compra ya no admite pago.")
        return redirect("tienda:compra", pk=venta.pk)
    if request.method == "GET":
        return render(request, "pagos/confirmar.html", {"venta": venta})
    pago, inicio = services.iniciar_pago(venta, request.build_absolute_uri(reverse("pagos:retorno")))
    if inicio is None:
        messages.error(
            request,
            "No pudimos conectar con el medio de pago en este momento. Tu compra quedó guardada como pendiente de pago; puedes reintentar en unos minutos.",
        )
        return redirect("tienda:compra", pk=venta.pk)
    if inicio.metodo == "POST":
        return render(request, "pagos/redirigir.html", {"inicio": inicio})
    return redirect(inicio.url)


@csrf_exempt  # Webpay retorna con POST desde otro dominio; se valida con el token del proveedor.
@require_http_methods(["GET", "POST"])
def retorno(request):
    pasarela = obtener_pasarela()
    token, cancelado = pasarela.token_desde_request(request)
    if not token:
        messages.error(request, "No recibimos información del pago.")
        return redirect("tienda:mis_compras")
    pago = services.confirmar_pago(token, pasarela=pasarela, cancelado=cancelado, request=request)
    if pago is None:
        raise Http404("Pago no encontrado.")
    venta = pago.venta
    if pago.estado == EstadoPago.APROBADO:
        messages.success(request, f"¡Pago exitoso! Tu compra {venta.codigo} está confirmada.")
    elif pago.estado == EstadoPago.RECHAZADO:
        messages.error(request, "El pago fue rechazado o anulado. Tu compra sigue pendiente: puedes reintentar el pago.")
    else:
        messages.warning(request, "No pudimos confirmar el pago todavía. Si ya fue cobrado, no se perderá tu pedido; reintenta en unos minutos o contáctanos.")
    if request.user.is_authenticated and venta.cliente_id == request.user.pk:
        return redirect("tienda:compra", pk=venta.pk)
    return redirect("core:inicio")


@rol_requerido(*SOLO_CLIENTE)
def sandbox(request, token):
    """Pantalla simulada de la pasarela (solo disponible con el sandbox habilitado)."""
    try:
        obtener_pasarela("sandbox")
    except Exception:
        raise Http404
    if not SandboxGateway.existe(token):
        raise Http404
    if request.method == "POST":
        SandboxGateway.resolver(token, request.POST.get("resultado") == "aprobar")
        return redirect(f"{reverse('pagos:retorno')}?token_ws={token}")
    return render(request, "pagos/sandbox.html", {"token": token})
