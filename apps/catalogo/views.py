from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.core.busqueda import filtrar_texto

from .models import CategoriaServicio, Servicio


def lista(request):
    qs = Servicio.objects.select_related("categoria").filter(categoria__activa=True)
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("categoria", "")
    qs = filtrar_texto(qs, ("nombre", "resumen", "descripcion"), q)
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
