from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.auditoria import services as auditoria

from .models import IntentoLogin, Rol, Usuario

# ---------------------------------------------------------------- bloqueo por intentos


def _ventana():
    return timezone.now() - timedelta(minutes=settings.LOGIN_VENTANA_MINUTOS)


def esta_bloqueado(email, ip):
    email = (email or "").lower()
    fallos = IntentoLogin.objects.filter(exitoso=False, fecha__gte=_ventana())
    if fallos.filter(email=email).count() >= settings.LOGIN_MAX_INTENTOS:
        return True
    if ip and fallos.filter(ip=ip).count() >= settings.LOGIN_MAX_INTENTOS_IP:
        return True
    return False


def registrar_intento(email, ip, exitoso):
    email = (email or "").lower()[:254]
    IntentoLogin.objects.create(email=email, ip=ip, exitoso=exitoso)
    if exitoso:
        IntentoLogin.objects.filter(email=email, exitoso=False).delete()
    # Limpieza oportunista de registros antiguos
    IntentoLogin.objects.filter(fecha__lt=timezone.now() - timedelta(days=2)).delete()


# ---------------------------------------------------------------- cuentas


@transaction.atomic
def registrar_cliente(*, email, password, first_name, last_name, rut="", telefono="", acepta_privacidad, request=None):
    usuario = Usuario.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        rut=rut,
        telefono=telefono,
        acepta_privacidad=acepta_privacidad,
        rol=Rol.CLIENTE,
    )
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CREAR, entidad="usuario", entidad_id=usuario.pk,
        descripcion="Registro de cliente", request=request,
    )
    return usuario


@transaction.atomic
def anonimizar_usuario(usuario, *, por=None, request=None):
    """Elimina los datos personales de un cliente (RNF-SEG-07).

    Se conserva el historial de negocio (solicitudes, cotizaciones, ventas) para
    no romper la trazabilidad ni la integridad referencial, pero sin datos
    personales identificables.
    """
    from apps.solicitudes.services import anonimizar_datos_cliente

    anonimizar_datos_cliente(usuario)
    usuario.email = f"eliminado-{usuario.pk}@anonimo.invalid"
    usuario.first_name = "Cliente"
    usuario.last_name = "eliminado"
    usuario.telefono = ""
    usuario.is_active = False
    usuario.anonimizado = True
    usuario.acepta_privacidad = False
    usuario.set_unusable_password()
    usuario.save()
    auditoria.registrar(
        usuario=por or usuario, accion=auditoria.Accion.PRIVACIDAD, entidad="usuario", entidad_id=usuario.pk,
        descripcion="Eliminación de datos personales (anonimización)", request=request,
    )
    return usuario
