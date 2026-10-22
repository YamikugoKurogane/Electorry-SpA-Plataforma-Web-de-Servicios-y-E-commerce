from django.conf import settings


def sitio(request):
    carrito_items = 0
    carrito = request.session.get("carrito") if hasattr(request, "session") else None
    if carrito:
        carrito_items = sum(int(c) for c in carrito.values())
    return {
        "EMPRESA": settings.EMPRESA,
        "IVA": settings.IVA_PORCENTAJE,
        "carrito_items": carrito_items,
    }
