from unittest import mock

from django.test import override_settings
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.pagos import services as pagos
from apps.pagos.gateways import REGISTRO, obtener_pasarela
from apps.pagos.gateways.base import InicioPago, PasarelaError, PasarelaPago, ResultadoPago
from apps.pagos.models import EstadoPago, Pago
from apps.tienda import services as ventas
from apps.tienda.carrito import Carrito
from apps.tienda.models import DetalleVenta, EstadoVenta, Venta

from .base import BaseTest

ENTREGA = {"nombre_cliente": "Carla", "direccion_entrega": "Calle 1", "telefono_contacto": "+56911111111"}


class CarritoCheckoutTests(BaseTest):
    def agregar(self, producto, n=1):
        return self.client.post(reverse("tienda:carrito_agregar", args=[producto.pk]), {"cantidad": n})

    def test_visitante_arma_carrito_pero_debe_ingresar_para_comprar(self):  # T1
        self.agregar(self.producto, 2)
        r = self.client.get(reverse("tienda:carrito"))
        self.assertContains(r, "Disyuntor 20A")
        r = self.client.get(reverse("tienda:checkout"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("ingresar", r["Location"])

    def test_checkout_crea_venta_pendiente_con_detalle(self):  # RF-13, RF-14
        self.login(self.cliente)
        self.agregar(self.producto, 2)
        self.agregar(self.producto2, 1)
        r = self.client.post(reverse("tienda:checkout"), ENTREGA)
        v = Venta.objects.get()
        self.assertRedirects(r, reverse("pagos:iniciar", args=[v.pk]), fetch_redirect_response=False)
        self.assertEqual(v.estado, EstadoVenta.PENDIENTE_PAGO)
        self.assertEqual(v.total, 2 * 7000 + 25000)
        self.assertEqual(v.detalles.count(), 2)
        self.assertEqual(Carrito(self.client).__class__.__name__, "Carrito")

    def test_precio_siempre_desde_la_base_de_datos(self):
        self.login(self.cliente)
        self.agregar(self.producto, 1)
        self.client.post(reverse("tienda:checkout"), {**ENTREGA, "precio": "1", "total": "1"})
        self.assertEqual(Venta.objects.get().total, 7000)

    def test_carrito_vacio_no_crea_venta(self):
        self.login(self.cliente)
        self.client.post(reverse("tienda:checkout"), ENTREGA)
        self.assertEqual(Venta.objects.count(), 0)

    def test_producto_inactivo_no_se_vende(self):
        self.login(self.cliente)
        self.agregar(self.producto, 1)
        self.producto.activo = False
        self.producto.save()
        self.client.post(reverse("tienda:checkout"), ENTREGA)
        self.assertEqual(Venta.objects.count(), 0)

    def test_cliente_no_ve_compra_ajena(self):  # S1
        v = ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1}], datos_entrega=ENTREGA)
        self.login(self.cliente2)
        self.assertEqual(self.client.get(reverse("tienda:compra", args=[v.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("pagos:iniciar", args=[v.pk])).status_code, 404)

    def test_falla_al_crear_detalle_no_deja_venta_huerfana(self):  # EC-02
        with mock.patch("apps.tienda.services.DetalleVenta.objects.bulk_create", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1}], datos_entrega=ENTREGA)
        self.assertEqual(Venta.objects.count(), 0)
        self.assertEqual(DetalleVenta.objects.count(), 0)


