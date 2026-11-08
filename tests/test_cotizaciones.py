from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.cotizaciones import services
from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
from apps.solicitudes.models import Estado

from .base import BaseTest

LINEAS = [{"descripcion": "Tablero", "cantidad": 2, "precio_unitario": 50000}, {"descripcion": "Mano de obra", "cantidad": 1, "precio_unitario": 100000}]


class CotizacionTests(BaseTest):
    def setUp(self):
        self.sol = self.crear_solicitud()

    def test_calculo_neto_iva_total(self):
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        self.assertEqual((c.neto, c.iva, c.total), (200000, 38000, 238000))

    def test_requiere_al_menos_una_linea(self):
        with self.assertRaises(services.CotizacionError):
            services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=[])
        self.assertEqual(Cotizacion.objects.count(), 0)  # transacción revertida

    def test_enviar_deja_solicitud_cotizada_y_notifica(self):  # RF-08, RF-11
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        with self.captureOnCommitCallbacks(execute=True):
            services.enviar_cotizacion(c, self.admin)
        self.sol.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.COTIZADA)
        self.assertEqual(c.estado, EstadoCotizacion.ENVIADA)
        self.assertTrue(any(c.codigo in m.subject for m in mail.outbox))

    def test_no_se_edita_ni_reenvia_lo_enviado(self):
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c, self.admin)
        with self.assertRaises(services.CotizacionError):
            services.actualizar_cotizacion(c, usuario=self.admin, lineas=LINEAS)
        with self.assertRaises(services.CotizacionError):
            services.enviar_cotizacion(c, self.admin)

    def test_nueva_cotizacion_reemplaza_la_anterior(self):
        c1 = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c1, self.admin)
        c2 = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c2, self.admin)
        c1.refresh_from_db()
        self.assertEqual(c1.estado, EstadoCotizacion.REEMPLAZADA)

    def test_cliente_acepta(self):
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c, self.admin)
        self.login(self.cliente)
        self.client.post(reverse("cotizaciones:responder", args=[c.pk]), {"accion": "aceptar"})
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.ACEPTADA)

    def test_sin_accion_no_rechaza_ni_acepta(self):  # regresión: un envío sin «accion» rechazaba la cotización
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c, self.admin)
        self.login(self.cliente)
        for datos in ({}, {"accion": ""}, {"accion": "borrar"}):
            self.client.post(reverse("cotizaciones:responder", args=[c.pk]), datos)
        c.refresh_from_db()
        self.sol.refresh_from_db()
        self.assertEqual(c.estado, EstadoCotizacion.ENVIADA)
        self.assertEqual(self.sol.estado, Estado.COTIZADA)

    def test_botones_de_respuesta_no_se_deshabilitan_por_js(self):  # regresión del script data-once
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent / "static" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn(".disabled = true", js)

    def test_cliente_rechaza_vuelve_a_revision(self):
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c, self.admin)
        self.login(self.cliente)
        self.client.post(reverse("cotizaciones:responder", args=[c.pk]), {"accion": "rechazar"})
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.EN_REVISION)

    def test_cliente_ajeno_no_puede_responder_ni_ver(self):  # S1
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        services.enviar_cotizacion(c, self.admin)
        self.login(self.cliente2)
        self.assertEqual(self.client.post(reverse("cotizaciones:responder", args=[c.pk]), {"accion": "aceptar"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("cotizaciones:detalle", args=[c.pk])).status_code, 404)
        c.refresh_from_db()
        self.assertEqual(c.estado, EstadoCotizacion.ENVIADA)

    def test_cliente_no_ve_borradores(self):
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        self.login(self.cliente)
        self.assertEqual(self.client.get(reverse("cotizaciones:detalle", args=[c.pk])).status_code, 302)
        r = self.client.get(reverse("solicitudes:detalle", args=[self.sol.pk]))
        self.assertNotContains(r, c.codigo)

    def test_cotizacion_vencida_no_se_acepta(self):
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS, validez_hasta=timezone.localdate() + timedelta(days=1))
        services.enviar_cotizacion(c, self.admin)
        Cotizacion.objects.filter(pk=c.pk).update(validez_hasta=timezone.localdate() - timedelta(days=1))
        with self.assertRaises(services.CotizacionError):
            services.responder_cotizacion(c, self.cliente, True)

    def test_flujo_completo_por_panel(self):
        self.login(self.admin)
        url = reverse("panel:cotizacion_crear", args=[self.sol.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {
            "observaciones": "Incluye materiales", "validez_hasta": "",
            "lineas-TOTAL_FORMS": "2", "lineas-INITIAL_FORMS": "0", "lineas-MIN_NUM_FORMS": "1", "lineas-MAX_NUM_FORMS": "1000",
            "lineas-0-descripcion": "Tablero", "lineas-0-cantidad": "1", "lineas-0-precio_unitario": "90000",
            "lineas-1-descripcion": "", "lineas-1-cantidad": "1", "lineas-1-precio_unitario": "",
        }
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["formset"].errors)
        c = Cotizacion.objects.get()
        self.assertEqual(c.neto, 90000)
        self.client.post(reverse("panel:cotizacion_enviar", args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.estado, EstadoCotizacion.ENVIADA)

    def test_listado_sin_n_mas_1(self):  # RNF-PER-02
        for _ in range(8):
            c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=LINEAS)
        self.login(self.admin)
        with self.assertNumQueries(9):
            self.client.get(reverse("panel:cotizaciones"))


class CotizacionDeProductosTests(BaseTest):
    """S3-R1: la cotización parte de los productos que pidió el cliente."""

    def setUp(self):
        from apps.solicitudes import services as sol
        self.sol = sol.crear_solicitud(
            cliente=self.cliente, servicio=None, datos={**self.datos_solicitud(), "servicio": None},
            items=[(self.producto, 3), (self.producto2, 1)])

    def test_lineas_sugeridas_con_precio_neto(self):
        lineas = services.lineas_sugeridas(self.sol)
        self.assertEqual([(l["descripcion"], l["cantidad"]) for l in lineas], [("Disyuntor 20A", 3), ("Diferencial", 1)])
        self.assertEqual(lineas[0]["precio_unitario"], 5882)   # 7.000 / 1,19
        self.assertEqual(lineas[1]["precio_unitario"], 21008)  # 25.000 / 1,19

    def test_formulario_nuevo_trae_lineas_precargadas(self):
        self.login(self.admin)
        r = self.client.get(reverse("panel:cotizacion_crear", args=[self.sol.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Precargamos los productos")
        self.assertContains(r, "Disyuntor 20A")
        self.assertEqual(r.context["formset"].forms[0].initial["cantidad"], 3)

    def test_formulario_de_solicitud_solo_servicio_no_precarga(self):
        sol = self.crear_solicitud(self.cliente2)
        self.login(self.admin)
        r = self.client.get(reverse("panel:cotizacion_crear", args=[sol.pk]))
        self.assertNotContains(r, "Precargamos los productos")

    def test_se_puede_cotizar_y_enviar_una_solicitud_de_productos(self):
        lineas = services.lineas_sugeridas(self.sol)
        c = services.crear_cotizacion(solicitud=self.sol, usuario=self.admin, lineas=lineas)
        services.enviar_cotizacion(c, self.admin)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.COTIZADA)
        self.login(self.cliente)
        self.assertContains(self.client.get(reverse("cotizaciones:detalle", args=[c.pk])), "Productos: Disyuntor 20A")

    def test_reporte_productos_mas_cotizados_y_csv(self):
        from apps.reportes import services as rep
        from django.utils import timezone
        d, h, ini, fin = rep.rango_fechas(timezone.localdate(), timezone.localdate())
        r = rep.resumen_solicitudes(ini, fin)
        self.assertEqual(r["por_producto"][0], ("Disyuntor 20A", 3, 1))
        self.assertEqual(r["por_servicio"][0][0], "(Solo productos)")
        from io import StringIO
        out = StringIO()
        rep.csv_solicitudes(ini, fin, out)
        self.assertIn("3 x Disyuntor 20A; 1 x Diferencial", out.getvalue())
