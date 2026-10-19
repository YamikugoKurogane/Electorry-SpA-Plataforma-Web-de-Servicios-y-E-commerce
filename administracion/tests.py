from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

class PruebasSeguridadRBAC(TestCase):
    def setUp(self):
        self.client = Client()
        # Usuario cliente común
        self.user_cliente = User.objects.create_user(username='cliente_test', password='password123')
        # Usuario administrador
        self.user_admin = User.objects.create_superuser(username='admin_test', password='password123')

    def test_acceso_denegado_usuario_no_autenticado(self):
        """[QA-01] Un usuario no autenticado no debe entrar a la administracion"""
        response = self.client.get('/administracion/')
        self.assertNotEqual(response.status_code, 200)

    def test_acceso_denegado_cliente_comun(self):
        """[QA-02] Un cliente comun no debe acceder al panel administrativo (RBAC)"""
        self.client.login(username='cliente_test', password='password123')
        response = self.client.get('/administracion/')
        self.assertNotEqual(response.status_code, 200)

    def test_acceso_permitido_admin(self):
        """[QA-03] El usuario administrador accede exitosamente"""
        self.client.login(username='admin_test', password='password123')
        response = self.client.get('/administracion/')
        self.assertEqual(response.status_code, 200)
