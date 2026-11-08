from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permisos import SOLO_CLIENTE, TODOS_AUTENTICADOS, rol_requerido
from apps.tienda.carrito import Carrito
from apps.tienda.models import Producto

from . import services
from .forms import ItemFormSet, SolicitudForm, items_validos
from .models import Adjunto


def _items_iniciales(request):
    """Productos precargados: desde la ficha de un producto (?producto=ID) o desde el carrito (?desde=carrito)."""
    if request.GET.get("desde") == "carrito":
        return [{"producto": l["producto"].pk, "cantidad": l["cantidad"]} for l in Carrito(request).lineas()]
    pid = request.GET.get("producto", "")
    if pid.isdigit() and Producto.objects.filter(pk=int(pid), activo=True, categoria__activa=True).exists():
        return [{"producto": int(pid), "cantidad": 1}]
    return []


@rol_requerido(*SOLO_CLIENTE)
def crear(request):
    inicial = {}
    if request.GET.get("servicio", "").isdigit():
        inicial["servicio"] = int(request.GET["servicio"])
    if request.method == "POST":
        datos = request.POST
        if "items-TOTAL_FORMS" not in datos:  # envío sin la sección de productos
            datos = datos.copy()
            datos["items-TOTAL_FORMS"], datos["items-INITIAL_FORMS"] = "0", "0"
        form = SolicitudForm(datos, request.FILES, usuario=request.user)
        items_fs = ItemFormSet(datos, prefix="items")
        if form.is_valid() & items_fs.is_valid():  # & evalúa ambos: se muestran todos los errores a la vez
            d = form.cleaned_data
            try:
                solicitud = services.crear_solicitud(
                    cliente=request.user, servicio=d.get("servicio"), datos=d, archivos=d["archivos"],
                    items=items_validos(items_fs), request=request,
                )
            except services.SolicitudError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"¡Listo! Tu solicitud {solicitud.codigo} fue enviada. Te avisaremos por correo.")
                return redirect(solicitud)
    else:
        form = SolicitudForm(usuario=request.user, initial=inicial)
        items_fs = ItemFormSet(prefix="items", initial=_items_iniciales(request))
    return render(request, "solicitudes/crear.html", {"form": form, "items_fs": items_fs})


@rol_requerido(*SOLO_CLIENTE)
def mis_solicitudes(request):
    qs = services.solicitudes_visibles_para(request.user)
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
            "puede_cancelar": request.user.es_cliente and services.puede_cliente_cancelar(solicitud),
        },
    )


@require_POST
@rol_requerido(*SOLO_CLIENTE)
def cancelar(request, pk):
    solicitud = services.obtener_solicitud_para(request.user, pk, request)
    try:
        services.cancelar_solicitud_cliente(solicitud, request.user, request)
        messages.success(request, f"La solicitud {solicitud.codigo} fue cancelada.")
    except services.TransicionInvalida as exc:
        messages.error(request, str(exc))
    return redirect(solicitud)


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
