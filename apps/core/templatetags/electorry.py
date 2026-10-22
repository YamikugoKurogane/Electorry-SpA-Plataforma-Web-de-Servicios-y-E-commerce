from django import template

from apps.core.utils import formatear_clp

register = template.Library()


@register.filter
def clp(valor):
    return formatear_clp(valor)


@register.filter
def attr(objeto, nombre):
    """Obtiene un atributo (o llama a un método sin argumentos) por nombre."""
    valor = getattr(objeto, nombre, "")
    if callable(valor):
        valor = valor()
    return valor


@register.filter
def estado_css(valor):
    return str(valor).lower().replace("_", "-")


@register.simple_tag(takes_context=True)
def qs_sin_pagina(context, **extra):
    """Mantiene los filtros GET al cambiar de página."""
    params = context["request"].GET.copy()
    params.pop("pagina", None)
    for k, v in extra.items():
        params[k] = v
    return params.urlencode()


@register.filter
def celda(objeto, campo):
    """Valor de una columna de tabla genérica: booleanos como Sí/No y precios en CLP."""
    valor = attr(objeto, campo)
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if campo in ("precio", "total") and valor not in ("", None):
        return formatear_clp(valor)
    return valor
