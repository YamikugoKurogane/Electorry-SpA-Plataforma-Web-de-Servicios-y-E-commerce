"""Carga servicios y productos reales desde planillas CSV (tarea S2-R3).

Uso:
    python manage.py importar_contenido contenido --simular   # valida y muestra qué haría, sin guardar
    python manage.py importar_contenido contenido             # guarda

Reglas:
- Todo o nada: si una fila tiene errores NO se guarda nada y se listan todos los errores con su línea.
- Es repetible: se identifica cada fila por su nombre (sin distinguir mayúsculas); si existe se actualiza.
- Acepta CSV de Excel (coma o punto y coma; UTF-8 o ANSI) y las categorías se crean solas.
"""
import csv
import io
import unicodedata
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.auditoria import services as auditoria
from apps.catalogo.models import CategoriaServicio, Servicio
from apps.tienda.models import CategoriaProducto, Producto

SI = {"si", "s", "1", "true", "verdadero", "x", "yes", "y"}
NO = {"no", "n", "0", "false", "falso"}
MAX_IMAGEN = 2 * 1024 * 1024


def _norm(texto):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return t.strip().lower()


class FilaInvalida(Exception):
    pass


def leer_csv(ruta):
    crudo = Path(ruta).read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            texto = crudo.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    primera = texto.splitlines()[0] if texto.strip() else ""
    delim = max((";", ",", "\t"), key=primera.count)
    lector = csv.reader(io.StringIO(texto), delimiter=delim)
    filas = list(lector)
    if not filas:
        return [], []
    cabecera = [_norm(c) for c in filas[0]]
    datos = []
    for numero, fila in enumerate(filas[1:], start=2):
        if not any(c.strip() for c in fila):
            continue
        if fila[0].strip().startswith("#"):  # fila de ejemplo / comentario
            continue
        datos.append((numero, {cabecera[i]: (fila[i].strip() if i < len(fila) else "") for i in range(len(cabecera))}))
    return cabecera, datos


def a_booleano(valor, por_defecto=True):
    v = _norm(valor)
    if v == "":
        return por_defecto
    if v in SI:
        return True
    if v in NO:
        return False
    raise FilaInvalida(f"«{valor}» no es válido; usa Sí o No")


def a_precio(valor):
    limpio = str(valor).replace("$", "").replace(" ", "").replace(".", "")
    if not limpio:
        raise FilaInvalida("falta el precio")
    if "," in limpio:
        raise FilaInvalida(f"precio «{valor}»: usa solo pesos enteros, sin decimales")
    if not limpio.isdigit() or int(limpio) <= 0:
        raise FilaInvalida(f"precio «{valor}» no es un monto válido en pesos")
    return int(limpio)


