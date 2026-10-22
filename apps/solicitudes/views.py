from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.permisos import SOLO_CLIENTE, TODOS_AUTENTICADOS, rol_requerido

from . import services
from .forms import SolicitudForm
from .models import Adjunto


@rol_requerido(*SOLO_CLIENTE)
def crear(request):
    inicial = {}
    if request.GET.get("servicio", "").isdigit():
        inicial["servicio"] = int(request.GET["servicio"])
    form = SolicitudForm(request.POST or None, request.FILES or None, usuario=request.user, initial=inicial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        solicitud = services.crear_solicitud(
            cliente=request.user, servicio=d["servicio"], datos=d, archivos=d["archivos"], request=request
        )
        messages.success(request, f"¡Listo! Tu solicitud {solicitud.codigo} fue enviada. Te avisaremos por correo.")
        return redirect(solicitud)
    return render(request, "solicitudes/crear.html", {"form": form})


@rol_requerido(*SOLO_CLIENTE)
def mis_solicitudes(request):
    qs = services.solicitudes_visibles_para(request.user).select_related("servicio")
    pagina = Paginator(qs, 10).get_page(request.GET.get("pagina"))
    return render(request, "solicitudes/mis_solicitudes.html", {"pagina": pagina})


@rol_requerido(*TODOS_AUTENTICADOS)
def detalle(request, pk):
    solicitud = services.obtener_solicitud_para(request.user, pk, request)
    cotizaciones = solicitud.cotizaciones.prefetch_related("lineas").order_by("-creada")
    if request.user.es_cliente:  # el cliente no ve borradores
        cotizaciones = cotizaciones.exclude(estado="BORRADOR")
    return render(
        request,
        "solicitudes/detalle.html",
        {
            "solicitud": solicitud,
            "historial": solicitud.historial.all(),
            "adjuntos": solicitud.adjuntos.all(),
            "cotizaciones": cotizaciones,
        },
    )


@rol_requerido(*TODOS_AUTENTICADOS)
def descargar_adjunto(request, pk):
    """Los adjuntos solo se entregan al propietario o al personal (nunca como archivo estático)."""
    adjunto = get_object_or_404(Adjunto, pk=pk)
    services.obtener_solicitud_para(request.user, adjunto.solicitud_id, request)
    try:
        f = adjunto.archivo.open("rb")
    except FileNotFoundError:
        raise Http404("Archivo no disponible.")
    respuesta = FileResponse(f, as_attachment=False, filename=adjunto.nombre_original)
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
    return respuesta
