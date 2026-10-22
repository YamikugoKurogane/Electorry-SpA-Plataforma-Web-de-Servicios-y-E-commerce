"""Adaptador Webpay Plus (API REST de Transbank).

Nunca maneja datos de tarjeta: el cliente es redirigido al formulario de
Transbank y regresa con un token. Usa timeouts y traduce cualquier falla a
`PasarelaError` para que el flujo de ventas la aísle (EC-06).

Por defecto apunta al ambiente de INTEGRACIÓN con credenciales públicas de
Transbank. Para producción define WEBPAY_BASE_URL, WEBPAY_COMMERCE_CODE y
WEBPAY_API_SECRET como variables de entorno.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

from .base import InicioPago, OrdenPago, PasarelaError, PasarelaPago, ResultadoPago

RUTA = "/rswebpaytransbank/v1.2/transactions"


class WebpayGateway(PasarelaPago):
    nombre = "webpay"

    def _llamar(self, metodo, ruta, cuerpo=None):
        url = settings.WEBPAY_BASE_URL.rstrip("/") + ruta
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(
            url,
            data=datos,
            method=metodo,
            headers={
                "Tbk-Api-Key-Id": settings.WEBPAY_COMMERCE_CODE,
                "Tbk-Api-Key-Secret": settings.WEBPAY_API_SECRET,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=settings.PAYMENT_TIMEOUT) as resp:  # noqa: S310
                return json.loads(resp.read().decode() or "{}")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise PasarelaError(f"Webpay no respondió correctamente: {exc}") from exc

    def iniciar(self, orden: OrdenPago, url_retorno: str) -> InicioPago:
        resp = self._llamar(
            "POST",
            RUTA,
            {"buy_order": orden.orden_compra[:26], "session_id": orden.sesion[:61], "amount": orden.monto, "return_url": url_retorno},
        )
        if "token" not in resp or "url" not in resp:
            raise PasarelaError("Respuesta inesperada de Webpay al iniciar la transacción.")
        return InicioPago(token=resp["token"], url=resp["url"], metodo="POST", campos={"token_ws": resp["token"]})

    def confirmar(self, token: str) -> ResultadoPago:
        resp = self._llamar("PUT", f"{RUTA}/{token}")
        aprobado = resp.get("status") == "AUTHORIZED" and resp.get("response_code") == 0
        # Solo se guardan campos no sensibles.
        detalle = {k: resp.get(k) for k in ("status", "response_code", "amount", "buy_order", "authorization_code", "payment_type_code", "installments_number") if k in resp}
        return ResultadoPago(aprobado=aprobado, referencia=str(resp.get("authorization_code", "")), detalle=detalle)

    def token_desde_request(self, request):
        data = request.POST if request.method == "POST" else request.GET
        if data.get("TBK_TOKEN"):  # el cliente anuló el pago en el formulario de Transbank
            return data.get("TBK_TOKEN"), True
        return data.get("token_ws", ""), False
