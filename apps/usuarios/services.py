from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.auditoria import services as auditoria
from apps.auditoria.models import RegistroAuditoria
from apps.core.utils import ip_cliente
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import EVENTO_RECUPERACION, notificar

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


# ---------------------------------------------------------------- recuperación de contraseña

DESC_SOLICITUD_RECUPERACION = "Solicitud de recuperación de contraseña"


def solicitar_recuperacion(email, *, request):
    """Envía un enlace de restablecimiento al correo, si corresponde a una cuenta activa.

    Devuelve siempre sin revelar si el correo existe (la vista responde lo mismo en todos los casos).
    Límites por hora: por correo y por IP, para que el formulario no sirva para inundar una casilla.
    """
    email = (email or "").strip().lower()
    ip = ip_cliente(request)
    desde = timezone.now() - timedelta(hours=1)

    if ip and RegistroAuditoria.objects.filter(
        accion=auditoria.Accion.RECUPERAR_PASSWORD, descripcion=DESC_SOLICITUD_RECUPERACION, ip=ip, fecha__gte=desde
    ).count() >= settings.RECUPERACION_MAX_SOLICITUDES_IP:
        return False

    with transaction.atomic():
        usuario = Usuario.objects.filter(email__iexact=email, is_active=True, anonimizado=False).first()
        auditoria.registrar(
            accion=auditoria.Accion.RECUPERAR_PASSWORD, entidad="usuario", entidad_id=usuario.pk if usuario else None,
            descripcion=DESC_SOLICITUD_RECUPERACION, request=request,
        )
        if usuario is None:
            return False
        recientes = Notificacion.objects.filter(
            destinatario=usuario.email, evento=EVENTO_RECUPERACION, creada__gte=desde
        ).count()
        if recientes >= settings.RECUPERACION_MAX_SOLICITUDES:
            return False

        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        enlace = request.build_absolute_uri(
            reverse("usuarios:restablecer_confirmar", kwargs={"uidb64": uid, "token": token})
        )
        minutos = max(settings.PASSWORD_RESET_TIMEOUT // 60, 1)
        saludo = f"Hola {usuario.first_name}," if usuario.first_name else "Hola,"
        cuerpo = (
            f"{saludo}\n\n"
            "Recibimos una solicitud para restablecer la contraseña de tu cuenta en "
            f"{settings.EMPRESA['nombre']}.\n\n"
            f"Para elegir una contraseña nueva abre este enlace (vale {minutos} minutos y se puede usar una sola vez):\n"
            f"{enlace}\n\n"
            "Si tú no lo pediste, ignora este correo: tu contraseña actual sigue funcionando.\n"
        )
        notificar(usuario.email, f"Restablece tu contraseña · {settings.EMPRESA['nombre']}", cuerpo, EVENTO_RECUPERACION)
    return True


def usuario_desde_uid(uidb64):
    """Usuario activo al que apunta el identificador del enlace, o None."""
    try:
        pk = urlsafe_base64_decode(uidb64).decode()
        usuario = Usuario.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError, Usuario.DoesNotExist):
        return None
    if not usuario.is_active or usuario.anonimizado:
        return None
    return usuario


def token_recuperacion_valido(usuario, token):
    """El token vence con PASSWORD_RESET_TIMEOUT y deja de servir al cambiar la contraseña o iniciar sesión."""
    return bool(usuario and token and default_token_generator.check_token(usuario, token))


@transaction.atomic
def restablecer_password(usuario, nueva_password, *, request=None):
    """Fija la contraseña nueva, libera el bloqueo por intentos fallidos y avisa por correo."""
    usuario.set_password(nueva_password)
    usuario.save(update_fields=["password"])
    IntentoLogin.objects.filter(email=usuario.email, exitoso=False).delete()
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.RECUPERAR_PASSWORD, entidad="usuario", entidad_id=usuario.pk,
        descripcion="Contraseña restablecida mediante enlace enviado por correo", request=request,
    )
    notificar(
        usuario.email,
        f"Tu contraseña fue cambiada · {settings.EMPRESA['nombre']}",
        f"Hola,\n\nLa contraseña de tu cuenta en {settings.EMPRESA['nombre']} se cambió el "
        f"{timezone.localtime():%d-%m-%Y a las %H:%M}.\n\n"
        f"Si no fuiste tú, escríbenos de inmediato a {settings.EMPRESA['email']}.\n",
        "cambio_password",
    )
    return usuario

