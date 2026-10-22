"""Lógica de negocio de solicitudes (RNF-MAN-01).

Las vistas solo orquestan; las reglas viven aquí: transiciones de estado,
historial, auditoría y notificaciones dentro de una única transacción.
"""
import logging

from django.db import transaction
from django.http import Http404

from apps.auditoria import services as auditoria
from apps.notificaciones import services as notif
from apps.usuarios.models import Rol

from .models import Adjunto, Estado, HistorialEstado, SolicitudCotizacion

log = logging.getLogger("electorry.solicitudes")

# Máquina de estados. Agregar un estado = editar este diccionario y `Estado` (EC-09).
TRANSICIONES = {
    Estado.PENDIENTE: {Estado.EN_REVISION, Estado.CANCELADA},
    Estado.EN_REVISION: {Estado.COTIZADA, Estado.CANCELADA},
    Estado.COTIZADA: {Estado.EN_REVISION, Estado.ACEPTADA, Estado.CANCELADA},
    Estado.ACEPTADA: {Estado.EN_EJECUCION, Estado.CANCELADA},
    Estado.EN_EJECUCION: {Estado.FINALIZADA, Estado.CANCELADA},
    Estado.FINALIZADA: set(),
    Estado.CANCELADA: set(),
}


class TransicionInvalida(Exception):
    pass


def transiciones_permitidas(estado):
    orden = [e for e, _ in Estado.choices]
    return sorted(TRANSICIONES.get(estado, set()), key=orden.index)


# ------------------------------------------------------------------ autorización por objeto (S1)


def solicitudes_visibles_para(usuario):
    """Único punto de filtrado por propietario (S1, EC-01)."""
    qs = SolicitudCotizacion.objects.select_related("servicio", "cliente")
    if usuario.rol in (Rol.ADMIN, Rol.INTERNO):
        return qs
    return qs.filter(cliente=usuario)


def obtener_solicitud_para(usuario, pk, request=None):
    """Devuelve la solicitud o 404 (sin revelar si existe) y registra el intento ajeno."""
    qs = solicitudes_visibles_para(usuario)
    try:
        return qs.get(pk=pk)
    except SolicitudCotizacion.DoesNotExist:
        if SolicitudCotizacion.objects.filter(pk=pk).exists():
            from apps.core.permisos import registrar_acceso_denegado

            if request is not None:
                registrar_acceso_denegado(request, f"solicitud ajena #{pk}")
        raise Http404("Solicitud no encontrada.")


# ------------------------------------------------------------------ casos de uso


@transaction.atomic
def crear_solicitud(*, cliente, servicio, datos, archivos=(), request=None):
    solicitud = SolicitudCotizacion.objects.create(
        cliente=cliente,
        servicio=servicio,
        descripcion=datos["descripcion"],
        direccion=datos["direccion"],
        comuna=datos.get("comuna", ""),
        nombre_contacto=datos["nombre_contacto"],
        telefono_contacto=datos["telefono_contacto"],
        email_contacto=datos["email_contacto"],
        estado=Estado.PENDIENTE,
    )
    for archivo in archivos:
        Adjunto.objects.create(
            solicitud=solicitud, archivo=archivo, nombre_original=archivo.name[:150], tamano=archivo.size
        )
    HistorialEstado.objects.create(
        solicitud=solicitud, estado_anterior="", estado_nuevo=Estado.PENDIENTE,
        usuario=cliente, usuario_nombre=cliente.nombre_completo or cliente.email, comentario="Solicitud creada",
    )
    auditoria.registrar(
        usuario=cliente, accion=auditoria.Accion.CREAR, entidad="solicitud", entidad_id=solicitud.pk,
        descripcion=f"Solicitud {solicitud.codigo} para «{servicio.nombre}»", despues={"estado": Estado.PENDIENTE}, request=request,
    )
    notif.notificar(
        solicitud.email_contacto,
        f"Recibimos tu solicitud {solicitud.codigo}",
        f"Hola {solicitud.nombre_contacto},\n\nRecibimos tu solicitud de cotización {solicitud.codigo} "
        f"para «{servicio.nombre}». Te contactaremos a la brevedad. Puedes revisar su estado en tu cuenta.\n\nElectorry SpA",
        evento="solicitud_recibida",
    )
    notif.notificar_interno(
        f"Nueva solicitud {solicitud.codigo}",
        f"{solicitud.nombre_contacto} solicitó cotización de «{servicio.nombre}».\n{solicitud.descripcion[:500]}",
        evento="solicitud_nueva",
    )
    return solicitud


@transaction.atomic
def cambiar_estado(solicitud, nuevo_estado, usuario, comentario="", request=None):
    """Cambia el estado validando la transición y registrando historial + auditoría (EC-08)."""
    solicitud = SolicitudCotizacion.objects.select_for_update().get(pk=solicitud.pk)
    anterior = solicitud.estado
    if nuevo_estado not in dict(Estado.choices):
        raise TransicionInvalida(f"Estado desconocido: {nuevo_estado}")
    if nuevo_estado == anterior:
        raise TransicionInvalida("La solicitud ya está en ese estado.")
    if nuevo_estado not in TRANSICIONES.get(anterior, set()):
        raise TransicionInvalida(
            f"No se puede pasar de «{Estado(anterior).label}» a «{Estado(nuevo_estado).label}»."
        )
    solicitud.estado = nuevo_estado
    solicitud.save(update_fields=["estado", "actualizada"])
    HistorialEstado.objects.create(
        solicitud=solicitud, estado_anterior=anterior, estado_nuevo=nuevo_estado, usuario=usuario,
        usuario_nombre=(usuario.nombre_completo or usuario.email) if usuario else "Sistema", comentario=comentario[:300],
    )
    auditoria.registrar(
        usuario=usuario, accion=auditoria.Accion.CAMBIO_ESTADO, entidad="solicitud", entidad_id=solicitud.pk,
        descripcion=f"{solicitud.codigo}: {anterior} → {nuevo_estado}", antes={"estado": anterior},
        despues={"estado": nuevo_estado, "comentario": comentario}, request=request,
    )
    notif.notificar(
        solicitud.email_contacto,
        f"Tu solicitud {solicitud.codigo} cambió de estado",
        f"Hola {solicitud.nombre_contacto},\n\nTu solicitud {solicitud.codigo} ahora está «{Estado(nuevo_estado).label}»."
        + (f"\n\nComentario: {comentario}" if comentario else "")
        + "\n\nPuedes ver el detalle en tu cuenta.\n\nElectorry SpA",
        evento="cambio_estado",
    )
    return solicitud


@transaction.atomic
def anonimizar_datos_cliente(cliente):
    """Elimina datos personales de las solicitudes de un cliente (RNF-SEG-07)."""
    for sol in SolicitudCotizacion.objects.filter(cliente=cliente):
        for adj in sol.adjuntos.all():
            adj.archivo.delete(save=False)
            adj.delete()
        sol.nombre_contacto = "Cliente eliminado"
        sol.telefono_contacto = ""
        sol.email_contacto = f"eliminado-{cliente.pk}@anonimo.invalid"
        sol.direccion = "—"
        sol.comuna = ""
        sol.save()
    HistorialEstado.objects.filter(usuario=cliente).update(usuario_nombre="Cliente eliminado")
