from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.usuarios.models import IntentoLogin, Usuario

from .base import PW, BaseTest


class RegistroLoginTests(BaseTest):
    def datos(self, **kw):
        d = {"first_name": "Nuevo", "last_name": "Cliente", "email": "nuevo@t.cl", "telefono": "+56 9 8888 7777",
             "password1": PW, "password2": PW, "acepta_privacidad": "on"}
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
