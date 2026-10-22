import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Notificacion

log = logging.getLogger("electorry.notificaciones")


def notificar(destinatario, asunto, cuerpo, evento=""):
    """Encola un correo y lo intenta enviar cuando la transacción actual se confirme.

    Nunca lanza excepciones hacia el flujo de negocio (RNF-DIS-02).
    """
    if not destinatario or destinatario.endswith(".invalid"):
        return None
    notificacion = Notificacion.objects.create(
        destinatario=destinatario, asunto=asunto[:200], cuerpo=cuerpo, evento=evento
    )
    transaction.on_commit(lambda: intentar_envio(notificacion.pk))
    return notificacion


def notificar_interno(asunto, cuerpo, evento=""):
    if settings.CORREO_AVISOS_INTERNOS:
        return notificar(settings.CORREO_AVISOS_INTERNOS, asunto, cuerpo, evento)
    return None


def intentar_envio(pk):
    """Intenta enviar una notificación. Devuelve True si se envió."""
    try:
        with transaction.atomic():
            n = Notificacion.objects.select_for_update().get(pk=pk)
            if n.estado == Notificacion.Estado.ENVIADA:
                return True
            n.intentos += 1
            try:
                send_mail(n.asunto, n.cuerpo, settings.DEFAULT_FROM_EMAIL, [n.destinatario], fail_silently=False)
            except Exception as exc:  # noqa: BLE001 — cualquier falla de correo se aísla
                n.ultimo_error = f"{type(exc).__name__}: {exc}"[:1000]
                if n.intentos >= settings.NOTIFICACION_MAX_INTENTOS:
                    n.estado = Notificacion.Estado.FALLIDA
                log.warning("Fallo de correo (notificación %s, intento %s): %s", pk, n.intentos, exc)
                n.save()
                return False
            n.estado = Notificacion.Estado.ENVIADA
            n.enviada_en = timezone.now()
            n.ultimo_error = ""
            n.save()
            return True
    except Exception:  # noqa: BLE001
        log.exception("Error inesperado enviando notificación %s", pk)
        return False


def reintentar_pendientes(limite=100):
    pendientes = Notificacion.objects.filter(estado=Notificacion.Estado.PENDIENTE).order_by("creada")[:limite]
    enviadas = 0
    for n in pendientes:
        if intentar_envio(n.pk):
            enviadas += 1
    return enviadas
