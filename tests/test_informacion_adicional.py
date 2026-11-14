"""S4-R2 · RF-25: el personal pide información adicional dentro de la solicitud y el cliente responde."""
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.solicitudes import requerimientos as rq
from apps.solicitudes import services
from apps.solicitudes.models import Adjunto, Estado, HistorialEstado, RequerimientoInfo

from .base import BaseTest

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
PDF = b"%PDF-1.4\n" + b"0" * 100


class InfoBase(BaseTest):
    def setUp(self):
        self.sol = self.crear_solicitud(self.cliente)

    def pedir(self, pregunta="¿Cuál es la potencia contratada?", usuario=None):
        return rq.pedir_informacion(self.sol, usuario or self.admin, pregunta)

    def png(self, nombre="foto.png"):
        return SimpleUploadedFile(nombre, PNG)


class PedirInformacionTests(InfoBase):
    def test_el_personal_pide_y_queda_registrado(self):
        r = self.pedir()
        self.assertEqual((r.estado, r.creado_por, r.creado_por_nombre), ("PENDIENTE", self.admin, "Ana Admin"))
        self.assertTrue(r.pendiente)
        a = RegistroAuditoria.objects.get(entidad="requerimiento_info", entidad_id=r.pk, accion="CREAR")
        self.assertEqual(a.usuario, self.admin)

    def test_tambien_puede_el_usuario_interno(self):
        self.assertEqual(self.pedir(usuario=self.interno).creado_por, self.interno)

    def test_un_cliente_no_puede_pedir_informacion(self):
        for quien in (self.cliente, self.cliente2, None):
            with self.assertRaises(rq.RequerimientoError):
                rq.pedir_informacion(self.sol, quien, "hola")
        self.assertEqual(RequerimientoInfo.objects.count(), 0)

    def test_validaciones_de_la_pregunta(self):
        for texto in ("", "   ", None):
            with self.assertRaises(rq.RequerimientoError):
                self.pedir(texto)
        with self.assertRaises(rq.RequerimientoError):
            self.pedir("x" * (rq.MAX_PREGUNTA + 1))
        self.pedir("x" * rq.MAX_PREGUNTA)   # el límite exacto es válido

    def test_una_solicitud_pendiente_pasa_a_en_revision_con_historial(self):
        self.assertEqual(self.sol.estado, Estado.PENDIENTE)
        self.pedir()
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.EN_REVISION)
        h = HistorialEstado.objects.filter(solicitud=self.sol).latest("id")
        self.assertEqual((h.estado_anterior, h.estado_nuevo, h.usuario), (Estado.PENDIENTE, Estado.EN_REVISION, self.admin))
        self.assertIn("información adicional", h.comentario)

    def test_en_otros_estados_no_se_cambia_el_estado(self):
        services.cambiar_estado(self.sol, Estado.EN_REVISION, self.admin)
        services.cambiar_estado(self.sol, Estado.COTIZADA, self.admin)
        self.pedir()
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, Estado.COTIZADA)

    def test_no_se_pide_en_solicitudes_cerradas(self):
        services.cambiar_estado(self.sol, Estado.CANCELADA, self.admin)
        with self.assertRaises(rq.RequerimientoError) as cm:
            self.pedir()
        self.assertIn("cancelada", str(cm.exception))

    def test_maximo_de_preguntas_pendientes(self):
        for i in range(rq.MAX_PENDIENTES):
            self.pedir(f"Pregunta {i}")
        with self.assertRaises(rq.RequerimientoError):
            self.pedir("una más")
        RequerimientoInfo.objects.filter(pk=RequerimientoInfo.objects.first().pk).update(respondido_en="2026-01-01T00:00:00Z")
        self.pedir("ahora sí")   # al liberarse una, se puede preguntar de nuevo

    def test_se_avisa_al_cliente_por_correo(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.pedir("¿Cuál es la potencia contratada?")
        correos = [m for m in mail.outbox if "más información" in m.subject]
        self.assertEqual(len(correos), 1)
        self.assertEqual(correos[0].to, ["c1@t.cl"])
        self.assertIn("potencia contratada", correos[0].body)
        self.assertIn(self.sol.codigo, correos[0].subject)


class ResponderTests(InfoBase):
    def test_responde_con_texto(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "Son 10 kW")
        r.refresh_from_db()
        self.assertEqual((r.estado, r.respuesta, r.respondido_por), ("RESPONDIDO", "Son 10 kW", self.cliente))
        self.assertIsNotNone(r.respondido_en)

    def test_responde_solo_con_archivos(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "", [self.png("tablero.png")])
        r.refresh_from_db()
        a = r.adjuntos.get()
        self.assertEqual((r.estado, r.respuesta, a.nombre_original, a.solicitud_id, a.requerimiento_id), ("RESPONDIDO", "", "tablero.png", self.sol.pk, r.pk))

    def test_texto_y_archivos(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "Adjunto la boleta", [SimpleUploadedFile("boleta.pdf", PDF), self.png()])
        self.assertEqual(RequerimientoInfo.objects.get().adjuntos.count(), 2)

    def test_exige_texto_o_archivo(self):
        r = self.pedir()
        for vacio in ("", "   ", None):
            with self.assertRaises(rq.RequerimientoError):
                rq.responder_requerimiento(r.pk, self.cliente, vacio, [])
        self.assertTrue(RequerimientoInfo.objects.get().pendiente)

    def test_limites_de_respuesta(self):
        r = self.pedir()
        with self.assertRaises(rq.RequerimientoError):
            rq.responder_requerimiento(r.pk, self.cliente, "x" * (rq.MAX_RESPUESTA + 1))
        with override_settings(ADJUNTOS_MAX_CANTIDAD=1):
            with self.assertRaises(rq.RequerimientoError):
                rq.responder_requerimiento(r.pk, self.cliente, "ok", [self.png("a.png"), self.png("b.png")])
        self.assertEqual(Adjunto.objects.count(), 0)   # un intento fallido no deja archivos sueltos

    def test_solo_responde_el_dueno_de_la_solicitud(self):
        r = self.pedir()
        for intruso in (self.cliente2, self.admin, self.interno):
            with self.assertRaises(rq.RequerimientoError):
                rq.responder_requerimiento(r.pk, intruso, "me hago pasar por el cliente")
        self.assertTrue(RequerimientoInfo.objects.get().pendiente)

    def test_se_responde_una_sola_vez(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "primera")
        with self.assertRaises(rq.RequerimientoError) as cm:
            rq.responder_requerimiento(r.pk, self.cliente, "segunda")
        self.assertIn("ya fue respondida", str(cm.exception))
        self.assertEqual(RequerimientoInfo.objects.get().respuesta, "primera")

    def test_no_se_responde_una_pregunta_cancelada_ni_en_solicitud_cerrada(self):
        r1, r2 = self.pedir("a"), self.pedir("b")
        rq.cancelar_requerimiento(r1.pk, self.admin)
        with self.assertRaises(rq.RequerimientoError) as cm:
            rq.responder_requerimiento(r1.pk, self.cliente, "tarde")
        self.assertIn("cancelada", str(cm.exception))
        services.cambiar_estado(self.sol, Estado.CANCELADA, self.cliente)
        r2.refresh_from_db()
        self.assertEqual(r2.estado, "CANCELADO")   # cerrar la solicitud cierra las preguntas abiertas

    def test_auditoria_y_correos(self):
        r = self.pedir(usuario=self.interno)
        with self.settings(CORREO_AVISOS_INTERNOS="ventas@t.cl"):
            with self.captureOnCommitCallbacks(execute=True):
                rq.responder_requerimiento(r.pk, self.cliente, "Son 10 kW", [self.png()])
        a = RegistroAuditoria.objects.get(entidad="requerimiento_info", entidad_id=r.pk, accion="EDITAR")
        self.assertEqual(a.usuario, self.cliente)
        destinos = sorted(m.to[0] for m in mail.outbox if "Respuesta del cliente" in m.subject)
        self.assertEqual(destinos, ["interno@t.cl", "ventas@t.cl"])   # quien preguntó + aviso interno


class CancelarYCierreTests(InfoBase):
    def test_el_personal_cancela_una_pregunta_pendiente(self):
        r = self.pedir()
        rq.cancelar_requerimiento(r.pk, self.interno)
        r.refresh_from_db()
        self.assertEqual((r.estado, r.cancelado_por), ("CANCELADO", self.interno))
        self.assertTrue(RegistroAuditoria.objects.filter(entidad="requerimiento_info", entidad_id=r.pk, descripcion__contains="canceló").exists())

    def test_no_se_cancela_lo_respondido_ni_lo_cancela_un_cliente(self):
        r = self.pedir()
        with self.assertRaises(rq.RequerimientoError):
            rq.cancelar_requerimiento(r.pk, self.cliente)
        rq.responder_requerimiento(r.pk, self.cliente, "ok")
        with self.assertRaises(rq.RequerimientoError):
            rq.cancelar_requerimiento(r.pk, self.admin)

    def test_finalizar_o_cancelar_la_solicitud_cierra_las_preguntas_pendientes(self):
        r = self.pedir()
        resp = self.pedir("otra")
        rq.responder_requerimiento(resp.pk, self.cliente, "listo")
        services.cambiar_estado(self.sol, Estado.CANCELADA, self.admin)
        r.refresh_from_db(); resp.refresh_from_db()
        self.assertEqual((r.estado, resp.estado), ("CANCELADO", "RESPONDIDO"))   # lo respondido no se toca

    def test_la_base_impide_respondida_y_cancelada_a_la_vez(self):
        from django.db import IntegrityError, transaction
        from django.utils import timezone
        r = self.pedir()
        with self.assertRaises(IntegrityError), transaction.atomic():
            RequerimientoInfo.objects.filter(pk=r.pk).update(respondido_en=timezone.now(), cancelado_en=timezone.now())

    def test_anonimizar_al_cliente_borra_sus_respuestas_y_archivos(self):  # RNF-SEG-07
        from apps.usuarios import services as usuarios
        r = self.pedir("¿Dirección exacta?")
        rq.responder_requerimiento(r.pk, self.cliente, "Calle Secreta 123, depto 4", [self.png()])
        usuarios.anonimizar_usuario(self.cliente)
        r.refresh_from_db()
        self.assertNotIn("Secreta", r.respuesta)
        self.assertEqual(r.adjuntos.count(), 0)
        self.assertEqual(r.pregunta, "¿Dirección exacta?")   # lo que escribió el personal se conserva


class PanelInfoTests(InfoBase):
    def url_pedir(self):
        return reverse("panel:info_pedir", args=[self.sol.pk])

    def test_el_panel_muestra_la_seccion_y_el_formulario(self):
        self.login(self.admin)
        r = self.client.get(reverse("panel:solicitud_detalle", args=[self.sol.pk]))
        self.assertContains(r, "Información adicional")
        self.assertContains(r, "Pedir información al cliente")
        self.assertContains(r, "Todavía no se ha pedido información")

    def test_pedir_por_http_admin_e_interno(self):
        for usuario in (self.admin, self.interno):
            self.login(usuario)
            r = self.client.post(self.url_pedir(), {"pregunta": f"Pregunta de {usuario.rol}"}, follow=True)
            self.assertContains(r, "Pregunta enviada")
        self.assertEqual(RequerimientoInfo.objects.count(), 2)

    def test_sin_permiso(self):
        self.assertEqual(self.client.post(self.url_pedir(), {"pregunta": "x"}).status_code, 302)   # visitante → login
        self.login(self.cliente)
        self.assertEqual(self.client.post(self.url_pedir(), {"pregunta": "x"}).status_code, 403)
        self.assertEqual(RequerimientoInfo.objects.count(), 0)

    def test_solo_por_post(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(self.url_pedir()).status_code, 405)

    def test_pregunta_vacia_muestra_error(self):
        self.login(self.admin)
        r = self.client.post(self.url_pedir(), {"pregunta": "   "}, follow=True)
        self.assertContains(r, "Escribe qué información necesitas")
        self.assertEqual(RequerimientoInfo.objects.count(), 0)

    def test_cancelar_desde_el_panel(self):
        r = self.pedir()
        self.login(self.admin)
        resp = self.client.post(reverse("panel:info_cancelar", args=[r.pk]), follow=True)
        self.assertContains(resp, "Pregunta cancelada")
        r.refresh_from_db()
        self.assertEqual(r.estado, "CANCELADO")

    def test_el_panel_muestra_la_respuesta_y_los_archivos(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "Son 10 kW", [self.png("tablero.png")])
        self.login(self.admin)
        html = self.client.get(reverse("panel:solicitud_detalle", args=[self.sol.pk])).content.decode()
        self.assertIn("Son 10 kW", html)
        self.assertIn("tablero.png", html)
        self.assertIn("Respondido", html)

    def test_en_solicitud_cerrada_no_se_ofrece_pedir(self):
        services.cambiar_estado(self.sol, Estado.CANCELADA, self.admin)
        self.login(self.admin)
        self.assertNotContains(self.client.get(reverse("panel:solicitud_detalle", args=[self.sol.pk])), "Pedir información al cliente")

    def test_filtro_y_tablero_de_pendientes(self):
        otra = self.crear_solicitud(self.cliente2)
        self.pedir()
        self.login(self.admin)
        r = self.client.get(reverse("panel:solicitudes"), {"info": "pendiente"})
        self.assertEqual([s.pk for s in r.context["pagina"]], [self.sol.pk])
        self.assertContains(r, "💬 1")
        self.assertEqual(len(self.client.get(reverse("panel:solicitudes")).context["pagina"]), 2)
        self.assertEqual(self.client.get(reverse("panel:dashboard")).context["info_pendiente"], 1)
        rq.responder_requerimiento(RequerimientoInfo.objects.get().pk, self.cliente, "ok")
        self.assertEqual(self.client.get(reverse("panel:dashboard")).context["info_pendiente"], 0)
        self.assertEqual(len(self.client.get(reverse("panel:solicitudes"), {"info": "pendiente"}).context["pagina"]), 0)


class ClienteInfoTests(InfoBase):
    def url_resp(self, r):
        return reverse("solicitudes:info_responder", args=[r.pk])

    def test_el_cliente_ve_el_aviso_y_el_formulario(self):
        self.pedir("¿Cuál es la potencia contratada?")
        self.login(self.cliente)
        r = self.client.get(self.sol.get_absolute_url())
        self.assertContains(r, "Necesitamos más información de tu parte")
        self.assertContains(r, "potencia contratada")
        self.assertContains(r, "Enviar respuesta")
        self.assertContains(self.client.get(reverse("solicitudes:mis_solicitudes")), "Responder")

    def test_sin_preguntas_no_hay_seccion_ni_aviso(self):
        self.login(self.cliente)
        r = self.client.get(self.sol.get_absolute_url())
        self.assertNotContains(r, "Información adicional")
        self.assertNotContains(r, "Necesitamos más información")

    def test_responder_por_http_con_texto_y_archivo(self):
        r = self.pedir()
        self.login(self.cliente)
        resp = self.client.post(self.url_resp(r), {"respuesta": "Son 10 kW", "archivos": self.png("boleta.png")}, follow=True)
        self.assertContains(resp, "Enviamos tu respuesta")
        self.assertContains(resp, "Son 10 kW")
        self.assertContains(resp, "boleta.png")
        self.assertNotContains(resp, "Necesitamos más información de tu parte")
        r.refresh_from_db()
        self.assertEqual(r.estado, "RESPONDIDO")

    def test_los_archivos_de_la_respuesta_no_se_duplican_en_adjuntos_generales(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "listo", [self.png("solo_respuesta.png")])
        self.login(self.cliente)
        html = self.client.get(self.sol.get_absolute_url()).content.decode()
        self.assertEqual(html.count("solo_respuesta.png"), 1)

    def test_respuesta_vacia_se_rechaza_y_conserva_la_pregunta(self):
        r = self.pedir()
        self.login(self.cliente)
        resp = self.client.post(self.url_resp(r), {"respuesta": "  "})
        self.assertContains(resp, "Escribe tu respuesta o adjunta al menos un archivo")
        self.assertContains(resp, "Enviar respuesta")   # sigue pendiente
        r.refresh_from_db()
        self.assertTrue(r.pendiente)

    def test_archivo_peligroso_se_rechaza(self):
        r = self.pedir()
        self.login(self.cliente)
        resp = self.client.post(self.url_resp(r), {"respuesta": "adjunto", "archivos": SimpleUploadedFile("virus.exe", b"MZ" + b"0" * 50)})
        self.assertContains(resp, "tipo de archivo no permitido")
        r.refresh_from_db()
        self.assertTrue(r.pendiente)
        self.assertEqual(Adjunto.objects.count(), 0)

    def test_extension_falsa_se_rechaza(self):
        r = self.pedir()
        self.login(self.cliente)
        resp = self.client.post(self.url_resp(r), {"respuesta": "x", "archivos": SimpleUploadedFile("script.png", b"<?php evil ?>")})
        self.assertContains(resp, "no es un archivo PNG válido")

    def test_un_cliente_ajeno_no_puede_responder_ni_ver(self):
        r = self.pedir()
        self.login(self.cliente2)
        self.assertEqual(self.client.post(self.url_resp(r), {"respuesta": "intruso"}).status_code, 404)
        self.assertEqual(self.client.get(self.sol.get_absolute_url()).status_code, 404)
        self.assertTrue(RequerimientoInfo.objects.get().pendiente)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="ACCESO_DENEGADO").exists())

    def test_el_personal_no_responde_por_el_cliente_y_el_visitante_va_al_login(self):
        r = self.pedir()
        self.assertEqual(self.client.post(self.url_resp(r), {"respuesta": "x"}).status_code, 302)
        self.login(self.admin)
        self.assertEqual(self.client.post(self.url_resp(r), {"respuesta": "x"}).status_code, 403)
        self.assertTrue(RequerimientoInfo.objects.get().pendiente)

    def test_solo_por_post(self):
        r = self.pedir()
        self.login(self.cliente)
        self.assertEqual(self.client.get(self.url_resp(r)).status_code, 405)

    def test_pregunta_inexistente(self):
        self.login(self.cliente)
        self.assertEqual(self.client.post(reverse("solicitudes:info_responder", args=[99999]), {"respuesta": "x"}).status_code, 404)

    def test_responder_dos_veces_muestra_error_amable(self):
        r = self.pedir()
        self.login(self.cliente)
        self.client.post(self.url_resp(r), {"respuesta": "primera"})
        resp = self.client.post(self.url_resp(r), {"respuesta": "segunda"})
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.respuesta, "primera")

    def test_descarga_de_adjuntos_de_respuesta(self):
        r = self.pedir()
        rq.responder_requerimiento(r.pk, self.cliente, "", [self.png("plano.png")])
        a = Adjunto.objects.get()
        url = reverse("solicitudes:adjunto", args=[a.pk])
        self.login(self.cliente)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.login(self.cliente2)
        self.assertEqual(self.client.get(url).status_code, 404)   # otro cliente no descarga archivos ajenos

    def test_varias_preguntas_cada_una_con_su_formulario(self):
        a, b = self.pedir("Primera"), self.pedir("Segunda")
        self.login(self.cliente)
        html = self.client.get(self.sol.get_absolute_url()).content.decode()
        self.assertIn(self.url_resp(a), html)
        self.assertIn(self.url_resp(b), html)
        self.assertIn(f"id_resp{a.pk}_respuesta", html)   # ids únicos por pregunta
        self.assertIn(f"id_resp{b.pk}_respuesta", html)
        self.client.post(self.url_resp(a), {"respuesta": "A"})
        self.assertTrue(RequerimientoInfo.objects.get(pk=b.pk).pendiente)   # responder una no cierra la otra
        self.assertContains(self.client.get(self.sol.get_absolute_url()), "Tienes 1 pregunta sin responder")


class RendimientoInfoTests(InfoBase):
    def test_las_listas_no_hacen_consultas_por_fila(self):  # RNF-PER-02
        def consultas(url, usuario):
            self.login(usuario)
            with CaptureQueriesContext(connection) as c:
                self.client.get(url)
            return len(c)

        def agregar(n):
            for _ in range(n):
                s = self.crear_solicitud(self.cliente)
                rq.pedir_informacion(s, self.admin, "¿Dato?")

        agregar(2)
        mis_2 = consultas(reverse("solicitudes:mis_solicitudes"), self.cliente)
        panel_2 = consultas(reverse("panel:solicitudes"), self.admin)
        agregar(6)
        self.assertEqual(consultas(reverse("solicitudes:mis_solicitudes"), self.cliente), mis_2)
        self.assertEqual(consultas(reverse("panel:solicitudes"), self.admin), panel_2)
