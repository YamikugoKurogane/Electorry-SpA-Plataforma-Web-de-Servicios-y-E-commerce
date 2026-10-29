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
        with self.assertNumQueries(8):
            self.client.get(reverse("panel:cotizaciones"))
