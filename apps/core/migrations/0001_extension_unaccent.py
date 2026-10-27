import logging

from django.db import migrations, transaction

log = logging.getLogger("electorry")


def crear_unaccent(apps, schema_editor):
    """Búsqueda sin distinguir tildes en PostgreSQL. No hace nada en otros motores.

    Si el usuario de la base no puede crear la extensión, la migración NO falla: la búsqueda
    seguirá funcionando, solo que distinguiendo tildes (ver apps/core/busqueda.py).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    try:
        with transaction.atomic(using=schema_editor.connection.alias):
            with schema_editor.connection.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo crear la extensión unaccent (%s). La búsqueda distinguirá tildes.", exc)


class Migration(migrations.Migration):
    dependencies = []
    operations = [migrations.RunPython(crear_unaccent, migrations.RunPython.noop)]
