from django.conf import settings


def ip_cliente(request):
    """IP del cliente. Solo confía en X-Forwarded-For si hay un proxy de confianza."""
    if settings.USE_X_FORWARDED_FOR:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def json_seguro(valor):
    """Convierte un valor a algo serializable en JSON (para auditoría)."""
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, (list, tuple, set)):
        return [json_seguro(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): json_seguro(v) for k, v in valor.items()}
    return str(valor)


def formatear_clp(valor):
    try:
        return "$" + f"{int(valor):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"
