"""Pasarela simulada para desarrollo, staging y pruebas. NO usar en producción.

Sin estado en memoria: la decisión del «cliente» se guarda en la tabla de pagos,
así funciona con varios workers de Gunicorn.
"""
import secrets

from django.urls import reverse

from .base import InicioPago, OrdenPago, PasarelaPago, ResultadoPago


class SandboxGateway(PasarelaPago):
    nombre = "sandbox"

    def iniciar(self, orden: OrdenPago, url_retorno: str) -> InicioPago:
        token = secrets.token_urlsafe(24)
        return InicioPago(token=token, url=reverse("pagos:sandbox", kwargs={"token": token}))

    def confirmar(self, token: str) -> ResultadoPago:
        from apps.pagos.models import Pago

        pago = Pago.objects.filter(proveedor=self.nombre, token=token).first()
        decision = (pago.detalle or {}).get("sandbox") if pago else None
        if decision not in ("aprobar", "rechazar"):
            return ResultadoPago(aprobado=False, detalle={"motivo": "sin autorización del cliente"})
        return ResultadoPago(aprobado=decision == "aprobar", referencia=f"SBX-{token[:8].upper()}", detalle={"sandbox": decision})

    def token_desde_request(self, request):
        data = request.POST if request.method == "POST" else request.GET
        return data.get("token_ws", ""), False

    @classmethod
    def resolver(cls, token, aprobar):
        from apps.pagos.models import Pago

        actualizados = Pago.objects.filter(proveedor=cls.nombre, token=token).update(
            detalle={"sandbox": "aprobar" if aprobar else "rechazar"}
        )
        return bool(actualizados)

    @classmethod
    def existe(cls, token):
        from apps.pagos.models import Pago

        return Pago.objects.filter(proveedor=cls.nombre, token=token).exists()
