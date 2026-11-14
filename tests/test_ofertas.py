"""S4-R1 · RF-16 / RF-17 · HU-06, HU-12, HU-17: gestión de ofertas con vigencia y vista para el cliente."""
from datetime import date, timedelta

from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.ofertas import services
from apps.ofertas.models import EstadoOferta, Oferta
from apps.solicitudes.models import SolicitudCotizacion
from apps.tienda import services as ventas
from apps.tienda.models import DetalleVenta, Producto

from .base import BaseTest

HOY = timezone.localdate()
ENTREGA = {"nombre_cliente": "Carla", "direccion_entrega": "Calle 1", "telefono_contacto": "+56911111111"}


class OfertasBase(BaseTest):
    def oferta(self, descuento=20, inicio=None, fin=None, productos=(), servicios=(), solo_clientes=False, titulo="Oferta", finalizada=False):
        o = Oferta.objects.create(
            titulo=titulo, descuento=descuento, fecha_inicio=inicio or HOY - timedelta(days=1), fecha_fin=fin or HOY + timedelta(days=10),
            solo_clientes=solo_clientes, finalizada_en=timezone.now() if finalizada else None, creada_por=self.admin,
        )
        o.productos.set(productos)
        o.servicios.set(servicios)
        return o

    def consultas(self, fn):
        with CaptureQueriesContext(connection) as c:
            r = fn()
        return len(c), r


