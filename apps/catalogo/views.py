from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import CategoriaServicio, Servicio


def lista(request):
    qs = Servicio.objects.select_related("categoria").filter(categoria__activa=True)
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("categoria", "")
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(resumen__icontains=q) | Q(descripcion__icontains=q))
    if cat.isdigit():
        qs = qs.filter(categoria_id=int(cat))
    pagina = Paginator(qs, 9).get_page(request.GET.get("pagina"))
    return render(
        request,
        "catalogo/lista.html",
        {"pagina": pagina, "categorias": CategoriaServicio.objects.filter(activa=True), "q": q, "cat": cat},
    )


def detalle(request, slug):
    servicio = get_object_or_404(Servicio.objects.select_related("categoria"), slug=slug)
    return render(request, "catalogo/detalle.html", {"servicio": servicio})
