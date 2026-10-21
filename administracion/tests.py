from django.test import TestCase, Client  # type: ignore[reportMissingImports]
from django.urls import reverse  # type: ignore[reportMissingImports]
from django.contrib.auth.models import User  # type: ignore[reportMissingImports]
from mainPage.models import Servicio  # type: ignore[reportMissingImports]


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


class ServicioCRUDTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        # Usuario administrador
        self.admin_user = User.objects.create_superuser(
            username='admin_test_crud',
            email='admin@electorry.cl',
            password='password123'
        )
        # Usuario cliente sin permisos
        self.cliente_user = User.objects.create_user(
            username='cliente_test_crud',
            email='cliente@electorry.cl',
            password='password123'
        )

    # ------------------------------------------------------------
    # Caso de Prueba 04: Creación exitosa desde cuenta administrador
    # ------------------------------------------------------------
    def test_creacion_exitosa_servicio_admin(self):
        """[QA-04] Creación exitosa de servicio desde cuenta administrador"""
        self.client.login(username='admin_test_crud', password='password123')
        
        data = {
            'nombre': 'Mantenimiento Preventivo Inversor',
            'descripcion': 'Limpieza y revisión de conexiones de inversor',
            'precio_referencial': 85000.00,
            'estado': True
        }
        
        response = self.client.post(reverse('servicio_crear'), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Servicio.objects.filter(nombre='Mantenimiento Preventivo Inversor').exists())

    # ------------------------------------------------------------
    # Caso de Prueba 05: Intento denegado desde usuario no autenticado / cliente
    # ------------------------------------------------------------
    def test_intento_denegado_creacion_cliente_o_anonimo(self):
        """[QA-05] Intento denegado de modificación CRUD desde usuario no autenticado/cliente"""
        # 1. Anónimo
        data = {
            'nombre': 'Intento Anónimo',
            'descripcion': 'Sin acceso',
            'precio_referencial': 1000.00,
            'estado': True
        }
        response_anon = self.client.post(reverse('servicio_crear'), data)
        self.assertEqual(response_anon.status_code, 302)
        self.assertFalse(Servicio.objects.filter(nombre='Intento Anónimo').exists())

        # 2. Cliente común (RBAC)
        self.client.login(username='cliente_test_crud', password='password123')
        data_cliente = {
            'nombre': 'Intento Cliente',
            'descripcion': 'Sin permiso',
            'precio_referencial': 2000.00,
            'estado': True
        }
        response_cliente = self.client.post(reverse('servicio_crear'), data_cliente)
        self.assertEqual(response_cliente.status_code, 302)
        self.assertFalse(Servicio.objects.filter(nombre='Intento Cliente').exists())