class VigenciaTests(OfertasBase):
    def test_estados(self):
        o = self.oferta(inicio=HOY + timedelta(days=2), fin=HOY + timedelta(days=5))
        self.assertEqual(o.estado, EstadoOferta.PROGRAMADA)
        self.assertEqual(self.oferta().estado, EstadoOferta.VIGENTE)
        self.assertEqual(self.oferta(inicio=HOY - timedelta(days=9), fin=HOY - timedelta(days=1)).estado, EstadoOferta.VENCIDA)
        self.assertEqual(self.oferta(finalizada=True).estado, EstadoOferta.FINALIZADA)

    def test_las_fechas_extremas_son_inclusivas(self):
        o = Oferta(descuento=10, fecha_inicio=date(2026, 6, 10), fecha_fin=date(2026, 6, 20))
        self.assertEqual(o.estado_en(date(2026, 6, 9)), EstadoOferta.PROGRAMADA)
        self.assertEqual(o.estado_en(date(2026, 6, 10)), EstadoOferta.VIGENTE)   # primer día
        self.assertEqual(o.estado_en(date(2026, 6, 20)), EstadoOferta.VIGENTE)   # último día
        self.assertEqual(o.estado_en(date(2026, 6, 21)), EstadoOferta.VENCIDA)

    def test_queryset_vigentes(self):
        v = self.oferta(titulo="v")
        self.oferta(titulo="programada", inicio=HOY + timedelta(days=1), fin=HOY + timedelta(days=3))
        self.oferta(titulo="vencida", inicio=HOY - timedelta(days=5), fin=HOY - timedelta(days=1))
        self.oferta(titulo="finalizada", finalizada=True)
        self.assertEqual(list(Oferta.objects.vigentes()), [v])
        self.assertEqual(Oferta.objects.vigentes(HOY + timedelta(days=2)).filter(titulo="programada").count(), 1)

    def test_la_base_rechaza_datos_invalidos(self):
        for kw in ({"descuento": 0}, {"descuento": 91}, {"inicio": HOY, "fin": HOY - timedelta(days=1)}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.oferta(**kw)


class PreciosTests(OfertasBase):
    def test_calculo_y_redondeo(self):
        c = services.precio_con_descuento
        self.assertEqual(c(7000, 15), 5950)
        self.assertEqual(c(25000, 33), 16750)
        self.assertEqual(c(1005, 50), 503)    # 502,5 → sube (mitad hacia arriba)
        self.assertEqual(c(999, 10), 899)     # 899,1 → baja
        self.assertEqual(c(1, 90), 1)         # nunca queda en $0

    def test_sin_oferta_es_precio_de_lista(self):
        pv = services.precio_vigente(self.producto)
        self.assertEqual((pv.precio, pv.precio_lista, pv.descuento, pv.con_oferta), (7000, 7000, 0, False))

    def test_con_oferta_vigente(self):
        self.oferta(descuento=20, productos=[self.producto])
        pv = services.precio_vigente(self.producto)
        self.assertEqual((pv.precio, pv.precio_lista, pv.descuento, pv.con_oferta), (5600, 7000, 20, True))

    def test_no_aplican_programadas_vencidas_ni_finalizadas(self):
        self.oferta(productos=[self.producto], inicio=HOY + timedelta(days=1), fin=HOY + timedelta(days=4))
        self.oferta(productos=[self.producto], inicio=HOY - timedelta(days=5), fin=HOY - timedelta(days=1))
        self.oferta(productos=[self.producto], finalizada=True)
        self.assertFalse(services.precio_vigente(self.producto).con_oferta)

    def test_varias_ofertas_se_aplica_la_de_mayor_descuento_sin_acumular(self):
        self.oferta(descuento=10, productos=[self.producto], titulo="chica")
        grande = self.oferta(descuento=30, productos=[self.producto], titulo="grande")
        pv = services.precio_vigente(self.producto)
        self.assertEqual((pv.precio, pv.descuento, pv.oferta.pk), (4900, 30, grande.pk))   # 7.000 − 30 %, no −37 %

    def test_empate_de_descuento_es_determinista(self):
        a = self.oferta(descuento=15, productos=[self.producto], titulo="A")
        self.oferta(descuento=15, productos=[self.producto], titulo="B")
        self.assertEqual(services.precio_vigente(self.producto).oferta.pk, a.pk)

    def test_ofertas_exclusivas_solo_para_sesion_iniciada(self):
        self.oferta(descuento=25, productos=[self.producto], solo_clientes=True)
        self.assertFalse(services.precio_vigente(self.producto, None).con_oferta)
        self.assertEqual(services.precio_vigente(self.producto, self.cliente).precio, 5250)

    def test_una_sola_consulta_para_toda_la_lista(self):
        extra = [Producto.objects.create(categoria=self.producto.categoria, nombre=f"P{i}", precio=1000 + i) for i in range(12)]
        self.oferta(productos=[self.producto, *extra[:6]])
        n, _ = self.consultas(lambda: services.precios_vigentes([self.producto, self.producto2, *extra]))
        self.assertEqual(n, 1)

    def test_al_cambiar_el_precio_de_lista_se_recalcula(self):
        self.oferta(descuento=50, productos=[self.producto])
        self.producto.precio = 10000
        self.producto.save()
        self.assertEqual(services.precio_vigente(self.producto).precio, 5000)


class AdministracionServicioTests(OfertasBase):
    def datos(self, **kw):
        d = {"titulo": "Verano solar", "descripcion": "x", "descuento": 15, "fecha_inicio": HOY, "fecha_fin": HOY + timedelta(days=7), "solo_clientes": False}
        d.update(kw)
        return d

    def test_crear_registra_auditoria(self):  # RF-16, RF-15
        o = services.crear_oferta(usuario=self.admin, datos=self.datos(), productos=[self.producto], servicios=[self.servicio])
        self.assertEqual((o.productos.count(), o.servicios.count(), o.creada_por), (1, 1, self.admin))
        r = RegistroAuditoria.objects.get(entidad="oferta", entidad_id=o.pk, accion="CREAR")
        self.assertEqual(r.usuario, self.admin)

    def test_validaciones(self):
        casos = [
            ({"titulo": " "}, [self.producto], "título"),
            ({"descuento": 0}, [self.producto], "descuento"),
            ({"descuento": 95}, [self.producto], "descuento"),
            ({"fecha_fin": HOY - timedelta(days=1), "fecha_inicio": HOY - timedelta(days=3)}, [self.producto], "pasado"),
            ({"fecha_fin": HOY, "fecha_inicio": HOY + timedelta(days=2)}, [self.producto], "anterior"),
            ({}, [], "al menos un producto o un servicio"),
        ]
        for kw, productos, texto in casos:
            with self.assertRaises(services.OfertaError, msg=str(kw)) as cm:
                services.crear_oferta(usuario=self.admin, datos=self.datos(**kw), productos=productos)
            self.assertIn(texto, str(cm.exception))
        self.assertEqual(Oferta.objects.count(), 0)

    def test_actualizar_con_auditoria_antes_y_despues(self):
        o = services.crear_oferta(usuario=self.admin, datos=self.datos(), productos=[self.producto])
        services.actualizar_oferta(o, usuario=self.admin, datos=self.datos(descuento=40), productos=[self.producto, self.producto2])
        o.refresh_from_db()
        self.assertEqual((o.descuento, o.productos.count()), (40, 2))
        r = RegistroAuditoria.objects.get(entidad="oferta", entidad_id=o.pk, accion="EDITAR")
        self.assertEqual((r.antes["descuento"], r.despues["descuento"]), (15, 40))

    def test_una_oferta_vencida_se_reabre_ampliando_la_fecha(self):
        o = self.oferta(inicio=HOY - timedelta(days=9), fin=HOY - timedelta(days=1), productos=[self.producto])
        self.assertEqual(o.estado, EstadoOferta.VENCIDA)
        services.actualizar_oferta(o, usuario=self.admin, datos=self.datos(fecha_inicio=o.fecha_inicio, fecha_fin=HOY + timedelta(days=5)), productos=[self.producto])
        o.refresh_from_db()
        self.assertEqual(o.estado, EstadoOferta.VIGENTE)

    def test_editar_una_vencida_sin_cambiar_su_fecha_no_se_rechaza(self):
        o = self.oferta(inicio=HOY - timedelta(days=9), fin=HOY - timedelta(days=1), productos=[self.producto])
        services.actualizar_oferta(o, usuario=self.admin, datos=self.datos(titulo="Nuevo título", fecha_inicio=o.fecha_inicio, fecha_fin=o.fecha_fin), productos=[self.producto])
        o.refresh_from_db()
        self.assertEqual(o.titulo, "Nuevo título")

    def test_finalizar(self):  # RF-16: finalizar
        o = self.oferta(descuento=20, productos=[self.producto])
        self.assertTrue(services.precio_vigente(self.producto).con_oferta)
        services.finalizar_oferta(o.pk, self.admin)
        o.refresh_from_db()
        self.assertEqual(o.estado, EstadoOferta.FINALIZADA)
        self.assertFalse(services.precio_vigente(self.producto).con_oferta)  # deja de aplicarse al instante
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="oferta", entidad_id=o.pk, accion="CAMBIO_ESTADO").exists())

    def test_finalizar_dos_veces_y_editar_finalizada(self):
        o = self.oferta(productos=[self.producto])
        services.finalizar_oferta(o.pk, self.admin)
        with self.assertRaises(services.OfertaError):
            services.finalizar_oferta(o.pk, self.admin)
        with self.assertRaises(services.OfertaError):
            services.actualizar_oferta(o, usuario=self.admin, datos=self.datos(), productos=[self.producto])


