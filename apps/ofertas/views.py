from django.core.paginator import Paginator
from django.shortcuts import render

from apps.tienda.models import Producto

from . import services


def lista(request):
    """RF-17 / HU-06: ofertas vigentes que le corresponden a quien mira."""
    usuario = request.user
    qs = services.ofertas_vigentes(usuario).prefetch_related("productos__categoria", "servicios").order_by("-descuento", "fecha_fin", "id")
    pagina = Paginator(qs, 9).get_page(request.GET.get("pagina"))
    ofertas = list(pagina.object_list)
    pagina.object_list = ofertas
    # precios de todos los productos de la página en una sola consulta
    productos = {p.pk: p for o in ofertas for p in o.productos.all()}
    precios = services.precios_vigentes(productos.values(), usuario)
    for o in ofertas:
        o.productos_con_precio = [(p, precios[p.pk]) for p in o.productos.all() if p.activo and p.categoria.activa]
        o.servicios_activos = [s for s in o.servicios.all() if s.disponible]
    ocultas = 0
    if not usuario.is_authenticated:
        ocultas = services.Oferta.objects.vigentes().filter(solo_clientes=True).count()
    return render(request, "ofertas/lista.html", {"pagina": pagina, "ofertas_exclusivas_ocultas": ocultas})
