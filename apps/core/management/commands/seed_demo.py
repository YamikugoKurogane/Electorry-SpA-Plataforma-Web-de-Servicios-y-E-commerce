import os
import secrets

from django.core.management.base import BaseCommand

from apps.catalogo.models import CategoriaServicio, Servicio
from apps.tienda.models import CategoriaProducto, Producto
from apps.usuarios.models import Rol, Usuario

SERVICIOS = {
    "Instalaciones eléctricas": [
        ("Instalación eléctrica residencial", "Instalación completa o ampliación de circuitos para viviendas.", "Diseñamos e instalamos circuitos, tableros y puntos de luz y fuerza cumpliendo la normativa vigente."),
        ("Instalación eléctrica comercial e industrial", "Soluciones para locales, oficinas y plantas.", "Canalizaciones, tableros de distribución, iluminación y puesta a tierra para uso comercial e industrial."),
    ],
    "Mantención y certificación": [
        ("Mantención preventiva y correctiva", "Revisión y reparación de instalaciones existentes.", "Detectamos fallas, termografía básica y reemplazo de componentes dañados."),
        ("Regularización y certificación (TE1)", "Apoyo en trámites ante la SEC.", "Levantamiento, correcciones y gestión de la declaración de instalación eléctrica."),
    ],
    "Energía y eficiencia": [
        ("Sistemas fotovoltaicos", "Paneles solares para autoconsumo.", "Dimensionamiento, instalación y puesta en marcha de sistemas fotovoltaicos."),
        ("Iluminación LED", "Cambio a iluminación eficiente.", "Proyectos de iluminación LED para hogares, locales y exteriores."),
    ],
}
PRODUCTOS = {
    "Protecciones": [("Disyuntor termomagnético 20A", 6990), ("Protector diferencial 25A 30mA", 24990)],
    "Cables y conductores": [("Cable libre de halógenos 2,5 mm² (rollo 100 m)", 54990), ("Alargador industrial 10 m", 12990)],
    "Iluminación": [("Ampolleta LED 12W luz cálida", 2990), ("Foco LED exterior 30W", 14990)],
    "Accesorios": [("Interruptor simple blanco", 1990), ("Enchufe doble con tierra", 3490)],
}


class Command(BaseCommand):
    help = "Carga datos de demostración (NO usar en producción con datos reales)."

    def handle(self, *args, **options):
        for i, (cat, items) in enumerate(SERVICIOS.items()):
            c, _ = CategoriaServicio.objects.get_or_create(nombre=cat, defaults={"orden": i})
            for nombre, resumen, desc in items:
                Servicio.objects.get_or_create(nombre=nombre, defaults={"categoria": c, "resumen": resumen, "descripcion": desc})
        for cat, items in PRODUCTOS.items():
            c, _ = CategoriaProducto.objects.get_or_create(nombre=cat)
            for nombre, precio in items:
                Producto.objects.get_or_create(nombre=nombre, defaults={"categoria": c, "precio": precio, "descripcion": nombre})
        pw_admin = os.environ.get("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        if not Usuario.objects.filter(email="admin@electorry.cl").exists():
            Usuario.objects.create_superuser("admin@electorry.cl", pw_admin, first_name="Admin", last_name="Electorry")
            self.stdout.write(self.style.WARNING(f"Admin creado: admin@electorry.cl / {pw_admin}"))
        if not Usuario.objects.filter(email="cliente@demo.cl").exists():
            pw = os.environ.get("SEED_CLIENTE_PASSWORD") or secrets.token_urlsafe(12)
            Usuario.objects.create_user("cliente@demo.cl", pw, first_name="Cliente", last_name="Demo", telefono="+56912345678", acepta_privacidad=True)
            self.stdout.write(self.style.WARNING(f"Cliente demo creado: cliente@demo.cl / {pw}"))
        if not Usuario.objects.filter(email="interno@electorry.cl").exists():
            pw = os.environ.get("SEED_INTERNO_PASSWORD") or secrets.token_urlsafe(12)
            Usuario.objects.create_user("interno@electorry.cl", pw, first_name="Usuario", last_name="Interno", rol=Rol.INTERNO)
            self.stdout.write(self.style.WARNING(f"Interno creado: interno@electorry.cl / {pw}"))
        self.stdout.write(self.style.SUCCESS("Datos de demostración listos."))
