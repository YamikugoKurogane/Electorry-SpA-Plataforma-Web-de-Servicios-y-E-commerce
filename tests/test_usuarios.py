import re

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.notificaciones.models import Notificacion
from apps.usuarios.forms import RegistroForm
from apps.usuarios.models import IntentoLogin, Usuario

from .base import PW, BaseTest


class RegistroLoginTests(BaseTest):
    def datos(self, **kw):
        d = {"first_name": "Nuevo", "last_name": "Cliente", "email": "nuevo@t.cl", "telefono": "+56 9 8888 7777",
             "rut": "18.123.456-3", "password1": PW, "password2": PW, "acepta_privacidad": "on"}
        d.update(kw)
        return d

    def test_registro_exitoso(self):  # RF-01
        r = self.client.post(reverse("usuarios:registro"), self.datos())
        self.assertEqual(r.status_code, 302)
        u = Usuario.objects.get(email="nuevo@t.cl")
        self.assertTrue(u.es_cliente)
        self.assertTrue(u.acepta_privacidad and u.fecha_privacidad)

    def test_correo_unico_sin_importar_mayusculas(self):
        r = self.client.post(reverse("usuarios:registro"), self.datos(email="C1@T.cl"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe una cuenta")

    def test_campos_obligatorios_y_consentimiento(self):
        r = self.client.post(reverse("usuarios:registro"), self.datos(first_name="", acepta_privacidad=""))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Usuario.objects.filter(email="nuevo@t.cl").exists())
        self.assertContains(r, "aviso de privacidad")  # RNF-SEG-07

    def test_contrasena_debil_rechazada(self):
        r = self.client.post(reverse("usuarios:registro"), self.datos(password1="12345678", password2="12345678"))
        self.assertFalse(Usuario.objects.filter(email="nuevo@t.cl").exists())

    def test_rut_invalido_rechazado(self):
        r = self.client.post(reverse("usuarios:registro"), self.datos(rut="11.111.111-0"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "RUT")
        self.assertContains(r, "inválido")

    def test_rut_valido_se_guarda_normalizado(self):
        form = RegistroForm(data=self.datos())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["rut"], "18.123.456-3")

    def test_login_correcto_e_incorrecto(self):
        r = self.client.post(reverse("usuarios:login"), {"username": "c1@t.cl", "password": PW})
        self.assertEqual(r.status_code, 302)
        self.client.logout()
        r = self.client.post(reverse("usuarios:login"), {"username": "c1@t.cl", "password": "mala"})
        self.assertContains(r, "incorrectos")

    @override_settings(LOGIN_MAX_INTENTOS=3)
    def test_bloqueo_por_intentos_repetidos(self):  # RNF-SEG-01
        for _ in range(3):
            self.client.post(reverse("usuarios:login"), {"username": "c1@t.cl", "password": "mala"})
        r = self.client.post(reverse("usuarios:login"), {"username": "c1@t.cl", "password": PW})  # clave correcta, pero bloqueado
        self.assertContains(r, "Demasiados intentos")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_cookies_de_sesion_httponly(self):
        from django.conf import settings
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY and settings.CSRF_COOKIE_HTTPONLY)

    def test_logout_solo_por_post(self):
        self.login(self.cliente)
        self.assertEqual(self.client.get(reverse("usuarios:logout")).status_code, 405)
        self.client.post(reverse("usuarios:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PrivacidadTests(BaseTest):
    def test_privacidad_y_terminos_de_venta_disponibles(self):
        self.assertEqual(self.client.get(reverse("core:privacidad")).status_code, 200)
        self.assertContains(self.client.get(reverse("core:terminos_venta")), "Ley N.º 19.628")
        self.assertContains(self.client.get(reverse("core:terminos_venta")), "Términos de venta")

    def test_rectificar_datos(self):  # RNF-SEG-07
        self.login(self.cliente)
        self.client.post(reverse("usuarios:perfil"), {"perfil-first_name": "Carlita", "perfil-last_name": "Uno", "perfil-telefono": "+56 9 1111 1111"})
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.first_name, "Carlita")

    def test_eliminar_cuenta_anonimiza_y_conserva_historial(self):
        sol = self.crear_solicitud()
        self.login(self.cliente)
        r = self.client.post(reverse("usuarios:eliminar_cuenta"), {"password": "incorrecta"})
        self.assertEqual(r.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.is_active)
        self.client.post(reverse("usuarios:eliminar_cuenta"), {"password": PW})
        self.cliente.refresh_from_db()
        sol.refresh_from_db()
        self.assertTrue(self.cliente.anonimizado and not self.cliente.is_active)
        self.assertTrue(self.cliente.email.endswith("@anonimo.invalid"))
        self.assertEqual(sol.telefono_contacto, "")
        self.assertNotIn("Carla", sol.nombre_contacto)
        self.assertFalse(self.client.login(username="c1@t.cl", password=PW))

    def test_admin_puede_anonimizar_interno_no(self):
        self.login(self.interno)
        r = self.client.post(reverse("panel:cliente_anonimizar", args=[self.cliente.pk]))
        self.assertEqual(r.status_code, 403)
        self.login(self.admin)
        self.client.post(reverse("panel:cliente_anonimizar", args=[self.cliente.pk]))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.anonimizado)


