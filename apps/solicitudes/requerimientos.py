"""Información adicional dentro de la solicitud (RF-25, S4-R2).

El personal (administrador o usuario interno) pregunta; el cliente dueño de la solicitud responde con texto y/o
archivos. Cada paso queda auditado y se avisa por correo. Las reglas viven aquí; las vistas solo orquestan.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.auditoria import services as auditoria
from apps.notificaciones import services as notif
from apps.usuarios.models import Rol

from . import services
from .models import Adjunto, Estado, RequerimientoInfo, SolicitudCotizacion

log = logging.getLogger("electorry.solicitudes")

MAX_PREGUNTA = 1000
MAX_RESPUESTA = 2000
MAX_PENDIENTES = 5  # evita llenar de preguntas al cliente
ESTADOS_CERRADOS = (Estado.CANCELADA, Estado.FINALIZADA)


class RequerimientoError(Exception):
    pass


def _nombre(usuario):
    return (usuario.nombre_completo or usuario.email) if usuario else "Sistema"


def _bloquear_solicitud(solicitud):
    return SolicitudCotizacion.objects.select_for_update().get(pk=solicitud.pk)


@transaction.atomic
def pedir_informacion(solicitud, usuario, pregunta, request=None):
    """El personal pide un dato al cliente. Si la solicitud estaba «Pendiente», pasa a «En revisión»."""
    if usuario is None or usuario.rol not in (Rol.ADMIN, Rol.INTERNO):
        raise RequerimientoError("Solo el personal puede pedir información al cliente.")
    pregunta = (pregunta or "").strip()
    if not pregunta:
        raise RequerimientoError("Escribe qué información necesitas.")
    if len(pregunta) > MAX_PREGUNTA:
        raise RequerimientoError(f"La pregunta no puede superar los {MAX_PREGUNTA} caracteres.")
    solicitud = _bloquear_solicitud(solicitud)
    if solicitud.estado in ESTADOS_CERRADOS:
        raise RequerimientoError(f"No se puede pedir información en una solicitud {Estado(solicitud.estado).label.lower()}.")
    if solicitud.requerimientos.filter(respondido_en__isnull=True, cancelado_en__isnull=True).count() >= MAX_PENDIENTES:
        raise RequerimientoError(f"Ya hay {MAX_PENDIENTES} preguntas sin responder. Espera la respuesta del cliente o cancela alguna.")

    req = RequerimientoInfo.objects.create(
        solicitud=solicitud, pregunta=pregunta, creado_por=usuario, creado_por_nombre=_nombre(usuario)
    )
    if solicitud.estado == Estado.PENDIENTE:
        services.cambiar_estado(solicitud, Estado.EN_REVISION, usuario, "Se solicitó información adicional al cliente", request)
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CREAR, entidad="requerimiento_info", entidad_id=req.pk,
        descripcion=f"{solicitud.codigo}: se pidió información adicional", despues={"solicitud": solicitud.pk, "pregunta": pregunta[:200]},
        request=request,
    )
    notif.notificar(
        solicitud.email_contacto,
        f"Necesitamos más información para tu solicitud {solicitud.codigo}",
        f"Hola {solicitud.nombre_contacto},\n\nPara avanzar con tu solicitud {solicitud.codigo} necesitamos que nos indiques:\n\n"
        f"«{pregunta}»\n\nIngresa a tu cuenta, abre la solicitud y responde ahí mismo (puedes adjuntar fotos o documentos).\n\nElectorry SpA",
        evento="info_solicitada",
    )
    return req


@transaction.atomic
def responder_requerimiento(requerimiento_id, cliente, respuesta="", archivos=(), request=None):
    """El cliente dueño responde con texto y/o archivos. Se responde una sola vez; si hace falta más, se pregunta de nuevo."""
    req = RequerimientoInfo.objects.select_for_update(of=("self",)).select_related("solicitud", "creado_por").get(pk=requerimiento_id)
    solicitud = req.solicitud
    if cliente.rol != Rol.CLIENTE or solicitud.cliente_id != cliente.pk:
        raise RequerimientoError("No puedes responder esta solicitud.")
    if req.estado == "RESPONDIDO":
        raise RequerimientoError("Esta pregunta ya fue respondida.")
    if req.estado == "CANCELADO":
        raise RequerimientoError("Esta pregunta ya no es necesaria: fue cancelada.")
    if solicitud.estado in ESTADOS_CERRADOS:
        raise RequerimientoError("La solicitud ya está cerrada.")
    respuesta = (respuesta or "").strip()
    archivos = list(archivos or [])
    if not respuesta and not archivos:
        raise RequerimientoError("Escribe tu respuesta o adjunta al menos un archivo.")
    if len(respuesta) > MAX_RESPUESTA:
        raise RequerimientoError(f"La respuesta no puede superar los {MAX_RESPUESTA} caracteres.")
    if len(archivos) > settings.ADJUNTOS_MAX_CANTIDAD:
        raise RequerimientoError(f"Puedes adjuntar hasta {settings.ADJUNTOS_MAX_CANTIDAD} archivos por respuesta.")

    req.respuesta = respuesta
    req.respondido_por = cliente
    req.respondido_en = timezone.now()
    req.save(update_fields=["respuesta", "respondido_por", "respondido_en"])
    for archivo in archivos:
        Adjunto.objects.create(
            solicitud=solicitud, requerimiento=req, archivo=archivo, nombre_original=archivo.name[:150], tamano=archivo.size
        )
    SolicitudCotizacion.objects.filter(pk=solicitud.pk).update(actualizada=timezone.now())
    auditoria.registrar(
        usuario=cliente, accion=auditoria.Accion.EDITAR, entidad="requerimiento_info", entidad_id=req.pk,
        descripcion=f"{solicitud.codigo}: el cliente respondió la información adicional ({len(archivos)} archivo(s))",
        despues={"respuesta": respuesta[:200], "archivos": len(archivos)}, request=request,
    )
    texto = (
        f"El cliente {solicitud.nombre_contacto} respondió la información adicional de {solicitud.codigo}.\n\n"
        f"Pregunta: «{req.pregunta}»\nRespuesta: «{respuesta or '(solo archivos adjuntos)'}»\nArchivos: {len(archivos)}"
    )
    quien = req.creado_por
    if quien and quien.is_active and quien.email:
        notif.notificar(quien.email, f"Respuesta del cliente en {solicitud.codigo}", texto, evento="info_respondida")
    if not quien or quien.email != settings.CORREO_AVISOS_INTERNOS:
        notif.notificar_interno(f"Respuesta del cliente en {solicitud.codigo}", texto, evento="info_respondida")
    return req


@transaction.atomic
def cancelar_requerimiento(requerimiento_id, usuario, request=None):
    """El personal retira una pregunta pendiente que ya no necesita."""
    if usuario is None or usuario.rol not in (Rol.ADMIN, Rol.INTERNO):
        raise RequerimientoError("Solo el personal puede cancelar una pregunta.")
    req = RequerimientoInfo.objects.select_for_update(of=("self",)).select_related("solicitud").get(pk=requerimiento_id)
    if req.estado != "PENDIENTE":
        raise RequerimientoError("Solo se pueden cancelar preguntas que siguen pendientes.")
    req.cancelado_en = timezone.now()
    req.cancelado_por = usuario
    req.save(update_fields=["cancelado_en", "cancelado_por"])
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.EDITAR, entidad="requerimiento_info", entidad_id=req.pk,
        descripcion=f"{req.solicitud.codigo}: se canceló una pregunta pendiente", request=request,
    )
    return req
