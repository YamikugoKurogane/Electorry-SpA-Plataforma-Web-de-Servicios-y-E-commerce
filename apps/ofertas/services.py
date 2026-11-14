"""Reglas de negocio de ofertas (RF-16, RF-17, HU-06, HU-12, HU-17).

Regla de precios: si varias ofertas vigentes afectan a un mismo producto, se aplica solo la de MAYOR descuento
(los descuentos no se acumulan). El precio con oferta se calcula siempre en el servidor.
"""
import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.auditoria import services as auditoria

from .models import DESCUENTO_MAXIMO, Oferta

log = logging.getLogger("electorry.ofertas")


class OfertaError(Exception):
    pass


@dataclass(frozen=True)
class PrecioVigente:
    precio: int  # lo que se cobra (con oferta si corresponde)
    precio_lista: int  # precio publicado sin oferta
    descuento: int = 0
    oferta: object = None

    @property
    def con_oferta(self):
        return self.oferta is not None and self.precio < self.precio_lista


def precio_con_descuento(precio_lista, descuento):
    """Pesos enteros, redondeando al más cercano; nunca baja de $1."""
    valor = Decimal(precio_lista) * Decimal(100 - descuento) / Decimal(100)
    return max(1, int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _ve_exclusivas(usuario):
    return usuario is not None and getattr(usuario, "is_authenticated", False)


def ofertas_vigentes(usuario=None, hoy=None):
    """Ofertas vigentes que corresponden a quien mira (los visitantes no ven las exclusivas para clientes)."""
    qs = Oferta.objects.vigentes(hoy)
    return qs if _ve_exclusivas(usuario) else qs.filter(solo_clientes=False)


def _mejor(actual, candidata):
    return candidata if actual is None or (candidata.descuento, -candidata.pk) > (actual.descuento, -actual.pk) else actual


def precios_vigentes(productos, usuario=None, hoy=None):
    """{producto_id: PrecioVigente} con UNA sola consulta para toda la lista (sin N+1)."""
    productos = list(productos)
    resultado = {p.pk: PrecioVigente(p.precio, p.precio) for p in productos}
    if not productos:
        return resultado
    filas = Oferta.productos.through.objects.filter(
        producto_id__in=list(resultado), oferta__in=ofertas_vigentes(usuario, hoy)
    ).select_related("oferta")
    mejor = {}
    for fila in filas:
        mejor[fila.producto_id] = _mejor(mejor.get(fila.producto_id), fila.oferta)
    for p in productos:
        o = mejor.get(p.pk)
        if o:
            resultado[p.pk] = PrecioVigente(precio_con_descuento(p.precio, o.descuento), p.precio, o.descuento, o)
    return resultado


def precio_vigente(producto, usuario=None, hoy=None):
    return precios_vigentes([producto], usuario, hoy)[producto.pk]


def anotar_precios(productos, usuario=None):
    """Deja el precio vigente en `producto.pv` para que las plantillas lo muestren. Devuelve la lista."""
    productos = list(productos)
    precios = precios_vigentes(productos, usuario)
    for p in productos:
        p.pv = precios[p.pk]
    return productos


def ofertas_de_servicios(servicios, usuario=None, hoy=None):
    """{servicio_id: Oferta} con la mejor oferta vigente de cada servicio (una consulta)."""
    ids = [s.pk for s in servicios]
    if not ids:
        return {}
    filas = Oferta.servicios.through.objects.filter(
        servicio_id__in=ids, oferta__in=ofertas_vigentes(usuario, hoy)
    ).select_related("oferta")
    mejor = {}
    for fila in filas:
        mejor[fila.servicio_id] = _mejor(mejor.get(fila.servicio_id), fila.oferta)
    return mejor


def anotar_ofertas_servicios(servicios, usuario=None):
    servicios = list(servicios)
    ofertas = ofertas_de_servicios(servicios, usuario)
    for s in servicios:
        s.oferta_vigente = ofertas.get(s.pk)
    return servicios


def descripcion_oferta(oferta):
    return f"«{oferta.titulo}»: {oferta.descuento} % de descuento, vigente hasta {oferta.fecha_fin:%d-%m-%Y}"


# ---------------------------------------------------------------- administración (RF-16)


def validar_oferta(datos, productos, servicios, *, hoy=None, oferta=None):
    """Devuelve la lista de problemas (vacía si todo está bien). La usa el formulario y el servicio."""
    hoy = hoy or timezone.localdate()
    problemas = []
    if not (datos.get("titulo") or "").strip():
        problemas.append("El título es obligatorio.")
    d = datos.get("descuento")
    if d is None or not (1 <= int(d) <= DESCUENTO_MAXIMO):
        problemas.append(f"El descuento debe estar entre 1 % y {DESCUENTO_MAXIMO} %.")
    ini, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
    if not ini or not fin:
        problemas.append("Indica la fecha de inicio y la de término.")
    else:
        if fin < ini:
            problemas.append("La fecha de término no puede ser anterior a la de inicio.")
        elif fin < hoy and (oferta is None or oferta.fecha_fin != fin):
            problemas.append("La fecha de término no puede estar en el pasado.")
    if not productos and not servicios:
        problemas.append("Elige al menos un producto o un servicio al que se aplique la oferta.")
    return problemas


def _datos_de_oferta(oferta):
    return {
        "titulo": oferta.titulo, "descuento": oferta.descuento, "fecha_inicio": oferta.fecha_inicio, "fecha_fin": oferta.fecha_fin,
        "solo_clientes": oferta.solo_clientes,
        "productos": sorted(oferta.productos.values_list("pk", flat=True)), "servicios": sorted(oferta.servicios.values_list("pk", flat=True)),
    }


@transaction.atomic
def crear_oferta(*, usuario, datos, productos=(), servicios=(), request=None):
    productos, servicios = list(productos), list(servicios)
    problemas = validar_oferta(datos, productos, servicios)
    if problemas:
        raise OfertaError(" ".join(problemas))
    oferta = Oferta.objects.create(creada_por=usuario, **datos)
    oferta.productos.set(productos)
    oferta.servicios.set(servicios)
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CREAR, entidad="oferta", entidad_id=oferta.pk,
        descripcion=descripcion_oferta(oferta), despues=_datos_de_oferta(oferta), request=request,
    )
    return oferta


