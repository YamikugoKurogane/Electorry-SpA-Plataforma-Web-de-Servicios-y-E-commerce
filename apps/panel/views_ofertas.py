"""Gestión de ofertas para el administrador (RF-16, HU-12, HU-17)."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.permisos import SOLO_ADMIN, rol_requerido
from apps.ofertas import services
from apps.ofertas.forms import OfertaForm
from apps.ofertas.models import EstadoOferta, Oferta


@rol_requerido(*SOLO_ADMIN)
def ofertas_lista(request):
    hoy = timezone.localdate()
    qs = Oferta.objects.annotate(n_productos=Count("productos", distinct=True), n_servicios=Count("servicios", distinct=True))
    estado = request.GET.get("estado", "")
    q = request.GET.get("q", "").strip()
    filtros = {
        EstadoOferta.VIGENTE: Q(finalizada_en__isnull=True, fecha_inicio__lte=hoy, fecha_fin__gte=hoy),
        EstadoOferta.PROGRAMADA: Q(finalizada_en__isnull=True, fecha_inicio__gt=hoy),
        EstadoOferta.VENCIDA: Q(finalizada_en__isnull=True, fecha_fin__lt=hoy),
        EstadoOferta.FINALIZADA: Q(finalizada_en__isnull=False),
    }
    if estado in filtros:
        qs = qs.filter(filtros[estado])
    else:
        estado = ""
    if q:
        qs = qs.filter(titulo__icontains=q)
    pagina = Paginator(qs, 20).get_page(request.GET.get("pagina"))
    return render(request, "panel/ofertas_lista.html", {
        "seccion": "ofertas", "pagina": pagina, "estados": EstadoOferta.choices, "estado": estado, "q": q, "hoy": hoy,
    })


def _guardar(request, oferta=None):
    form = OfertaForm(request.POST or None, instance=oferta)
    if request.method == "POST" and form.is_valid():
        args = dict(
            usuario=request.user, datos=form.datos(), productos=form.cleaned_data["productos"],
            servicios=form.cleaned_data["servicios"], request=request,
        )
        try:
            if oferta is None:
                nueva = services.crear_oferta(**args)
            else:
                nueva = services.actualizar_oferta(oferta, **args)
        except services.OfertaError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Oferta guardada." if oferta else f"Oferta «{nueva.titulo}» creada.")
            return redirect("panel:ofertas")
    return render(request, "panel/oferta_form.html", {"seccion": "ofertas", "form": form, "oferta": oferta})


@rol_requerido(*SOLO_ADMIN)
def oferta_crear(request):
    return _guardar(request)


@rol_requerido(*SOLO_ADMIN)
def oferta_editar(request, pk):
    oferta = get_object_or_404(Oferta, pk=pk)
    if not oferta.editable:
        messages.error(request, "Una oferta finalizada no se puede editar. Crea una nueva.")
        return redirect("panel:ofertas")
    return _guardar(request, oferta)


@require_POST
@rol_requerido(*SOLO_ADMIN)
def oferta_finalizar(request, pk):
    get_object_or_404(Oferta, pk=pk)
    try:
        oferta = services.finalizar_oferta(pk, request.user, request)
        messages.success(request, f"La oferta «{oferta.titulo}» fue finalizada: ya no se aplica ni se muestra a los clientes.")
    except services.OfertaError as exc:
        messages.error(request, str(exc))
    return redirect("panel:ofertas")
