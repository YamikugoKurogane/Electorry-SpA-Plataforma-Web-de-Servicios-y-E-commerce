from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import RegistroAuditoria
from apps.catalogo.models import Servicio
from apps.cotizaciones import services as cot
from apps.solicitudes import services as sol
from apps.solicitudes.models import Estado
from apps.tienda.models import Producto
from apps.usuarios.models import Rol, Usuario

from .base import PW, BaseTest


class CatalogoPublicoTests(BaseTest):
    def test_catalogo_publico_sin_login(self):  # RF-02
        r = self.client.get(reverse("catalogo:lista"))
        self.assertContains(r, "Instalación residencial")
        r = self.client.get(self.servicio.get_absolute_url())
        self.assertContains(r, "Disponible")
        self.assertContains(self.client.get(self.servicio_off.get_absolute_url()), "No disponible")

    def test_busqueda_y_filtro(self):
        r = self.client.get(reverse("catalogo:lista"), {"q": "residencial"})
        self.assertEqual(len(r.context["pagina"]), 1)

    def test_paginacion(self):
        for i in range(12):
            Servicio.objects.create(categoria=self.servicio.categoria, nombre=f"S{i}", resumen="r", descripcion="d")
        r = self.client.get(reverse("catalogo:lista"))
        self.assertTrue(r.context["pagina"].has_next())

    def test_inicio_y_privacidad_y_salud(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get(reverse("core:privacidad")).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:salud")).json(), {"estado": "ok"})

    def test_pagina_404_controlada(self):
        r = self.client.get("/no-existe/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Página no encontrada", status_code=404)

    def test_catalogo_rendimiento_consultas_constantes(self):  # RNF-PER-02, EC-05
        for i in range(8):
            Servicio.objects.create(categoria=self.servicio.categoria, nombre=f"X{i}", resumen="r", descripcion="d")
        with self.assertNumQueries(3):
            self.client.get(reverse("catalogo:lista"))

    def test_productos_publicos(self):
        self.assertContains(self.client.get(reverse("tienda:lista")), "Disyuntor 20A")
        self.assertContains(self.client.get(self.producto.get_absolute_url()), "$7.000")

    def test_api_solo_lectura(self):
        r = self.client.get("/api/v1/servicios/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)
        self.assertEqual(self.client.post("/api/v1/servicios/", {}).status_code, 405)
        self.assertEqual(self.client.get("/api/v1/productos/").json()["count"], 2)


class PanelCrudTests(BaseTest):
    def test_crud_servicios_con_auditoria(self):  # RF-06
        self.login(self.admin)
        r = self.client.post(reverse("panel:servicio_crear"), {"categoria": self.servicio.categoria_id, "nombre": "Nuevo servicio", "resumen": "r", "descripcion": "d", "disponible": "on"})
        self.assertEqual(r.status_code, 302)
        s = Servicio.objects.get(nombre="Nuevo servicio")
        self.assertEqual(s.slug, "nuevo-servicio")
        self.client.post(reverse("panel:servicio_editar", args=[s.pk]), {"categoria": s.categoria_id, "nombre": "Nuevo servicio", "resumen": "cambiado", "descripcion": "d"})
        s.refresh_from_db()
        self.assertEqual(s.resumen, "cambiado")
        self.assertFalse(s.disponible)
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="servicio", accion="EDITAR").exists())
        self.client.post(reverse("panel:servicio_eliminar", args=[s.pk]))
        self.assertFalse(Servicio.objects.filter(pk=s.pk).exists())

    def test_servicio_con_solicitudes_se_desactiva_no_se_borra(self):
        self.crear_solicitud()
        self.login(self.admin)
        self.client.post(reverse("panel:servicio_eliminar", args=[self.servicio.pk]))
        self.servicio.refresh_from_db()
        self.assertFalse(self.servicio.disponible)

    def test_crud_productos(self):  # RF-12
        self.login(self.admin)
        r = self.client.post(reverse("panel:producto_crear"), {"categoria": self.producto.categoria_id, "nombre": "Cable", "precio": "1500", "activo": "on", "descripcion": ""})
        self.assertEqual(r.status_code, 302)
        r = self.client.post(reverse("panel:producto_crear"), {"categoria": self.producto.categoria_id, "nombre": "Malo", "precio": "0"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Producto.objects.filter(nombre="Malo").count(), 0)

    def test_usuarios_y_roles(self):  # RF-10
        self.login(self.admin)
        r = self.client.post(reverse("panel:usuario_crear"), {"first_name": "Nuevo", "last_name": "Interno", "email": "n@t.cl", "telefono": "", "rol": Rol.INTERNO, "is_active": "on", "password": PW})
        self.assertEqual(r.status_code, 302)
        u = Usuario.objects.get(email="n@t.cl")
        self.assertEqual(u.rol, Rol.INTERNO)
        self.assertTrue(u.check_password(PW))
        self.assertFalse(u.is_staff)

    def test_admin_no_puede_quitarse_su_acceso(self):
        self.login(self.admin)
        self.client.post(reverse("panel:usuario_editar", args=[self.admin.pk]), {"first_name": "Ana", "last_name": "Admin", "email": "admin@t.cl", "telefono": "", "rol": Rol.CLIENTE, "is_active": "on"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, Rol.ADMIN)

    def test_clientes_historial(self):  # RF-07
        self.crear_solicitud()
        self.login(self.interno)
        r = self.client.get(reverse("panel:cliente_detalle", args=[self.cliente.pk]))
        self.assertContains(r, "SOL-")
        self.assertContains(self.client.get(reverse("panel:clientes"), {"q": "Carla"}), "Carla")

    def test_auditoria_visible_solo_admin(self):
        self.crear_solicitud()
        self.login(self.admin)
        r = self.client.get(reverse("panel:auditoria"), {"entidad": "solicitud"})
        self.assertContains(r, "Solicitud SOL-")


class ReportesTests(BaseTest):
    def setUp(self):
        self.s1 = self.crear_solicitud()
        self.s2 = self.crear_solicitud(self.cliente2)
        lineas = [{"descripcion": "x", "cantidad": 1, "precio_unitario": 100000}]
        c = cot.crear_cotizacion(solicitud=self.s1, usuario=self.admin, lineas=lineas)
        cot.enviar_cotizacion(c, self.admin)
        cot.responder_cotizacion(c, self.cliente, True)

    def test_reporte_solicitudes_y_cotizaciones(self):  # RF-09
        self.login(self.admin)
        r = self.client.get(reverse("panel:reportes"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["solicitudes"]["total"], 2)
        self.assertEqual(r.context["cotizaciones"]["monto_aceptado_neto"], 100000)
        self.assertEqual(r.context["cotizaciones"]["monto_aceptado_total"], 119000)
        self.assertEqual(r.context["cotizaciones"]["tasa_aceptacion"], 100)

    def test_rango_de_fechas_excluye(self):
        self.login(self.admin)
        ayer = (timezone.localdate() - timedelta(days=10)).isoformat()
        r = self.client.get(reverse("panel:reportes"), {"desde": ayer, "hasta": ayer})
        self.assertEqual(r.context["solicitudes"]["total"], 0)

    def test_exportar_csv(self):
        self.login(self.admin)
        r = self.client.get(reverse("panel:reportes"), {"exportar": "solicitudes"})
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("SOL-", r.content.decode())
        r = self.client.get(reverse("panel:reportes"), {"exportar": "cotizaciones"})
        self.assertIn("COT-", r.content.decode())

    def test_reportes_solo_admin(self):
        self.login(self.interno)
        self.assertEqual(self.client.get(reverse("panel:reportes")).status_code, 403)