@transaction.atomic
def actualizar_oferta(oferta, *, usuario, datos, productos=(), servicios=(), request=None):
    oferta = Oferta.objects.select_for_update().get(pk=oferta.pk)
    if not oferta.editable:
        raise OfertaError("Una oferta finalizada no se puede editar. Crea una nueva.")
    productos, servicios = list(productos), list(servicios)
    problemas = validar_oferta(datos, productos, servicios, oferta=oferta)
    if problemas:
        raise OfertaError(" ".join(problemas))
    antes = _datos_de_oferta(oferta)
    for campo, valor in datos.items():
        setattr(oferta, campo, valor)
    oferta.save()
    oferta.productos.set(productos)
    oferta.servicios.set(servicios)
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.EDITAR, entidad="oferta", entidad_id=oferta.pk,
        descripcion=descripcion_oferta(oferta), antes=antes, despues=_datos_de_oferta(oferta), request=request,
    )
    return oferta


@transaction.atomic
def finalizar_oferta(oferta_id, usuario, request=None):
    """Termina la oferta de inmediato (sin esperar su fecha de término). No se puede deshacer."""
    oferta = Oferta.objects.select_for_update().get(pk=oferta_id)
    if oferta.finalizada_en:
        raise OfertaError("La oferta ya estaba finalizada.")
    estado_antes = oferta.estado
    oferta.finalizada_en = timezone.now()
    oferta.save(update_fields=["finalizada_en", "actualizada"])
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CAMBIO_ESTADO, entidad="oferta", entidad_id=oferta.pk,
        descripcion=f"Oferta finalizada: {descripcion_oferta(oferta)}", antes={"estado": estado_antes}, despues={"estado": "FINALIZADA"}, request=request,
    )
    return oferta
