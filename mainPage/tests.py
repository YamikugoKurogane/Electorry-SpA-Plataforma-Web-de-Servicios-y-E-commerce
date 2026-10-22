from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .models import SolicitudCotizacion

User = get_user_model()


class SolicitudCotizacionViewTests(TestCase):
    def test_home_renders_quote_form(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "name=\"nombre\"")
        self.assertContains(response, "name=\"correo\"")

    def test_home_submits_quote_request(self):
        payload = {
            "nombre": "Ana",
            "apellido": "García",
            "correo": "ana@example.com",
            "telefono": "+56912345678",
            "tipo_solicitud": "INSTALACION_ELECTRICA",
            "descripcion": "Necesito instalación eléctrica para un local.",
            "ubicacion": "Santiago",
            "observaciones": "Urgente",
        }

        response = self.client.post(reverse("home"), payload)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(SolicitudCotizacion.objects.filter(correo="ana@example.com").exists())

        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("enviada" in str(message).lower() for message in messages))


class AdminCrudTemplateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="secret123",
            is_staff=True,
        )
        self.client.force_login(self.admin)

    def test_admin_productos_page_renders(self):
        response = self.client.get(reverse("admin_productos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mantenedor de Productos")
        self.assertContains(response, "Nuevo producto")

    def test_admin_servicios_page_renders(self):
        response = self.client.get(reverse("admin_servicios"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mantenedor de Servicios")
        self.assertContains(response, "Nuevo servicio")
