from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.notificaciones.models import Notificacion
from apps.solicitudes import services
from apps.solicitudes.models import Adjunto, Estado, HistorialEstado, SolicitudCotizacion

from .base import BaseTest

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
PDF = b"%PDF-1.4\n" + b"0" * 100


class CrearSolicitudTests(BaseTest):
    def test_visitante_debe_registrarse(self):  # T1
        r = self.client.post(reverse("solicitudes:crear"), self.datos_solicitud())
        self.assertEqual(r.status_code, 302)
        self.assertIn("/cuenta/ingresar/", r["Location"])
        self.assertEqual(SolicitudCotizacion.objects.count(), 0)

    def test_crea_solicitud_con_estado_inicial_historial_y_auditoria(self):  # RF-03, RF-15
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), self.datos_solicitud())
        self.assertEqual(r.status_code, 302)
        s = SolicitudCotizacion.objects.get()
        self.assertEqual(s.estado, Estado.PENDIENTE)
        self.assertEqual(s.cliente, self.cliente)
        self.assertIsNotNone(s.creada)
        self.assertEqual(HistorialEstado.objects.filter(solicitud=s).count(), 1)
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="solicitud", entidad_id=s.pk, accion="CREAR").exists())

    def test_validacion_de_servidor(self):
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), self.datos_solicitud(descripcion="corta", email_contacto="no-es-correo"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SolicitudCotizacion.objects.count(), 0)

    def test_servicio_no_disponible_rechazado(self):
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), self.datos_solicitud(servicio=self.servicio_off.pk))
        self.assertEqual(SolicitudCotizacion.objects.count(), 0)

    def test_personal_no_crea_solicitudes(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("solicitudes:crear")).status_code, 403)

    def test_adjuntos_validos(self):  # EC-10
        self.login(self.cliente)
        self.client.post(reverse("solicitudes:crear"), {**self.datos_solicitud(), "archivos": [
            SimpleUploadedFile("foto.png", PNG), SimpleUploadedFile("plano.pdf", PDF)]})
        s = SolicitudCotizacion.objects.get()
        self.assertEqual(s.adjuntos.count(), 2)
        nombre = s.adjuntos.first().archivo.name
        self.assertNotIn("foto", nombre)  # nombre aleatorio

    def test_adjunto_ejecutable_rechazado(self):  # EC-10
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), {**self.datos_solicitud(), "archivos": SimpleUploadedFile("virus.exe", b"MZ" + b"0" * 50)})
        self.assertContains(r, "tipo de archivo no permitido")
        self.assertEqual(SolicitudCotizacion.objects.count(), 0)

    def test_adjunto_con_extension_falsa_rechazado(self):
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), {**self.datos_solicitud(), "archivos": SimpleUploadedFile("script.png", b"<?php evil ?>")})
        self.assertContains(r, "no es un archivo PNG válido")

    @override_settings(ADJUNTO_MAX_BYTES=50)
    def test_adjunto_demasiado_grande_rechazado(self):
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), {**self.datos_solicitud(), "archivos": SimpleUploadedFile("g.png", PNG)})
        self.assertContains(r, "supera el tamaño máximo")

    @override_settings(ADJUNTOS_MAX_CANTIDAD=1)
    def test_demasiados_adjuntos(self):
        self.login(self.cliente)
        r = self.client.post(reverse("solicitudes:crear"), {**self.datos_solicitud(), "archivos": [SimpleUploadedFile("a.png", PNG), SimpleUploadedFile("b.png", PNG)]})
        self.assertContains(r, "hasta 1 archivos")


