"""S3-R2 · RF-36: listado de pagos para el administrador con filtros por estado y fecha."""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.pagos import services as pagos
from apps.pagos.models import EstadoPago, Pago
from apps.tienda import services as ventas
from apps.tienda.models import EstadoVenta

from .base import BaseTest

ENTREGA = {"nombre_cliente": "Carla", "direccion_entrega": "Calle 1", "telefono_contacto": "+56911111111"}
SCL = ZoneInfo("America/Santiago")


class ListadoPagosTests(BaseTest):
    def venta(self, cliente=None, producto=None, cantidad=1):
        return ventas.crear_venta(cliente=cliente or self.cliente, lineas=[{"producto": producto or self.producto, "cantidad": cantidad}], datos_entrega=ENTREGA)

    def pago(self, venta=None, estado=EstadoPago.APROBADO, proveedor="sandbox", fecha=None, referencia=""):
        venta = venta or self.venta()
        p = Pago.objects.create(venta=venta, proveedor=proveedor, monto=venta.total, estado=estado, referencia=referencia)
        if fecha:
            Pago.objects.filter(pk=p.pk).update(creado=fecha)
        return p

    def get(self, **params):
        self.login(self.admin)
        return self.client.get(reverse("panel:pagos"), params)

    # ---- acceso
    def test_solo_el_administrador(self):
        url = reverse("panel:pagos")
        self.assertEqual(self.client.get(url).status_code, 302)  # visitante → login
        self.login(self.cliente)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login(self.interno)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_exportacion_tambien_protegida(self):
        self.login(self.interno)
        self.assertEqual(self.client.get(reverse("panel:pagos"), {"exportar": "csv"}).status_code, 403)

    # ---- contenido y totales
    def test_lista_pagos_con_venta_cliente_y_monto(self):
        p = self.pago(referencia="REF-123")
        r = self.get()
        self.assertContains(r, p.venta.codigo)
        self.assertContains(r, "c1@t.cl")
        self.assertContains(r, "$7.000")
        self.assertContains(r, "REF-123")

    def test_totales_solo_suman_aprobados_y_no_se_duplican(self):
        self.pago(estado=EstadoPago.APROBADO)                                              # 7.000
        self.pago(estado=EstadoPago.APROBADO, venta=self.venta(producto=self.producto2))   # 25.000
        self.pago(estado=EstadoPago.RECHAZADO)
        self.pago(estado=EstadoPago.ERROR)
        self.pago(estado=EstadoPago.INICIADO)
        r = self.get()
        self.assertEqual(r.context["monto_aprobado"], 32000)
        self.assertEqual(r.context["total"], 5)
        self.assertEqual({v: n for _, n, v in r.context["resumen"]},
                         {"INICIADO": 1, "APROBADO": 2, "RECHAZADO": 1, "ERROR": 1})

    # ---- filtros
    def test_filtro_por_estado(self):
        a = self.pago(estado=EstadoPago.APROBADO)
        b = self.pago(estado=EstadoPago.RECHAZADO)
        r = self.get(estado="RECHAZADO")
        self.assertEqual([p.pk for p in r.context["pagina"]], [b.pk])
        self.assertEqual(r.context["total"], 1)
        self.assertEqual(r.context["monto_aprobado"], 0)

    def test_estado_invalido_se_ignora(self):
        self.pago()
        r = self.get(estado="HACKEADO")
        self.assertEqual(r.context["total"], 1)
        self.assertEqual(r.context["estado"], "")

    def test_filtro_por_fecha_incluye_los_dos_extremos(self):
        viejo = self.pago(fecha=datetime(2026, 3, 5, 12, 0, tzinfo=SCL))
        medio = self.pago(fecha=datetime(2026, 3, 10, 12, 0, tzinfo=SCL))
        nuevo = self.pago(fecha=datetime(2026, 3, 20, 12, 0, tzinfo=SCL))
        r = self.get(desde="2026-03-05", hasta="2026-03-10")
        self.assertEqual({p.pk for p in r.context["pagina"]}, {viejo.pk, medio.pk})
        r = self.get(desde="2026-03-11")
        self.assertEqual([p.pk for p in r.context["pagina"]], [nuevo.pk])
        r = self.get(hasta="2026-03-04")
        self.assertEqual(r.context["total"], 0)

    def test_la_fecha_se_interpreta_en_hora_de_chile(self):
        # 23:30 del 10 de marzo en Chile = 02:30 del 11 en UTC: debe contarse como día 10.
        p = self.pago(fecha=datetime(2026, 3, 10, 23, 30, tzinfo=SCL))
        self.assertEqual([x.pk for x in self.get(desde="2026-03-10", hasta="2026-03-10").context["pagina"]], [p.pk])
        self.assertEqual(self.get(desde="2026-03-11", hasta="2026-03-11").context["total"], 0)

    def test_fechas_invertidas_se_ordenan_y_avisa(self):
        self.pago(fecha=datetime(2026, 3, 10, 12, 0, tzinfo=SCL))
        r = self.get(desde="2026-03-31", hasta="2026-03-01")
        self.assertEqual(r.context["total"], 1)
        self.assertContains(r, "invertidas")

    def test_fecha_invalida_se_ignora_sin_error(self):
        self.pago()
        r = self.get(desde="no-es-fecha", hasta="2026-13-45")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["total"], 1)

    def test_filtro_por_medio_de_pago(self):
        self.pago(proveedor="webpay")
        m = self.pago(proveedor="manual")
        r = self.get(proveedor="manual")
        self.assertEqual([p.pk for p in r.context["pagina"]], [m.pk])

    def test_busqueda_por_codigo_correo_y_referencia(self):
        p1 = self.pago(referencia="AUTH-777")
        p2 = self.pago(venta=self.venta(cliente=self.cliente2))
        self.assertEqual([p.pk for p in self.get(q=p1.venta.codigo).context["pagina"]], [p1.pk])
        self.assertEqual([p.pk for p in self.get(q="c2@t.cl").context["pagina"]], [p2.pk])
        self.assertEqual([p.pk for p in self.get(q="AUTH-777").context["pagina"]], [p1.pk])
        self.assertEqual(self.get(q="inexistente").context["total"], 0)

    def test_filtros_combinados(self):
        self.pago(estado=EstadoPago.APROBADO, fecha=datetime(2026, 3, 10, 12, 0, tzinfo=SCL))
        ok = self.pago(estado=EstadoPago.RECHAZADO, fecha=datetime(2026, 3, 10, 12, 0, tzinfo=SCL))
        self.pago(estado=EstadoPago.RECHAZADO, fecha=datetime(2026, 4, 10, 12, 0, tzinfo=SCL))
        r = self.get(estado="RECHAZADO", desde="2026-03-01", hasta="2026-03-31")
        self.assertEqual([p.pk for p in r.context["pagina"]], [ok.pk])

    # ---- paginación, rendimiento, exportación
    def test_paginacion(self):
        for _ in range(27):
            self.pago()
        r = self.get()
        self.assertEqual(len(r.context["pagina"]), 25)
        self.assertEqual(r.context["total"], 27)
        self.assertEqual(len(self.client.get(reverse("panel:pagos"), {"pagina": 2}).context["pagina"]), 2)

    def test_consultas_constantes_sin_n_mas_1(self):  # RNF-PER-02
        def consultas(n):
            Pago.objects.all().delete()
            for _ in range(n):
                self.pago()
            self.login(self.admin)
            with CaptureQueriesContext(connection) as c:
                self.client.get(reverse("panel:pagos"))
            return len(c)
        self.assertEqual(consultas(2), consultas(15))

    def test_exportar_csv_respeta_filtros(self):
        self.pago(estado=EstadoPago.APROBADO, referencia="OK-1")
        self.pago(estado=EstadoPago.RECHAZADO, referencia="NO-1")
        r = self.get(estado="APROBADO", exportar="csv")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        cuerpo = r.content.decode("utf-8-sig")
        self.assertIn("OK-1", cuerpo)
        self.assertNotIn("NO-1", cuerpo)
        self.assertTrue(cuerpo.startswith("id,fecha,venta,cliente,proveedor,estado,monto,referencia"))

    def test_csv_neutraliza_formulas(self):
        self.pago(referencia='=HYPERLINK("http://malo.example","clic")')
        cuerpo = self.get(exportar="csv").content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", cuerpo)

    # ---- pagos manuales
    def test_pago_manual_queda_registrado_y_aparece_en_el_listado(self):
        v = self.venta()
        self.login(self.admin)
        self.client.post(reverse("panel:venta_accion", args=[v.pk]), {"accion": "pagada_manual"})
        v.refresh_from_db()
        self.assertEqual(v.estado, EstadoVenta.PAGADA)
        p = Pago.objects.get(venta=v)
        self.assertEqual((p.proveedor, p.estado, p.monto), ("manual", EstadoPago.APROBADO, 7000))
        r = self.client.get(reverse("panel:pagos"))
        self.assertEqual(r.context["monto_aprobado"], 7000)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="PAGO", entidad="venta", entidad_id=v.pk).exists())

    def test_pago_manual_es_idempotente(self):
        v = self.venta()
        pagos.registrar_pago_manual(v.pk, self.admin)
        pagos.registrar_pago_manual(v.pk, self.admin)
        self.assertEqual(Pago.objects.filter(venta=v).count(), 1)

    def test_pago_manual_no_duplica_si_ya_pago_por_pasarela(self):
        v = self.venta()
        self.pago(venta=v, estado=EstadoPago.APROBADO, proveedor="webpay")
        ventas.marcar_pagada(v.pk)
        pagos.registrar_pago_manual(v.pk, self.admin)
        self.assertEqual(Pago.objects.filter(venta=v).count(), 1)

    def test_no_se_registra_pago_manual_en_venta_cancelada(self):
        v = self.venta()
        ventas.cancelar_venta(v.pk, self.admin)
        with self.assertRaises(ventas.VentaError):
            pagos.registrar_pago_manual(v.pk, self.admin)
        self.assertEqual(Pago.objects.count(), 0)
