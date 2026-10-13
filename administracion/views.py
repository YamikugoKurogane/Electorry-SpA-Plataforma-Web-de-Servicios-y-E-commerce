import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError

from .services import (
    cambiar_estado_cotizacion,
    obtener_estado_cotizacion,
    obtener_estado_cotizacion_display,
)
from mainPage.models import SolicitudCotizacion
from .models import GestionEstadoCotizacion

# Función de validación de rol para RBAC (Staff / Administrador)
def es_administrador(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# --- VISTA PRINCIPAL DE ADMINISTRACIÓN (PROTEGIDA CON RBAC) ---
@login_required
@user_passes_test(es_administrador)
def homeAdmin(request):
    return render(request, "indexAdmin.html")


# --- VISTAS PARA GESTIÓN Y ESTADOS DE COTIZACIÓN (PROTEGIDAS CON RBAC) ---
@login_required
@user_passes_test(es_administrador)
@require_POST
def cambiar_estado_solicitud(request, solicitud_id):

    try:
        solicitud = SolicitudCotizacion.objects.get(
            id=solicitud_id
        )
    except SolicitudCotizacion.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'message': 'La solicitud de cotización no existe.'
            },
            status=404
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {
                'success': False,
                'message': 'El cuerpo de la solicitud no contiene JSON válido.'
            },
            status=400
        )

    nuevo_estado = data.get('estado')
    observacion = data.get('observacion')

    if not nuevo_estado:
        return JsonResponse(
            {
                'success': False,
                'message': 'Debe indicar el nuevo estado.'
            },
            status=400
        )

    try:
        gestion = cambiar_estado_cotizacion(
            solicitud=solicitud,
            nuevo_estado=nuevo_estado,
            observacion=observacion
        )
    except ValidationError as error:
        return JsonResponse(
            {
                'success': False,
                'message': str(error)
            },
            status=400
        )

    return JsonResponse(
        {
            'success': True,
            'message': 'Estado actualizado correctamente.',
            'solicitud_id': solicitud.id,
            'estado': gestion.estado,
            'estado_display': gestion.get_estado_display(),
            'fecha_cambio': gestion.fecha_cambio.isoformat(),
            'observacion': gestion.observacion,
        },
        status=200
    )


@login_required
@user_passes_test(es_administrador)
def detalle_solicitud_cotizacion(request, solicitud_id):

    try:
        solicitud = SolicitudCotizacion.objects.get(
            id=solicitud_id
        )
    except SolicitudCotizacion.DoesNotExist:
        return JsonResponse(
            {
                'success': False,
                'message': 'La solicitud no existe.'
            },
            status=404
        )

    estado = obtener_estado_cotizacion(solicitud)
    estado_display = obtener_estado_cotizacion_display(solicitud)

    return JsonResponse(
        {
            'success': True,
            'solicitud': {
                'id': solicitud.id,
                'estado': estado,
                'estado_display': estado_display,
            }
        }
    )