class PanelOfertasTests(OfertasBase):
    def post_form(self, url, **kw):
        d = {"titulo": "Cables en oferta", "descripcion": "", "descuento": "20", "fecha_inicio": HOY.isoformat(),
             "fecha_fin": (HOY + timedelta(days=5)).isoformat(), "productos": [self.producto.pk]}
        d.update(kw)
        return self.client.post(url, d)

    def test_solo_el_administrador(self):
        urls = [reverse("panel:ofertas"), reverse("panel:oferta_crear")]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 302)
        for usuario in (self.cliente, self.interno):
            self.login(usuario)
            for u in urls:
                self.assertEqual(self.client.get(u).status_code, 403, (usuario.rol, u))
        self.login(self.admin)
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 200)

    def test_crear_por_formulario(self):
        self.login(self.admin)
        r = self.post_form(reverse("panel:oferta_crear"))
        self.assertRedirects(r, reverse("panel:ofertas"))
        o = Oferta.objects.get()
        self.assertEqual((o.titulo, o.descuento, o.solo_clientes), ("Cables en oferta", 20, False))
        self.assertEqual(list(o.productos.all()), [self.producto])

    def test_formulario_muestra_todos_los_errores(self):
        self.login(self.admin)
        r = self.post_form(reverse("panel:oferta_crear"), descuento="99", productos=[])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Oferta.objects.count(), 0)
        self.assertContains(r, "entre 1")
        self.assertContains(r, "al menos un producto o un servicio")

    def test_editar(self):
        o = self.oferta(productos=[self.producto])
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("panel:oferta_editar", args=[o.pk])), "Editar oferta")
        r = self.post_form(reverse("panel:oferta_editar", args=[o.pk]), descuento="35", titulo="Editada")
        self.assertRedirects(r, reverse("panel:ofertas"))
        o.refresh_from_db()
        self.assertEqual((o.descuento, o.titulo), (35, "Editada"))

    def test_finalizar_solo_por_post(self):
        o = self.oferta(productos=[self.producto])
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("panel:oferta_finalizar", args=[o.pk])).status_code, 405)
        self.client.post(reverse("panel:oferta_finalizar", args=[o.pk]))
        o.refresh_from_db()
        self.assertEqual(o.estado, EstadoOferta.FINALIZADA)

    def test_no_se_edita_una_finalizada(self):
        o = self.oferta(productos=[self.producto], finalizada=True)
        self.login(self.admin)
        r = self.client.get(reverse("panel:oferta_editar", args=[o.pk]), follow=True)
        self.assertContains(r, "no se puede editar")

    def test_listado_filtra_por_estado_y_titulo(self):
        self.oferta(titulo="Vigente A", productos=[self.producto])
        self.oferta(titulo="Programada B", inicio=HOY + timedelta(days=2), fin=HOY + timedelta(days=4), productos=[self.producto])
        self.oferta(titulo="Vencida C", inicio=HOY - timedelta(days=5), fin=HOY - timedelta(days=2), productos=[self.producto])
        self.oferta(titulo="Finalizada D", finalizada=True, productos=[self.producto])
        self.login(self.admin)
        def titulos(**p): return sorted(o.titulo for o in self.client.get(reverse("panel:ofertas"), p).context["pagina"])
        self.assertEqual(len(titulos()), 4)
        self.assertEqual(titulos(estado="VIGENTE"), ["Vigente A"])
        self.assertEqual(titulos(estado="PROGRAMADA"), ["Programada B"])
        self.assertEqual(titulos(estado="VENCIDA"), ["Vencida C"])
        self.assertEqual(titulos(estado="FINALIZADA"), ["Finalizada D"])
        self.assertEqual(titulos(q="programada"), ["Programada B"])
        self.assertEqual(len(titulos(estado="HACKEADO")), 4)

    def test_el_menu_del_panel_tiene_ofertas_solo_para_admin(self):
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("panel:dashboard")), reverse("panel:ofertas"))
        self.login(self.interno)
        self.assertNotContains(self.client.get(reverse("panel:dashboard")), reverse("panel:ofertas"))

    def test_listado_sin_n_mas_1(self):
        def n(cantidad):
            Oferta.objects.all().delete()
            for i in range(cantidad):
                self.oferta(titulo=f"O{i}", productos=[self.producto, self.producto2], servicios=[self.servicio])
            self.login(self.admin)
            return self.consultas(lambda: self.client.get(reverse("panel:ofertas")))[0]
        self.assertEqual(n(2), n(12))