class PagoTests(BaseTest):
    def setUp(self):
        self.venta = ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1}], datos_entrega=ENTREGA)

    def flujo_sandbox(self, aprobar=True):
        self.login(self.cliente)
        r = self.client.post(reverse("pagos:iniciar", args=[self.venta.pk]))
        self.assertEqual(r.status_code, 302)
        token = r["Location"].rstrip("/").split("/")[-1]
        r = self.client.post(reverse("pagos:sandbox", args=[token]), {"resultado": "aprobar" if aprobar else "rechazar"})
        return token, self.client.get(r["Location"])

    def test_pago_aprobado_marca_venta_pagada(self):
        token, r = self.flujo_sandbox(True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PAGADA)
        self.assertEqual(Pago.objects.get().estado, EstadoPago.APROBADO)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="PAGO", entidad="venta").exists())

    def test_pago_rechazado_deja_venta_pendiente_y_permite_reintentar(self):  # EC-02
        self.flujo_sandbox(False)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PENDIENTE_PAGO)
        self.flujo_sandbox(True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PAGADA)
        self.assertEqual(Pago.objects.count(), 2)

    def test_confirmacion_idempotente(self):  # EC-02: reintento idempotente
        token, _ = self.flujo_sandbox(True)
        pasarela = obtener_pasarela()
        with mock.patch.object(type(pasarela), "confirmar", side_effect=AssertionError("no debe volver a confirmar")):
            for _ in range(3):
                p = pagos.confirmar_pago(token)
                self.assertEqual(p.estado, EstadoPago.APROBADO)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="PAGO", entidad="venta").count(), 1)

    def test_falla_de_pasarela_no_pierde_el_pedido(self):  # EC-06
        self.login(self.cliente)
        with mock.patch("apps.pagos.gateways.sandbox.SandboxGateway.iniciar", side_effect=PasarelaError("timeout")):
            r = self.client.post(reverse("pagos:iniciar", args=[self.venta.pk]), follow=True)
        self.assertContains(r, "pendiente de pago")
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PENDIENTE_PAGO)
        self.assertEqual(Pago.objects.get().estado, EstadoPago.ERROR)
        self.assertEqual(Venta.objects.count(), 1)

    def test_falla_al_confirmar_deja_pago_iniciado_para_reintentar(self):
        self.login(self.cliente)
        r = self.client.post(reverse("pagos:iniciar", args=[self.venta.pk]))
        token = r["Location"].rstrip("/").split("/")[-1]
        with mock.patch("apps.pagos.gateways.sandbox.SandboxGateway.confirmar", side_effect=PasarelaError("caída")):
            p = pagos.confirmar_pago(token)
        self.assertEqual(p.estado, EstadoPago.INICIADO)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PENDIENTE_PAGO)

    def test_sin_aprobacion_no_se_paga(self):
        self.login(self.cliente)
        r = self.client.post(reverse("pagos:iniciar", args=[self.venta.pk]))
        token = r["Location"].rstrip("/").split("/")[-1]
        p = pagos.confirmar_pago(token)  # nadie aprobó en la pasarela
        self.assertEqual(p.estado, EstadoPago.RECHAZADO)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PENDIENTE_PAGO)

    def test_token_desconocido(self):
        self.assertIsNone(pagos.confirmar_pago("token-inexistente"))
        self.login(self.cliente)
        self.assertEqual(self.client.get(reverse("pagos:retorno") + "?token_ws=nada").status_code, 404)

    @override_settings(PAYMENT_SANDBOX_PERMITIDO=False)
    def test_sandbox_bloqueado_en_produccion(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured):
            obtener_pasarela("sandbox")

    def test_no_se_almacenan_datos_de_tarjeta(self):  # RNF-SEG-06
        campos = {f.name for f in Pago._meta.get_fields()}
        self.assertFalse(campos & {"tarjeta", "numero_tarjeta", "cvv", "card_number", "pan"})

    def test_cambiar_de_pasarela_no_toca_ventas(self):  # EC-03
        class FakeGateway(PasarelaPago):
            nombre = "fake"
            def iniciar(self, orden, url_retorno):
                return InicioPago(token="fake-tok", url="https://pago.fake/x")
            def confirmar(self, token):
                return ResultadoPago(aprobado=True, referencia="F1")
            def token_desde_request(self, request):
                return request.GET.get("t", ""), False

        REGISTRO["fake"] = "tests.test_tienda_pagos.FakeGateway"
        globals()["FakeGateway"] = FakeGateway
        try:
            with override_settings(PAYMENT_GATEWAY="fake"):
                pago, inicio = pagos.iniciar_pago(self.venta, "http://x/retorno")
                self.assertEqual(inicio.url, "https://pago.fake/x")
                p = pagos.confirmar_pago("fake-tok")
                self.assertEqual(p.proveedor, "fake")
                self.venta.refresh_from_db()
                self.assertEqual(self.venta.estado, EstadoVenta.PAGADA)
        finally:
            REGISTRO.pop("fake", None)

    def test_adaptador_webpay_traduce_errores_de_red(self):
        from apps.pagos.gateways.webpay import WebpayGateway
        import urllib.error
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")):
            with self.assertRaises(PasarelaError):
                WebpayGateway().iniciar(mock.Mock(orden_compra="V1-P1", sesion="s", monto=1000), "http://x")

    def test_adaptador_webpay_respuesta_autorizada(self):
        import json
        from apps.pagos.gateways.webpay import WebpayGateway

        class Resp:
            def __init__(s, d): s.d = d
            def read(s): return json.dumps(s.d).encode()
            def __enter__(s): return s
            def __exit__(s, *a): return False
        with mock.patch("urllib.request.urlopen", return_value=Resp({"status": "AUTHORIZED", "response_code": 0, "authorization_code": "123", "card_detail": {"card_number": "6623"}})):
            res = WebpayGateway().confirmar("tok")
        self.assertTrue(res.aprobado)
        self.assertNotIn("card_detail", res.detalle)  # no se guarda nada de tarjeta

    def test_cancelacion_del_cliente_en_webpay(self):
        from apps.pagos.gateways.webpay import WebpayGateway
        from django.test import RequestFactory
        req = RequestFactory().get("/pagos/retorno/", {"TBK_TOKEN": "abc"})
        self.assertEqual(WebpayGateway().token_desde_request(req), ("abc", True))

    def test_venta_pagada_no_se_cancela_y_manual_funciona(self):
        self.login(self.admin)
        self.client.post(reverse("panel:venta_accion", args=[self.venta.pk]), {"accion": "pagada_manual"})
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, EstadoVenta.PAGADA)
        with self.assertRaises(ventas.VentaError):
            ventas.cancelar_venta(self.venta.pk, self.admin)
