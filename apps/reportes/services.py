"""Reportes básicos de solicitudes y cotizaciones (RF-09, HU-12)."""
import csv
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
from apps.solicitudes.models import Estado, SolicitudCotizacion
from apps.tienda.models import EstadoVenta, Venta


def rango_fechas(desde=None, hasta=None):
    """Devuelve (inicio, fin) como datetimes aware. Por defecto, los últimos 90 días."""
    hoy = timezone.localdate()
    hasta = hasta or hoy
    desde = desde or (hoy - timedelta(days=90))
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(desde, time.min), tz)
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min), tz)
    return desde, hasta, inicio, fin


def _con_iva(neto):
    v = Decimal(neto) * (Decimal(100 + settings.IVA_PORCENTAJE) / Decimal(100))
    return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def resumen_solicitudes(inicio, fin):
    qs = SolicitudCotizacion.objects.filter(creada__gte=inicio, creada__lt=fin)
    por_estado = {e: 0 for e, _ in Estado.choices}
    for fila in qs.values("estado").annotate(n=Count("id")):
        por_estado[fila["estado"]] = fila["n"]
    por_servicio = list(qs.values("servicio__nombre").annotate(n=Count("id")).order_by("-n", "servicio__nombre")[:10])
    por_mes = list(qs.annotate(mes=TruncMonth("creada")).values("mes").annotate(n=Count("id")).order_by("mes"))
    return {
        "total": sum(por_estado.values()),
        "por_estado": [(Estado(e).label, n) for e, n in por_estado.items()],
        "por_servicio": [(f["servicio__nombre"], f["n"]) for f in por_servicio],
        "por_mes": [(f["mes"].strftime("%Y-%m"), f["n"]) for f in por_mes],
    }


def resumen_cotizaciones(inicio, fin):
    qs = Cotizacion.objects.filter(creada__gte=inicio, creada__lt=fin)
    filas = qs.values("estado").annotate(n=Count("id", distinct=True), neto=Sum(F("lineas__cantidad") * F("lineas__precio_unitario")))
    datos = {e: {"n": 0, "neto": 0} for e, _ in EstadoCotizacion.choices}
    for f in filas:
        datos[f["estado"]] = {"n": f["n"], "neto": f["neto"] or 0}
    aceptadas, rechazadas = datos["ACEPTADA"]["n"], datos["RECHAZADA"]["n"]
    respondidas = aceptadas + rechazadas
    return {
        "por_estado": [(EstadoCotizacion(e).label, d["n"], d["neto"], _con_iva(d["neto"])) for e, d in datos.items()],
        "total": sum(d["n"] for d in datos.values()),
        "monto_aceptado_neto": datos["ACEPTADA"]["neto"],
        "monto_aceptado_total": _con_iva(datos["ACEPTADA"]["neto"]),
        "tasa_aceptacion": round(100 * aceptadas / respondidas) if respondidas else None,
    }


def resumen_ventas(inicio, fin):
    qs = Venta.objects.filter(creada__gte=inicio, creada__lt=fin)
    por_estado = {e: {"n": 0, "monto": 0} for e, _ in EstadoVenta.choices}
    for f in qs.values("estado").annotate(n=Count("id"), monto=Sum("total")):
        por_estado[f["estado"]] = {"n": f["n"], "monto": f["monto"] or 0}
    return {
        "por_estado": [(EstadoVenta(e).label, d["n"], d["monto"]) for e, d in por_estado.items()],
        "ingresos": por_estado["PAGADA"]["monto"],
    }


def csv_solicitudes(inicio, fin, escritor):
    w = csv.writer(escritor)
    w.writerow(["codigo", "fecha", "cliente", "servicio", "estado", "direccion"])
    for s in SolicitudCotizacion.objects.filter(creada__gte=inicio, creada__lt=fin).select_related("cliente", "servicio").iterator():
        w.writerow([s.codigo, timezone.localtime(s.creada).strftime("%Y-%m-%d %H:%M"), s.nombre_contacto, s.servicio.nombre, s.get_estado_display(), s.direccion])


def csv_cotizaciones(inicio, fin, escritor):
    w = csv.writer(escritor)
    w.writerow(["codigo", "fecha", "solicitud", "estado", "neto", "iva", "total"])
    qs = Cotizacion.objects.filter(creada__gte=inicio, creada__lt=fin).select_related("solicitud").prefetch_related("lineas")
    for c in qs.iterator(chunk_size=200):
        w.writerow([c.codigo, timezone.localtime(c.creada).strftime("%Y-%m-%d %H:%M"), c.solicitud.codigo, c.get_estado_display(), c.neto, c.iva, c.total])
