"""Búsqueda de texto que ignora mayúsculas y tildes («instalacion» encuentra «Instalación»).

En PostgreSQL usa la extensión `unaccent` (creada por la migración core.0001). Si no está disponible,
o en SQLite (solo desarrollo), cae a una búsqueda normal por contenido.
"""
import unicodedata
from functools import lru_cache

from django.db import connection
from django.db.models import CharField, F, Func, Q


def sin_tildes(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


@lru_cache(maxsize=1)
def _hay_unaccent():
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'")
        return cur.fetchone() is not None


def filtrar_texto(qs, campos, texto):
    texto = (texto or "").strip()
    if not texto:
        return qs
    cond = Q()
    if _hay_unaccent():
        qs = qs.annotate(**{f"_u_{c}": Func(F(c), function="unaccent", output_field=CharField()) for c in campos})
        for c in campos:
            cond |= Q(**{f"_u_{c}__icontains": sin_tildes(texto)})
    else:
        for c in campos:
            cond |= Q(**{f"{c}__icontains": texto})
    return qs.filter(cond)