class RecuperarPasswordTests(BaseTest):
    """Recuperación de contraseña mediante un enlace enviado por correo."""

    NUEVA = "Otra-Clave-Segura-98765"

    def pedir(self, email="c1@t.cl"):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("usuarios:recuperar_password"), {"email": email})

    def enlace(self):
        return re.search(r"https?://testserver(/\S+)", mail.outbox[-1].body).group(1)

    def abrir_enlace(self, enlace=None):
        """Abre el enlace del correo y sigue la redirección a la URL sin token; devuelve la URL del formulario."""
        r = self.client.get(enlace or self.enlace())
        self.assertEqual(r.status_code, 302)
        return r.url

    def restablecer(self, url, clave=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, {"new_password1": clave or self.NUEVA, "new_password2": clave or self.NUEVA})

    def test_envia_enlace_al_correo(self):
        r = self.pedir()
        self.assertRedirects(r, reverse("usuarios:login"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["c1@t.cl"])
        self.assertIn("/cuenta/restablecer/", mail.outbox[0].body)

    def test_respuesta_identica_si_el_correo_no_existe(self):
        r = self.client.post(reverse("usuarios:recuperar_password"), {"email": "nadie@t.cl"}, follow=True)
        self.assertContains(r, "Si el correo corresponde a una cuenta")
        self.assertEqual(len(mail.outbox), 0)
        r2 = self.client.post(reverse("usuarios:recuperar_password"), {"email": "c1@t.cl"}, follow=True)
        self.assertContains(r2, "Si el correo corresponde a una cuenta")

    def test_correo_en_mayusculas_encuentra_la_cuenta(self):
        self.pedir("C1@T.CL")
        self.assertEqual(len(mail.outbox), 1)

    def test_flujo_completo_cambia_la_contrasena(self):
        self.pedir()
        url = self.abrir_enlace()
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.restablecer(url)
        self.assertRedirects(r, reverse("usuarios:login"))
        self.assertTrue(self.client.login(username="c1@t.cl", password=self.NUEVA))
        self.client.logout()
        self.assertFalse(self.client.login(username="c1@t.cl", password=PW))

    def test_el_token_no_queda_en_la_url_del_formulario(self):
        self.pedir()
        enlace = self.enlace()
        url = self.abrir_enlace(enlace)
        self.assertTrue(url.endswith("/set-password/"))
        self.assertNotEqual(url, enlace)

    def test_enlace_de_un_solo_uso(self):
        self.pedir()
        enlace = self.enlace()
        self.restablecer(self.abrir_enlace(enlace))
        self.client.logout()
        r = self.client.get(enlace)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Enlace no válido")

    def test_enlace_manipulado_o_inexistente_es_invalido(self):
        self.pedir()
        uid, _token = self.enlace().rstrip("/").split("/")[-2:]
        for url in (f"/cuenta/restablecer/{uid}/abc-def/", "/cuenta/restablecer/xx/abc-def/", "/cuenta/restablecer/MQ/set-password/"):
            self.assertContains(self.client.get(url), "Enlace no válido")

    def test_enlace_vencido(self):
        self.pedir()
        enlace = self.enlace()
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertContains(self.client.get(enlace), "Enlace no válido")

    def test_contrasena_debil_se_rechaza_y_no_cambia(self):
        self.pedir()
        r = self.restablecer(self.abrir_enlace(), clave="12345678")
        self.assertEqual(r.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password(PW))

    def test_contrasenas_distintas_se_rechazan(self):
        self.pedir()
        url = self.abrir_enlace()
        r = self.client.post(url, {"new_password1": self.NUEVA, "new_password2": self.NUEVA + "x"})
        self.assertEqual(r.status_code, 200)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password(PW))

    def test_cuentas_inactivas_o_anonimizadas_no_reciben_enlace(self):
        Usuario.objects.filter(pk=self.cliente.pk).update(is_active=False)
        self.pedir("c1@t.cl")
        Usuario.objects.filter(pk=self.cliente2.pk).update(anonimizado=True)
        self.pedir("c2@t.cl")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(RECUPERACION_MAX_SOLICITUDES=2)
    def test_limite_de_solicitudes_por_correo(self):
        for _ in range(4):
            self.pedir()
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(RECUPERACION_MAX_SOLICITUDES_IP=2)
    def test_limite_de_solicitudes_por_ip(self):
        for correo in ("c1@t.cl", "c2@t.cl", "admin@t.cl"):
            self.pedir(correo)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(LOGIN_MAX_INTENTOS=3)
    def test_restablecer_libera_el_bloqueo_por_intentos(self):
        for _ in range(3):
            self.client.post(reverse("usuarios:login"), {"username": "c1@t.cl", "password": "mala"})
        self.assertTrue(IntentoLogin.objects.filter(email="c1@t.cl", exitoso=False).exists())
        self.pedir()
        self.restablecer(self.abrir_enlace())
        self.assertFalse(IntentoLogin.objects.filter(email="c1@t.cl", exitoso=False).exists())
        r = self.client.post(reverse("usuarios:login"), {"username": "c1@t.cl", "password": self.NUEVA})
        self.assertEqual(r.status_code, 302)

    def test_cambia_la_contrasena_cierra_otras_sesiones(self):
        otra = self.client_class()
        otra.force_login(self.cliente)
        self.assertEqual(otra.get(reverse("usuarios:perfil")).status_code, 200)
        self.pedir()
        self.restablecer(self.abrir_enlace())
        self.assertEqual(otra.get(reverse("usuarios:perfil")).status_code, 302)

    def test_avisa_el_cambio_y_no_deja_el_enlace_guardado(self):
        self.pedir()
        self.restablecer(self.abrir_enlace())
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("fue cambiada", mail.outbox[1].subject)
        self.assertEqual(Notificacion.objects.filter(evento="cambio_password", destinatario="c1@t.cl").count(), 1)
        n = Notificacion.objects.get(evento="recuperar_password")
        self.assertNotIn("/restablecer/", n.cuerpo)

    def test_queda_auditado(self):
        self.pedir()
        self.restablecer(self.abrir_enlace())
        acciones = RegistroAuditoria.objects.filter(accion="RECUPERAR_PASSWORD", entidad="usuario", entidad_id=self.cliente.pk)
        self.assertEqual(acciones.count(), 2)  # solicitud + restablecimiento

    def test_usuario_autenticado_va_al_cambio_de_contrasena(self):
        self.login(self.cliente)
        r = self.client.get(reverse("usuarios:recuperar_password"))
        self.assertRedirects(r, reverse("usuarios:cambiar_password"))

    def test_login_enlaza_a_la_recuperacion(self):
        self.assertContains(self.client.get(reverse("usuarios:login")), reverse("usuarios:recuperar_password"))