class VistaClienteTests(OfertasBase):
    """RF-17: el cliente ve las ofertas vigentes que le corresponden."""

    def test_muestra_solo_las_vigentes_con_su_precio(self):
        self.oferta(titulo="Vigente", descuento=20, productos=[self.producto], servicios=[self.servicio])
        self.oferta(titulo="Vencida", inicio=HOY - timedelta(days=5), fin=HOY - timedelta(days=1), productos=[self.producto2])
        self.oferta(titulo="Programada", inicio=HOY + timedelta(days=3), fin=HOY + timedelta(days=9), productos=[self.producto2])
        self.oferta(titulo="Finalizada", finalizada=True, productos=[self.producto2])
        r = self.client.get(reverse("ofertas:lista"))
        self.assertContains(r, "Vigente")
        for no in ("Vencida", "Programada", "Finalizada"):
            self.assertNotContains(r, no)
        self.assertContains(r, "$5.600")   # 7.000 − 20 %
        self.assertContains(r, "$7.000")   # precio de lista tachado
        self.assertContains(r, "Instalación residencial")

    def test_sin_ofertas_mensaje_amable(self):
        self.assertContains(self.client.get(reverse("ofertas:lista")), "No hay ofertas vigentes")

    def test_los_visitantes_no_ven_las_exclusivas_pero_se_les_avisa(self):
        self.oferta(titulo="Para todos", productos=[self.producto])
        self.oferta(titulo="Secreta clientes", solo_clientes=True, productos=[self.producto2])
        r = self.client.get(reverse("ofertas:lista"))
        self.assertContains(r, "Para todos")
        self.assertNotContains(r, "Secreta clientes")
        self.assertContains(r, "1 oferta exclusiva")
        self.login(self.cliente)
        r = self.client.get(reverse("ofertas:lista"))
        self.assertContains(r, "Secreta clientes")
        self.assertContains(r, "Exclusiva para clientes")
        self.assertNotContains(r, "oferta exclusiva para clientes registrados")

    def test_el_inicio_destaca_ofertas_y_el_menu_las_enlaza(self):
        self.oferta(titulo="Gran descuento", descuento=30, productos=[self.producto])
        r = self.client.get("/")
        self.assertContains(r, "Ofertas vigentes")
        self.assertContains(r, "Gran descuento")
        self.assertContains(r, reverse("ofertas:lista"))

    def test_sin_ofertas_el_inicio_no_muestra_la_seccion(self):
        self.assertNotContains(self.client.get("/"), "Ofertas vigentes")

    def test_tarjeta_y_ficha_del_producto(self):
        self.oferta(descuento=20, productos=[self.producto], titulo="Semana eléctrica")
        r = self.client.get(reverse("tienda:lista"))
        self.assertContains(r, "$5.600")
        self.assertContains(r, "−20%")
        r = self.client.get(self.producto.get_absolute_url())
        self.assertContains(r, "$5.600")
        self.assertContains(r, "Semana eléctrica")
        self.assertContains(r, "IVA incluido")

    def test_catalogo_de_servicios_muestra_la_oferta(self):
        self.oferta(descuento=15, servicios=[self.servicio], titulo="Instala y ahorra")
        self.assertContains(self.client.get(reverse("catalogo:lista")), "−15%")
        self.assertContains(self.client.get(self.servicio.get_absolute_url()), "Instala y ahorra")

    def test_paginas_de_ofertas_sin_n_mas_1(self):
        def n(cantidad):
            Oferta.objects.all().delete()
            for i in range(cantidad):
                self.oferta(titulo=f"O{i}", productos=[self.producto, self.producto2], servicios=[self.servicio])
            return self.consultas(lambda: self.client.get(reverse("ofertas:lista")))[0]
        self.assertEqual(n(2), n(8))

    def test_tienda_sin_n_mas_1_con_ofertas(self):
        o = self.oferta(productos=[self.producto, self.producto2])
        pocas = self.consultas(lambda: self.client.get(reverse("tienda:lista")))[0]
        nuevos = [Producto.objects.create(categoria=self.producto.categoria, nombre=f"P{i}", precio=1000) for i in range(10)]
        o.productos.add(*nuevos)
        self.assertEqual(self.consultas(lambda: self.client.get(reverse("tienda:lista")))[0], pocas)   # 12 productos con oferta, mismas consultas


