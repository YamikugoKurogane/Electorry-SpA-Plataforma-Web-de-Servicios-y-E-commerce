from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

REGISTRO = {
    "sandbox": "apps.pagos.gateways.sandbox.SandboxGateway",
    "webpay": "apps.pagos.gateways.webpay.WebpayGateway",
    # "mercadopago": "apps.pagos.gateways.mercadopago.MercadoPagoGateway",  ← un archivo nuevo, nada más (EC-03)
}


def obtener_pasarela(nombre=None):
    nombre = nombre or settings.PAYMENT_GATEWAY
    ruta = REGISTRO.get(nombre)
    if not ruta:
        raise ImproperlyConfigured(f"Pasarela de pago desconocida: {nombre}")
    if nombre == "sandbox" and not settings.PAYMENT_SANDBOX_PERMITIDO:
        raise ImproperlyConfigured("La pasarela sandbox no está permitida en este entorno.")
    return import_string(ruta)()
