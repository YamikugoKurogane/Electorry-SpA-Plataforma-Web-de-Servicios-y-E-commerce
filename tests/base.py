import shutil
import tempfile

from django.test import TestCase, override_settings

from apps.catalogo.models import CategoriaServicio, Servicio
from apps.tienda.models import CategoriaProducto, Producto
from apps.usuarios.models import Rol, Usuario

PW = "Clave-Segura-12345"
_MEDIA = tempfile.mkdtemp(prefix="electorry-test-media-")


@override_settings(MEDIA_ROOT=_MEDIA)
class BaseTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user("admin@t.cl", PW, first_name="Ana", last_name="Admin", rol=Rol.ADMIN)
        cls.interno = Usuario.objects.create_user("interno@t.cl", PW, first_name="Ivo", last_name="Interno", rol=Rol.INTERNO)
        cls.cliente = Usuario.objects.create_user("c1@t.cl", PW, first_name="Carla", last_name="Uno", telefono="+56911111111", acepta_privacidad=True)
        cls.cliente2 = Usuario.objects.create_user("c2@t.cl", PW, first_name="Pedro", last_name="Dos", telefono="+56922222222", acepta_privacidad=True)
        cat = CategoriaServicio.objects.create(nombre="Instalaciones")
        cls.servicio = Servicio.objects.create(categoria=cat, nombre="Instalación residencial", resumen="r", descripcion="d")
        cls.servicio_off = Servicio.objects.create(categoria=cat, nombre="Servicio apagado", resumen="r", descripcion="d", disponible=False)
        cp = CategoriaProducto.objects.create(nombre="Protecciones")
        cls.producto = Producto.objects.create(categoria=cp, nombre="Disyuntor 20A", precio=7000, descripcion="x")
        cls.producto2 = Producto.objects.create(categoria=cp, nombre="Diferencial", precio=25000, descripcion="y")

    def login(self, usuario):
        self.client.force_login(usuario)

    def datos_solicitud(self, **extra):
        d = {
            "servicio": self.servicio.pk, "descripcion": "Necesito instalar un tablero nuevo en mi casa",
            "direccion": "Calle 123", "comuna": "Melipilla", "nombre_contacto": "Carla Uno",
            "telefono_contacto": "+56911111111", "email_contacto": "c1@t.cl",
        }
        d.update(extra)
        return d

    def crear_solicitud(self, cliente=None):
        from apps.solicitudes import services

        d = self.datos_solicitud()
        d["servicio"] = self.servicio
        return services.crear_solicitud(cliente=cliente or self.cliente, servicio=self.servicio, datos=d)