class LoMostradoEsLoCobradoTests(OfertasBase):
    """Publicidad honesta: el precio que se ve es el que se cobra (Ley 19.496)."""

    def agregar(self, producto, n=1):
        self.client.post(reverse("tienda:carrito_agregar", args=[producto.pk]), {"cantidad": n})

    def test_el_carrito_usa_el_precio_con_oferta_y_muestra_el_ahorro(self):
        self.oferta(descuento=20, productos=[self.producto])
        self.login(self.cliente)
        self.agregar(self.producto, 3)
        self.agregar(self.producto2, 1)
        r = self.client.get(reverse("tienda:carrito"))
        self.assertEqual(r.context["total"], 3 * 5600 + 25000)
        self.assertEqual(r.context["ahorro"], 3 * 1400)
        self.assertContains(r, "Ahorras con ofertas")
        self.assertContains(r, "$4.200")

    def test_la_venta_cobra_el_precio_con_oferta_y_lo_congela(self):
        o = self.oferta(descuento=20, productos=[self.producto], titulo="Verano")
        self.login(self.cliente)
        self.agregar(self.producto, 2)
        r = self.client.post(reverse("tienda:checkout"), ENTREGA)
        self.assertEqual(r.status_code, 302)
        venta = self.cliente.ventas.get()
        d = venta.detalles.get()
        self.assertEqual((venta.total, d.precio_unitario, d.precio_lista, d.oferta_titulo, d.ahorro), (11200, 5600, 7000, "Verano", 2800))
        services.finalizar_oferta(o.pk, self.admin)          # la oferta termina después de comprar
        venta.refresh_from_db()
        d.refresh_from_db()
        self.assertEqual((venta.total, d.precio_unitario), (11200, 5600))   # la venta no cambia
        self.assertContains(self.client.get(reverse("tienda:compra", args=[venta.pk])), "Verano")

    def test_servicio_crear_venta_ignora_precios_que_envie_el_navegador(self):
        self.oferta(descuento=50, productos=[self.producto])
        venta = ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1, "precio": 1, "subtotal": 1}], datos_entrega=ENTREGA)
        self.assertEqual(venta.total, 3500)

    def test_compra_sin_oferta_queda_con_precio_de_lista(self):
        venta = ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1}], datos_entrega=ENTREGA)
        d = venta.detalles.get()
        self.assertEqual((d.precio_unitario, d.precio_lista, d.oferta_titulo, d.con_oferta), (7000, 7000, "", False))

    def test_oferta_exclusiva_se_cobra_solo_a_clientes_con_sesion(self):
        self.oferta(descuento=30, productos=[self.producto], solo_clientes=True)
        self.assertEqual(services.precio_vigente(self.producto, None).precio, 7000)      # visitante: precio de lista
        venta = ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1}], datos_entrega=ENTREGA)
        self.assertEqual(venta.total, 4900)                                              # cliente: precio exclusivo

    def test_el_checkout_muestra_el_ahorro(self):
        self.oferta(descuento=20, productos=[self.producto])
        self.login(self.cliente)
        self.agregar(self.producto, 1)
        self.assertContains(self.client.get(reverse("tienda:checkout")), "Estás ahorrando $1.400")

    def test_pago_total_con_oferta(self):
        from apps.pagos import services as pagos
        self.oferta(descuento=20, productos=[self.producto])
        venta = ventas.crear_venta(cliente=self.cliente, lineas=[{"producto": self.producto, "cantidad": 1}], datos_entrega=ENTREGA)
        pago, _ = pagos.iniciar_pago(venta, "http://x/retorno")
        self.assertEqual(pago.monto, 5600)   # a la pasarela se le cobra el monto con oferta


