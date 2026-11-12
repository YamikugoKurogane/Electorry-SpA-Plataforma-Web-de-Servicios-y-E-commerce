"""Adaptador Mercado Pago Checkout Pro (Sandbox/Producción)."""
import json
import urllib.error
import urllib.request
from django.conf import settings
from .base import InicioPago, OrdenPago, PasarelaError, PasarelaPago, ResultadoPago

API_URL = "https://api.mercadopago.com"

class MercadoPagoGateway(PasarelaPago):
    nombre = "mercadopago"

    def _llamar(self, metodo, ruta, cuerpo=None):
        url = API_URL.rstrip("/") + ruta
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
        
        req = urllib.request.Request(
            url, data=datos, method=metodo,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=settings.PAYMENT_TIMEOUT) as resp:
                return json.loads(resp.read().decode() or "{}")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise PasarelaError(f"Mercado Pago no respondió correctamente: {exc}") from exc

    def iniciar(self, orden: OrdenPago, url_retorno: str) -> InicioPago:
        resp = self._llamar("POST", "/checkout/preferences", {
            "items": [{
                "title": f"Orden {orden.orden_compra}", "quantity": 1,
                "unit_price": float(orden.monto), "currency_id": "CLP"
            }],
            "back_urls": {"success": url_retorno, "failure": url_retorno, "pending": url_retorno},
            "auto_return": "approved",
            "external_reference": orden.orden_compra
        })
        if "init_point" not in resp:
            raise PasarelaError("Respuesta inesperada de Mercado Pago al iniciar.")
            return InicioPago(url=resp["init_point"], metodo="GET", campos={}) # type: ignore 

    def confirmar(self, token: str) -> ResultadoPago:
        resp = self._llamar("GET", f"/v1/payments/{token}")
        aprobado = resp.get("status") == "approved"
        detalle = {
            "status": resp.get("status"),
            "status_detail": resp.get("status_detail"),
            "payment_method_id": resp.get("payment_method_id"),
        }
        return ResultadoPago(aprobado=aprobado, referencia=str(resp.get("id", "")), detalle=detalle)

    def token_desde_request(self, request):
        data = request.GET
        payment_id = data.get("payment_id") or data.get("collection_id")
        if not payment_id:
            return "", True
        return payment_id, False