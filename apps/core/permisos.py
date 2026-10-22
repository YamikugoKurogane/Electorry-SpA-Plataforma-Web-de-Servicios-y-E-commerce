"""Autorización por rol (RNF-SEG-02, EC-01).

Toda vista protegida usa `rol_requerido` o `RolRequeridoMixin`. Un acceso
denegado se registra en el log de seguridad y en la auditoría.
"""
import logging
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from apps.usuarios.models import Rol

from .utils import ip_cliente

seguridad = logging.getLogger("electorry.seguridad")

SOLO_ADMIN = (Rol.ADMIN,)
PERSONAL = (Rol.ADMIN, Rol.INTERNO)
SOLO_CLIENTE = (Rol.CLIENTE,)
TODOS_AUTENTICADOS = (Rol.ADMIN, Rol.INTERNO, Rol.CLIENTE)


def registrar_acceso_denegado(request, detalle=""):
    from apps.auditoria import services as auditoria

    usuario = request.user if request.user.is_authenticated else None
    seguridad.warning(
        "Acceso denegado: usuario=%s ip=%s %s %s %s",
        getattr(usuario, "email", "anónimo"),
        ip_cliente(request),
        request.method,
        request.path,
        detalle,
    )
    auditoria.registrar(
        usuario=usuario,
        accion=auditoria.Accion.ACCESO_DENEGADO,
        entidad="acceso",
        descripcion=f"{request.method} {request.path} {detalle}".strip(),
        request=request,
    )


def rol_requerido(*roles):
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.rol not in roles:
                registrar_acceso_denegado(request)
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


class RolRequeridoMixin(AccessMixin):
    roles = TODOS_AUTENTICADOS

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.rol not in self.roles:
            registrar_acceso_denegado(request)
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
