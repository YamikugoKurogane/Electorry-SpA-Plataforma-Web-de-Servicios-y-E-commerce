"""Verifica que la base de datos está bien integrada (tarea S2-R1, RNF-17).

Uso:  python manage.py verificar_bd [--exigir-postgres]

Comprueba el motor, las migraciones y que la base RECHAZA datos inválidos.
Todo se ejecuta dentro de una transacción que se revierte: no deja datos.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import ProtectedError

OK, FALLA, AVISO = "OK   ", "FALLA", "AVISO"


class _Revertir(Exception):
    pass


class Command(BaseCommand):
    help = "Comprueba motor, migraciones y restricciones de integridad de la base de datos."

    def add_arguments(self, parser):
        parser.add_argument("--exigir-postgres", action="store_true", help="Falla si el motor no es PostgreSQL.")

    def handle(self, *args, **opts):
        self.fallas = 0
        vendor = connection.vendor
        self._linea(OK if vendor == "postgresql" else (FALLA if opts["exigir_postgres"] else AVISO),
                    f"Motor: {vendor}" + ("" if vendor == "postgresql" else " (el proyecto se despliega con PostgreSQL)"))
        if vendor != "postgresql" and opts["exigir_postgres"]:
            self.fallas += 1
        if vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SHOW server_version")
                self._linea(OK, f"Versión de PostgreSQL: {cur.fetchone()[0]}")
                cur.execute("SHOW server_encoding")
                enc = cur.fetchone()[0]
            self._linea(OK if enc.upper() == "UTF8" else FALLA, f"Codificación: {enc}")
            if enc.upper() != "UTF8":
                self.fallas += 1

        plan = MigrationExecutor(connection).migration_plan(
            MigrationExecutor(connection).loader.graph.leaf_nodes())
        self._linea(OK if not plan else FALLA, "Migraciones al día" if not plan else f"Migraciones pendientes: {len(plan)} (ejecuta migrate)")
        if plan:
            self.fallas += 1

        try:
            with transaction.atomic():
                self._integridad(vendor)
                raise _Revertir  # no deja nada en la base
        except _Revertir:
            pass

        if self.fallas:
            raise CommandError(f"{self.fallas} verificación(es) fallaron.")
        self.stdout.write(self.style.SUCCESS("\nBase de datos verificada correctamente."))

    # ------------------------------------------------------------------
    def _linea(self, estado, texto):
        estilo = {OK: self.style.SUCCESS, FALLA: self.style.ERROR, AVISO: self.style.WARNING}[estado]
        self.stdout.write(f"[{estilo(estado)}] {texto}")

    def _debe_fallar(self, descripcion, funcion, excepciones=(IntegrityError, ProtectedError)):
        """La base debe rechazar la operación. Cada intento usa su propio savepoint."""
        try:
            with transaction.atomic():
                funcion()
        except excepciones as exc:
            self._linea(OK, f"Rechaza: {descripcion}  ({type(exc).__name__})")
        else:
            self._linea(FALLA, f"ACEPTÓ un dato inválido: {descripcion}")
            self.fallas += 1

    def _integridad(self, vendor):
        from apps.catalogo.models import CategoriaServicio, Servicio
        from apps.cotizaciones.models import Cotizacion, LineaCotizacion
        from apps.pagos.models import Pago
        from apps.solicitudes.models import SolicitudCotizacion
        from apps.tienda.models import CategoriaProducto, DetalleVenta, Producto, Venta
        from apps.usuarios.models import Usuario

        u1 = Usuario.objects.create_user("verificar1@verificar.test", "Clave-Temporal-12345")
        Usuario.objects.create_user("verificar2@verificar.test", "Clave-Temporal-12345")
        cat = CategoriaServicio.objects.create(nombre="__verificar__")
        servicio = Servicio.objects.create(categoria=cat, nombre="__verificar__", resumen="r", descripcion="d")
        sol = SolicitudCotizacion.objects.create(
            cliente=u1, servicio=servicio, descripcion="x" * 20, direccion="d",
            nombre_contacto="n", telefono_contacto="+56911111111", email_contacto="a@b.cl")
        cp = CategoriaProducto.objects.create(nombre="__verificar__")
        prod = Producto.objects.create(categoria=cp, nombre="__verificar__", precio=1000)
        venta = Venta.objects.create(cliente=u1, total=1000)
        cot = Cotizacion.objects.create(solicitud=sol)

        self._debe_fallar("dos usuarios con el mismo correo",
                          lambda: Usuario.objects.create_user("verificar1@verificar.test", "Clave-Temporal-12345"))
        self._debe_fallar("detalle de venta con cantidad 0",
                          lambda: DetalleVenta.objects.create(venta=venta, producto=prod, nombre_producto="x", cantidad=0, precio_unitario=1))
        self._debe_fallar("línea de cotización con cantidad 0",
                          lambda: LineaCotizacion.objects.create(cotizacion=cot, descripcion="x", cantidad=0, precio_unitario=1))
        self._debe_fallar("dos pagos con el mismo token y proveedor",
                          lambda: [Pago.objects.create(venta=venta, proveedor="x", token="t", monto=1) for _ in range(2)])
        self._debe_fallar("borrar un servicio que tiene solicitudes", servicio.delete)
        self._debe_fallar("borrar un producto con ventas", lambda: (
            DetalleVenta.objects.create(venta=venta, producto=prod, nombre_producto="x", cantidad=1, precio_unitario=1), prod.delete()))
        self._debe_fallar("categoría de servicio con nombre repetido", lambda: CategoriaServicio.objects.create(nombre="__verificar__"))

        if vendor == "postgresql":
            # Las claves foráneas se validan al final de la transacción; se fuerza la validación inmediata.
            def borrado_directo():
                with connection.cursor() as cur:
                    cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    cur.execute("DELETE FROM catalogo_servicio WHERE id = %s", [servicio.pk])
            self._debe_fallar("borrado SQL directo de un servicio con solicitudes (clave foránea)", borrado_directo)

            def bloqueo():
                Venta.objects.select_for_update().get(pk=venta.pk)
            try:
                with transaction.atomic():
                    bloqueo()
                self._linea(OK, "Bloqueo de filas (SELECT ... FOR UPDATE) disponible: pagos e historial seguros")
            except Exception as exc:  # noqa: BLE001
                self._linea(FALLA, f"SELECT FOR UPDATE falló: {exc}")
                self.fallas += 1
