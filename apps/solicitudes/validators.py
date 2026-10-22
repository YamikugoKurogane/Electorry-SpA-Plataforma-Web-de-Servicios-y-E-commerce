"""Validación de archivos adjuntos (RNF-SEG-04, EC-10).

Lista blanca de tipos, tamaño máximo y verificación del contenido real
(firma del archivo), no solo de la extensión declarada.
"""
import os

from django.conf import settings
from django.core.exceptions import ValidationError

FIRMAS = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "pdf": (b"%PDF-",),
}


def extension_de(nombre):
    return os.path.splitext(nombre or "")[1].lower().lstrip(".")


def validar_adjunto(archivo):
    nombre = os.path.basename(archivo.name or "")
    ext = extension_de(nombre)
    permitidas = settings.ADJUNTO_EXTENSIONES
    if ext not in permitidas:
        raise ValidationError(
            f"«{nombre}»: tipo de archivo no permitido. Solo se aceptan {', '.join(e.upper() for e in permitidas if e != 'jpeg')}."
        )
    if archivo.size > settings.ADJUNTO_MAX_BYTES:
        mb = settings.ADJUNTO_MAX_BYTES // (1024 * 1024)
        raise ValidationError(f"«{nombre}» supera el tamaño máximo de {mb} MB.")
    if archivo.size == 0:
        raise ValidationError(f"«{nombre}» está vacío.")
    cabecera = archivo.read(16)
    archivo.seek(0)
    if not any(cabecera.startswith(f) for f in FIRMAS[ext]):
        raise ValidationError(f"«{nombre}» no es un archivo {ext.upper()} válido.")
    return archivo