class AutorizacionPorObjetoTests(BaseTest):
    """EC-01: 0 accesos indebidos."""

    def setUp(self):
        self.sol = self.crear_solicitud(self.cliente)

    def test_cliente_ve_la_suya(self):
        self.login(self.cliente)
        self.assertEqual(self.client.get(reverse("solicitudes:detalle", args=[self.sol.pk])).status_code, 200)

    def test_cliente_no_ve_ajena_y_queda_registrado(self):
        self.login(self.cliente2)
        r = self.client.get(reverse("solicitudes:detalle", args=[self.sol.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="ACCESO_DENEGADO").exists())

    def test_cliente_no_ve_listado_ajeno(self):
        self.login(self.cliente2)
        r = self.client.get(reverse("solicitudes:mis_solicitudes"))
        self.assertNotContains(r, self.sol.codigo)

    def test_adjunto_ajeno_no_descargable(self):
        adj = Adjunto.objects.create(solicitud=self.sol, archivo=SimpleUploadedFile("x.png", PNG), nombre_original="x.png", tamano=108)
        self.login(self.cliente2)
        self.assertEqual(self.client.get(reverse("solicitudes:adjunto", args=[adj.pk])).status_code, 404)
        self.login(self.cliente)
        r = self.client.get(reverse("solicitudes:adjunto", args=[adj.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.login(self.interno)
        self.assertEqual(self.client.get(reverse("solicitudes:adjunto", args=[adj.pk])).status_code, 200)

    def test_visitante_redirigido_a_login(self):
        for url in (reverse("solicitudes:detalle", args=[self.sol.pk]), reverse("panel:dashboard"), reverse("solicitudes:mis_solicitudes")):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)

    def test_cliente_no_accede_a_ninguna_pantalla_del_panel(self):
        self.login(self.cliente)
        from django.urls import get_resolver
        rutas = [
            reverse("panel:dashboard"), reverse("panel:solicitudes"), reverse("panel:solicitud_detalle", args=[self.sol.pk]),
            reverse("panel:cotizaciones"), reverse("panel:clientes"), reverse("panel:ventas"), reverse("panel:servicios"),
            reverse("panel:productos"), reverse("panel:usuarios"), reverse("panel:reportes"), reverse("panel:auditoria"),
            reverse("panel:notificaciones"), reverse("panel:cotizacion_crear", args=[self.sol.pk]),
        ]
        for url in rutas:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_interno_no_accede_a_pantallas_de_admin(self):
        self.login(self.interno)
        for name in ("panel:usuarios", "panel:reportes", "panel:auditoria", "panel:servicios", "panel:productos", "panel:notificaciones"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        for name in ("panel:dashboard", "panel:solicitudes", "panel:cotizaciones", "panel:clientes", "panel:ventas"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class EstadosTests(BaseTest):
    def setUp(self):
        self.sol = self.crear_solicitud()

    def test_flujo_completo_con_historial(self):  # RF-05, EC-08
        for est in (Estado.EN_REVISION, Estado.COTIZADA, Estado.ACEPTADA, Estado.EN_EJECUCION, Estado.FINALIZADA):
            services.cambiar_estado(self.sol, est, self.admin, "ok")
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.FINALIZADA)
        hist = list(HistorialEstado.objects.filter(solicitud=self.sol).order_by("id"))
        self.assertEqual(len(hist), 6)
        for h in hist[1:]:  # 100 % registran usuario, fecha, anterior y nuevo (RNF-AUD-01)
            self.assertEqual(h.usuario, self.admin)
            self.assertTrue(h.estado_anterior and h.estado_nuevo and h.fecha)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="CAMBIO_ESTADO", entidad_id=self.sol.pk).count(), 5)

    def test_transicion_invalida(self):
        with self.assertRaises(services.TransicionInvalida):
            services.cambiar_estado(self.sol, Estado.FINALIZADA, self.admin)
        with self.assertRaises(services.TransicionInvalida):
            services.cambiar_estado(self.sol, Estado.PENDIENTE, self.admin)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.PENDIENTE)

    def test_estado_final_no_cambia(self):
        services.cambiar_estado(self.sol, Estado.CANCELADA, self.admin)
        with self.assertRaises(services.TransicionInvalida):
            services.cambiar_estado(self.sol, Estado.EN_REVISION, self.admin)

    def test_cambio_por_panel_y_cliente_ve_historial(self):
        self.login(self.admin)
        r = self.client.post(reverse("panel:solicitud_detalle", args=[self.sol.pk]), {"estado": "EN_REVISION", "comentario": "Visita agendada"})
        self.assertEqual(r.status_code, 302)
        self.login(self.cliente)
        r = self.client.get(reverse("solicitudes:detalle", args=[self.sol.pk]))
        self.assertContains(r, "En revisión")
        self.assertContains(r, "Visita agendada")

    def test_panel_rechaza_estado_invalido(self):
        self.login(self.admin)
        self.client.post(reverse("panel:solicitud_detalle", args=[self.sol.pk]), {"estado": "FINALIZADA"})
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.PENDIENTE)

    def test_historial_atomico_con_el_cambio(self):  # NR4
        from unittest import mock
        with mock.patch("apps.solicitudes.services.HistorialEstado.objects.create", side_effect=RuntimeError("falla")):
            with self.assertRaises(RuntimeError):
                services.cambiar_estado(self.sol, Estado.EN_REVISION, self.admin)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.PENDIENTE)  # el cambio se revirtió

    def test_filtros_del_panel(self):
        self.crear_solicitud(self.cliente2)
        services.cambiar_estado(self.sol, Estado.EN_REVISION, self.admin)
        self.login(self.admin)
        r = self.client.get(reverse("panel:solicitudes"), {"estado": "EN_REVISION"})
        self.assertContains(r, self.sol.codigo)
        self.assertEqual(len(r.context["pagina"]), 1)
        r = self.client.get(reverse("panel:solicitudes"), {"q": "c2@t.cl"})
        self.assertEqual(len(r.context["pagina"]), 0)  # el contacto es c1@t.cl en datos de prueba


