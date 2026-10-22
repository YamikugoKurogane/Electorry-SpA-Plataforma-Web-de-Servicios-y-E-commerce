from apps.core.utils import ip_cliente, json_seguro

from .models import RegistroAuditoria


class Accion:
    CREAR = "CREAR"
    EDITAR = "EDITAR"
    ELIMINAR = "ELIMINAR"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    ENVIAR = "ENVIAR"
    PAGO = "PAGO"
    LOGIN = "LOGIN"
    LOGIN_FALLIDO = "LOGIN_FALLIDO"
    ACCESO_DENEGADO = "ACCESO_DENEGADO"
    PRIVACIDAD = "PRIVACIDAD"


def registrar(*, usuario=None, accion, entidad, entidad_id=None, descripcion="", antes=None, despues=None, request=None):
    """Escribe un registro de auditoría.

    Se invoca desde la capa de servicios dentro de la misma transacción que
    el cambio auditado (NR4): si el cambio se revierte, el registro también.
    """
    if usuario is not None and not getattr(usuario, "is_authenticated", False):
        usuario = None
    return RegistroAuditoria.objects.create(
        usuario=usuario,
        usuario_email=getattr(usuario, "email", "") or "",
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        descripcion=descripcion[:300],
        antes=json_seguro(antes),
        despues=json_seguro(despues),
        ip=ip_cliente(request) if request is not None else None,
    )