class Command(BaseCommand):
    help = "Importa servicios y productos desde servicios.csv y productos.csv."

    def add_arguments(self, parser):
        parser.add_argument("carpeta", help="Carpeta con servicios.csv y/o productos.csv (y opcionalmente imagenes/)")
        parser.add_argument("--simular", action="store_true", help="Valida y muestra el resultado sin guardar nada")

    def handle(self, *args, **opts):
        carpeta = Path(opts["carpeta"])
        if not carpeta.is_dir():
            raise CommandError(f"No existe la carpeta «{carpeta}».")
        f_serv, f_prod = carpeta / "servicios.csv", carpeta / "productos.csv"
        if not f_serv.exists() and not f_prod.exists():
            raise CommandError("Falta servicios.csv y/o productos.csv en la carpeta.")
        self.simular = opts["simular"]
        self.carpeta = carpeta
        self.errores, self.res = [], {}

        with transaction.atomic():
            if f_serv.exists():
                self._procesar("servicios", f_serv, ("categoria", "nombre", "resumen", "descripcion"), self._servicio)
            if f_prod.exists():
                self._procesar("productos", f_prod, ("categoria", "nombre", "precio"), self._producto)
            if self.errores or self.simular:
                transaction.set_rollback(True)

        for tipo, r in self.res.items():
            self.stdout.write(f"{tipo.capitalize():10} creados: {r['creado']:3}  actualizados: {r['actualizado']:3}  sin cambios: {r['igual']:3}  categorías nuevas: {r['cat']}")
        if self.errores:
            self.stdout.write(self.style.ERROR(f"\n{len(self.errores)} error(es). NO se guardó nada:"))
            for e in self.errores:
                self.stdout.write(self.style.ERROR(f"  • {e}"))
            raise CommandError("Corrige las filas indicadas y vuelve a ejecutar.")
        if self.simular:
            self.stdout.write(self.style.WARNING("\nSimulación: no se guardó nada. Quita --simular para guardar."))
        else:
            self.stdout.write(self.style.SUCCESS("\nContenido importado correctamente."))

    # ------------------------------------------------------------------
    def _procesar(self, tipo, ruta, obligatorias, aplicar):
        self.res[tipo] = {"creado": 0, "actualizado": 0, "igual": 0, "cat": 0}
        cabecera, filas = leer_csv(ruta)
        faltan = [c for c in obligatorias if c not in cabecera]
        if faltan:
            self.errores.append(f"{ruta.name}: faltan las columnas {', '.join(faltan)} (columnas encontradas: {', '.join(cabecera) or 'ninguna'})")
            return
        for numero, fila in filas:
            try:
                with transaction.atomic():
                    aplicar(tipo, fila)
            except (FilaInvalida, ValidationError) as exc:
                detalle = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                self.errores.append(f"{ruta.name}, línea {numero} («{fila.get('nombre', '')}»): {detalle}")

    def _categoria(self, tipo, modelo, nombre):
        if not nombre:
            raise FilaInvalida("falta la categoría")
        cat = modelo.objects.filter(nombre__iexact=nombre).first()
        if cat is None:
            cat = modelo(nombre=nombre)
            cat.full_clean()
            cat.save()
            self.res[tipo]["cat"] += 1
        return cat

    def _guardar(self, tipo, objeto, entidad, valores, nombre):
        nuevo = objeto.pk is None
        cambios = {k: v for k, v in valores.items() if nuevo or getattr(objeto, k) != v}
        for k, v in valores.items():
            setattr(objeto, k, v)
        objeto.full_clean(exclude=["slug", "imagen"])
        if nuevo or cambios:
            objeto.save()
            auditoria.registrar(
                accion=auditoria.Accion.CREAR if nuevo else auditoria.Accion.EDITAR, entidad=entidad,
                entidad_id=objeto.pk, descripcion=f"Importación de contenido: {nombre}"[:200],
                despues={k: str(v) for k, v in cambios.items()})
            self.res[tipo]["creado" if nuevo else "actualizado"] += 1
        else:
            self.res[tipo]["igual"] += 1

    def _servicio(self, tipo, f):
        if not f["nombre"]:
            raise FilaInvalida("falta el nombre")
        if not f["resumen"] or not f["descripcion"]:
            raise FilaInvalida("faltan el resumen o la descripción")
        cat = self._categoria(tipo, CategoriaServicio, f["categoria"])
        obj = Servicio.objects.filter(nombre__iexact=f["nombre"]).first() or Servicio()
        self._guardar(tipo, obj, "servicio", {
            "categoria": cat, "nombre": f["nombre"], "resumen": f["resumen"], "descripcion": f["descripcion"],
            "disponible": a_booleano(f.get("disponible", ""))}, f["nombre"])

    def _producto(self, tipo, f):
        if not f["nombre"]:
            raise FilaInvalida("falta el nombre")
        cat = self._categoria(tipo, CategoriaProducto, f["categoria"])
        obj = Producto.objects.filter(nombre__iexact=f["nombre"]).first() or Producto()
        self._guardar(tipo, obj, "producto", {
            "categoria": cat, "nombre": f["nombre"], "descripcion": f.get("descripcion", ""),
            "precio": a_precio(f["precio"]), "activo": a_booleano(f.get("activo", ""))}, f["nombre"])
        self._imagen(obj, f.get("imagen", ""))

    def _imagen(self, producto, nombre_archivo):
        if not nombre_archivo:
            return
        ruta = self.carpeta / "imagenes" / nombre_archivo
        if not ruta.is_file():
            raise FilaInvalida(f"no se encontró la imagen «imagenes/{nombre_archivo}»")
        if ruta.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            raise FilaInvalida(f"la imagen «{nombre_archivo}» debe ser JPG o PNG")
        if ruta.stat().st_size > MAX_IMAGEN:
            raise FilaInvalida(f"la imagen «{nombre_archivo}» supera 2 MB")
        if producto.imagen or self.simular:  # no duplicar archivos en cada ejecución; en simulación no se escribe nada
            return
        with ruta.open("rb") as fh:
            producto.imagen.save(ruta.name, File(fh), save=True)