class NotificacionesTests(BaseTest):
    def test_cambio_de_estado_envia_correo(self):  # RF-11
        sol = self.crear_solicitud()
        with self.captureOnCommitCallbacks(execute=True):
            services.cambiar_estado(sol, Estado.EN_REVISION, self.admin, "Lo revisamos")
        self.assertTrue(any("cambió de estado" in m.subject for m in mail.outbox))

    def test_falla_de_correo_no_pierde_la_solicitud(self):  # EC-06, RNF-DIS-02
        from unittest import mock
        self.login(self.cliente)
        with mock.patch("apps.notificaciones.services.send_mail", side_effect=ConnectionError("smtp caído")):
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post(reverse("solicitudes:crear"), self.datos_solicitud())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SolicitudCotizacion.objects.count(), 1)  # 0 solicitudes perdidas
        n = Notificacion.objects.get()
        self.assertEqual(n.estado, Notificacion.Estado.PENDIENTE)
        self.assertIn("smtp caído", n.ultimo_error)

    def test_reintento_posterior_envia(self):
        from unittest import mock
        from apps.notificaciones import services as ns
        with mock.patch("apps.notificaciones.services.send_mail", side_effect=ConnectionError("x")):
            with self.captureOnCommitCallbacks(execute=True):
                ns.notificar("a@b.cl", "Hola", "cuerpo")
        self.assertEqual(ns.reintentar_pendientes(), 1)
        self.assertEqual(Notificacion.objects.get().estado, Notificacion.Estado.ENVIADA)

    @override_settings(NOTIFICACION_MAX_INTENTOS=2)
    def test_pasa_a_fallida_tras_max_intentos(self):
        from unittest import mock
        from apps.notificaciones import services as ns
        with mock.patch("apps.notificaciones.services.send_mail", side_effect=ConnectionError("x")):
            with self.captureOnCommitCallbacks(execute=True):
                ns.notificar("a@b.cl", "Hola", "cuerpo")
            ns.reintentar_pendientes()
        self.assertEqual(Notificacion.objects.get().estado, Notificacion.Estado.FALLIDA)