class SolicitudesConOfertaTests(OfertasBase):
    def enviar(self, servicio=None, items=()):
        self.login(self.cliente)
        d = self.datos_solicitud()
        d["servicio"] = servicio.pk if servicio else ""
        d["items-TOTAL_FORMS"], d["items-INITIAL_FORMS"] = str(len(items)), "0"
        for i, (p, n) in enumerate(items):
            d[f"items-{i}-producto"], d[f"items-{i}-cantidad"] = p.pk, n
        return self.client.post(reverse("solicitudes:crear"), d)

    def test_precio_de_referencia_con_oferta_y_oferta_registrada(self):
        self.oferta(descuento=20, productos=[self.producto], servicios=[self.servicio], titulo="Combo solar")
        self.enviar(servicio=self.servicio, items=[(self.producto, 2)])
        s = SolicitudCotizacion.objects.get()
        self.assertEqual(s.items.get().precio_referencia, 5600)
        self.assertIn("Combo solar", s.oferta_aplicada)
        self.assertEqual(s.oferta_aplicada.count("Combo solar"), 1)   # una oferta usada dos veces se informa una sola vez

    def test_sin_oferta_no_hay_texto(self):
        self.enviar(servicio=self.servicio, items=[(self.producto, 1)])
        s = SolicitudCotizacion.objects.get()
        self.assertEqual((s.oferta_aplicada, s.items.get().precio_referencia), ("", 7000))

    def test_el_texto_sobrevive_aunque_la_oferta_termine(self):
        o = self.oferta(descuento=10, servicios=[self.servicio], titulo="Efímera")
        self.enviar(servicio=self.servicio)
        services.finalizar_oferta(o.pk, self.admin)
        self.assertIn("Efímera", SolicitudCotizacion.objects.get().oferta_aplicada)

    def test_el_admin_ve_la_oferta_y_la_cotizacion_parte_con_precio_con_oferta(self):
        from apps.cotizaciones import services as cot
        self.oferta(descuento=20, productos=[self.producto], titulo="Semana eléctrica")
        self.enviar(items=[(self.producto, 3)])
        s = SolicitudCotizacion.objects.get()
        self.login(self.admin)
        self.assertContains(self.client.get(reverse("panel:solicitud_detalle", args=[s.pk])), "Semana eléctrica")
        self.assertContains(self.client.get(reverse("panel:cotizacion_crear", args=[s.pk])), "El cliente solicitó con oferta vigente")
        self.assertEqual(cot.lineas_sugeridas(s)[0]["precio_unitario"], 4706)   # 5.600 / 1,19
