from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .models import SolicitudCotizacion


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
