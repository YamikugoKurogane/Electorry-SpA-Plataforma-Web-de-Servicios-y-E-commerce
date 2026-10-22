from datetime import date

from django.http import HttpResponse
from django.shortcuts import render

from apps.core.permisos import SOLO_ADMIN, rol_requerido

from . import services


def _fecha(valor):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


@rol_requerido(*SOLO_ADMIN)
def reporte(request):
    desde, hasta, inicio, fin = services.rango_fechas(_fecha(request.GET.get("desde")), _fecha(request.GET.get("hasta")))
    if desde > hasta:
        desde, hasta, inicio, fin = services.rango_fechas(hasta, desde)
    exportar = request.GET.get("exportar")
    if exportar in ("solicitudes", "cotizaciones"):
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="{exportar}_{desde}_{hasta}.csv"'
        respuesta.write("\ufeff")  # BOM para que Excel respete los acentos
        (services.csv_solicitudes if exportar == "solicitudes" else services.csv_cotizaciones)(inicio, fin, respuesta)
        return respuesta
    solicitudes = services.resumen_solicitudes(inicio, fin)
    maximo = max([n for _, n in solicitudes["por_estado"]] or [1]) or 1
    return render(
        request,
        "reportes/reporte.html",
        {
            "desde": desde, "hasta": hasta, "solicitudes": solicitudes, "maximo": maximo,
            "cotizaciones": services.resumen_cotizaciones(inicio, fin),
            "ventas": services.resumen_ventas(inicio, fin),
        },
    )
