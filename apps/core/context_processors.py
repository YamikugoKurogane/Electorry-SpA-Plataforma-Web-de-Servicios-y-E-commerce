from django.conf import settings


def sitio(request):
    carrito_items = 0
    carrito = request.session.get("carrito") if hasattr(request, "session") else None
    if carrito:
        carrito_items = sum(int(c) for c in carrito.values())
    from apps.core.models import ConfiguracionSitio

    empresa = dict(settings.EMPRESA)
    configuracion = ConfiguracionSitio.objects.filter(pk=1).values(
        "nombre", "eslogan", "email", "telefono", "whatsapp", "direccion", "titulo_inicio", "texto_inicio"
    ).first()
    if configuracion:
        empresa.update(configuracion)
    return {
        "EMPRESA": empresa,
        "IVA": settings.IVA_PORCENTAJE,
        "carrito_items": carrito_items,
    }
