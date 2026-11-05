"""Listado de pagos para el administrador (RF-36, S3-R2)."""
import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.permisos import SOLO_ADMIN, rol_requerido
from apps.core.utils import csv_seguro, fecha_o_none
from apps.pagos.models import EstadoPago, Pago


def _filtrar(request):
    """Aplica los filtros GET. Devuelve (queryset, filtros_usados)."""
    qs = Pago.objects.select_related("venta__cliente")
    estado = request.GET.get("estado", "")
    proveedor = request.GET.get("proveedor", "")
    q = request.GET.get("q", "").strip()
    desde = fecha_o_none(request.GET.get("desde"))
    hasta = fecha_o_none(request.GET.get("hasta"))
    if desde and hasta and desde > hasta:
        desde, hasta = hasta, desde
        messages.info(request, "Las fechas estaban invertidas; las ordenamos por ti.")
    if estado in dict(EstadoPago.choices):
        qs = qs.filter(estado=estado)
    else:
        estado = ""
    if proveedor:
        qs = qs.filter(proveedor=proveedor)
    if desde:
        qs = qs.filter(creado__date__gte=desde)
    if hasta:
        qs = qs.filter(creado__date__lte=hasta)
    if q:
        cond = Q(venta__cliente__email__icontains=q) | Q(venta__nombre_cliente__icontains=q) | Q(referencia__icontains=q)
        numero = q.upper().removeprefix("VTA-").lstrip("0") or "0"
        if numero.isdigit():
            cond |= Q(venta_id=int(numero))
        qs = qs.filter(cond)
    return qs, {"estado": estado, "proveedor": proveedor, "q": q, "desde": desde, "hasta": hasta}


@rol_requerido(*SOLO_ADMIN)
def pagos_lista(request):
    qs, filtros = _filtrar(request)

    if request.GET.get("exportar") == "csv":
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = f'attachment; filename="pagos_{timezone.localdate()}.csv"'
        respuesta.write("\ufeff")  # BOM: Excel respeta los acentos
        w = csv.writer(respuesta)
        w.writerow(["id", "fecha", "venta", "cliente", "proveedor", "estado", "monto", "referencia"])
        for p in qs.iterator(chunk_size=500):
            w.writerow([csv_seguro(x) for x in (
                p.pk, timezone.localtime(p.creado).strftime("%Y-%m-%d %H:%M"), p.venta.codigo, p.venta.cliente.email,
                p.proveedor, p.get_estado_display(), p.monto, p.referencia)])
        return respuesta

    # order_by() vacío: sin él, el orden por defecto entra al GROUP BY y rompe los totales.
    conteos = {f["estado"]: f["n"] for f in qs.order_by().values("estado").annotate(n=Count("id"))}
    monto_aprobado = qs.filter(estado=EstadoPago.APROBADO).order_by().aggregate(t=Sum("monto"))["t"] or 0
    pagina = Paginator(qs, 25).get_page(request.GET.get("pagina"))
    return render(request, "panel/pagos_lista.html", {
        "seccion": "pagos", "pagina": pagina, "estados": EstadoPago.choices,
        "proveedores": Pago.objects.order_by().values_list("proveedor", flat=True).distinct().order_by("proveedor"),
        "total": sum(conteos.values()), "monto_aprobado": monto_aprobado,
        "resumen": [(label, conteos.get(valor, 0), valor) for valor, label in EstadoPago.choices],
        "estado": filtros["estado"], "proveedor": filtros["proveedor"], "q": filtros["q"],
        "desde": filtros["desde"].isoformat() if filtros["desde"] else "",
        "hasta": filtros["hasta"].isoformat() if filtros["hasta"] else "",
    })
