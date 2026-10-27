import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.auditoria.models import RegistroAuditoria
from apps.catalogo.models import Servicio
from apps.tienda.models import Producto

SERV = "categoria;nombre;resumen;descripcion;disponible\nInstalaciones;Instalación de tablero;Tablero nuevo;Incluye materiales y mano de obra.;Sí\n"
PROD = "categoria;nombre;descripcion;precio;activo;imagen\nProtecciones;Disyuntor 20A;Termomagnético;$6.990;Sí;\nCables;Cable 2,5 mm;Rollo 100 m;54990;no;\n"


class ImportarContenidoTests(TestCase):
    def carpeta(self, serv=SERV, prod=PROD, codificacion="utf-8-sig"):
        d = Path(tempfile.mkdtemp(prefix="contenido-"))
        if serv is not None:
            (d / "servicios.csv").write_text(serv, encoding=codificacion)
        if prod is not None:
            (d / "productos.csv").write_text(prod, encoding=codificacion)
        return d

    def correr(self, d, *args):
        out = StringIO()
        call_command("importar_contenido", str(d), *args, stdout=out)
        return out.getvalue()

    def test_importa_servicios_y_productos(self):
        self.correr(self.carpeta())
        self.assertEqual(Servicio.objects.get().categoria.nombre, "Instalaciones")
        self.assertEqual(Producto.objects.get(nombre="Disyuntor 20A").precio, 6990)
        self.assertFalse(Producto.objects.get(nombre="Cable 2,5 mm").activo)
        self.assertTrue(RegistroAuditoria.objects.filter(descripcion__startswith="Importación de contenido").exists())

    def test_es_repetible_sin_duplicar(self):
        d = self.carpeta()
        self.correr(d)
        salida = self.correr(d)
        self.assertEqual(Servicio.objects.count(), 1)
        self.assertEqual(Producto.objects.count(), 2)
        self.assertIn("sin cambios:   1", salida)

    def test_actualiza_si_cambia_el_precio(self):
        self.correr(self.carpeta())
        self.correr(self.carpeta(prod=PROD.replace("$6.990", "7500")))
        self.assertEqual(Producto.objects.get(nombre="Disyuntor 20A").precio, 7500)
        self.assertEqual(Producto.objects.count(), 2)

    def test_simular_no_guarda(self):
        self.correr(self.carpeta(), "--simular")
        self.assertEqual(Servicio.objects.count() + Producto.objects.count(), 0)

    def test_error_no_guarda_nada_y_informa_linea(self):
        malo = PROD + "Cables;Cable malo;x;abc;Sí;\n"
        d = self.carpeta(prod=malo)
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("importar_contenido", str(d), stdout=out)
        self.assertIn("línea 4", out.getvalue())
        self.assertEqual(Servicio.objects.count() + Producto.objects.count(), 0)  # ni el servicio válido

    def test_columnas_faltantes(self):
        d = self.carpeta(serv="nombre;resumen\nX;Y\n", prod=None)
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("importar_contenido", str(d), stdout=out)
        self.assertIn("faltan las columnas", out.getvalue())

    def test_acepta_coma_ansi_y_encabezados_con_tilde(self):
        serv = "Categoría,Nombre,Resumen,Descripción\nMantención,Revisión eléctrica,Revisamos tu casa,Detalle completo\n"
        self.correr(self.carpeta(serv=serv, prod=None, codificacion="cp1252"))
        self.assertEqual(Servicio.objects.get().nombre, "Revisión eléctrica")

    def test_ignora_filas_de_ejemplo(self):
        serv = SERV + "# EJEMPLO;ignorar;;;\n"
        self.correr(self.carpeta(serv=serv, prod=None))
        self.assertEqual(Servicio.objects.count(), 1)

    def test_valor_booleano_invalido(self):
        d = self.carpeta(serv=SERV.replace("Sí", "tal vez"), prod=None)
        with self.assertRaises(CommandError):
            call_command("importar_contenido", str(d), stdout=StringIO())

    def test_imagen_inexistente(self):
        d = self.carpeta(prod=PROD.replace("Termomagnético;$6.990;Sí;", "Termomagnético;$6.990;Sí;fantasma.jpg"))
        with self.assertRaises(CommandError):
            call_command("importar_contenido", str(d), stdout=StringIO())

    def test_plantillas_del_repositorio_no_importan_nada(self):
        base = Path(__file__).resolve().parent.parent / "contenido"
        self.correr(base)
        self.assertEqual(Servicio.objects.count() + Producto.objects.count(), 0)
