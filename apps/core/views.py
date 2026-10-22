import logging

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.catalogo.models import Servicio
from apps.tienda.models import Producto

log = logging.getLogger("electorry")


def inicio(request):
    servicios = Servicio.objects.select_related("categoria").filter(disponible=True, categoria__activa=True)[:6]
    productos = Producto.objects.select_related("categoria").filter(activo=True, categoria__activa=True).order_by("-creado")[:4]
    return render(request, "core/inicio.html", {"servicios": servicios, "productos": productos})


def privacidad(request):
    return render(request, "core/privacidad.html")


def salud(request):
    """Healthcheck para monitoreo y reinicio automático (R1)."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return JsonResponse({"estado": "ok"})
    except Exception:  # noqa: BLE001
        log.exception("Healthcheck: base de datos no disponible")
        return JsonResponse({"estado": "error"}, status=503)


# Páginas de error controladas (RNF-FIA-01)
def error_400(request, exception=None):
    return render(request, "400.html", status=400)


def error_403(request, exception=None):
    return render(request, "403.html", status=403)


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)
