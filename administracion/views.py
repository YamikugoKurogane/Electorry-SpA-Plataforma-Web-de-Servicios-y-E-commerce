import json
import logging
from django.shortcuts import render, redirect, get_object_or_404  # type: ignore
from django.http import JsonResponse  # type: ignore
from django.views.decorators.http import require_POST  # type: ignore
from django.contrib.auth.decorators import login_required, user_passes_test  # type: ignore
from django.contrib import messages  # type: ignore
from django.core.exceptions import ValidationError  # type: ignore

from .services import (
    cambiar_estado_cotizacion,
    obtener_estado_cotizacion,
    obtener_estado_cotizacion_display,
)

# IMPORTACIONES DESDE MAINPAGE (MODELOS Y FORMULARIOS)
from mainPage.models import SolicitudCotizacion, Servicio  # type: ignore
from mainPage.forms import ServicioForm  # type: ignore
from .models import GestionEstadoCotizacion  # type: ignore

# Configuración del logger alineado con ejecucion.log
logger = logging.getLogger('ejecucion')

# Función de validación de rol para RBAC (Staff / Administrador)
def es_administrador(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# --- VISTA PRINCIPAL DE ADMINISTRACIÓN (PROTEGIDA CON RBAC) ---
@login_required
@user_passes_test(es_administrador)
def homeAdmin(request):
    return render(request, "indexAdmin.html")


# ============================================================
# VISTAS CRUD PARA MANTENEDOR DE SERVICIOS FOTOVOLTAICOS [HU-11]
# ============================================================

@login_required
@user_passes_test(es_administrador)
def servicio_listar(request):
    servicios = Servicio.objects.all()
    return render(request, 'administracion/servicios_list.html', {'servicios': servicios})


@login_required
@user_passes_test(es_administrador)
def servicio_crear(request):
    if request.method == 'POST':
        form = ServicioForm(request.POST, request.FILES)
        if form.is_valid():
            servicio = form.save()
            logger.info(f"[CRUD SERVICIOS] Servicio creado exitosamente: ID {servicio.id} - '{servicio.nombre}' por usuario '{request.user.username}'")
            messages.success(request, f"Servicio '{servicio.nombre}' creado exitosamente.")
            return redirect('servicio_listar')
        else:
            logger.warning(f"[CRUD SERVICIOS] Error de validación al crear servicio por usuario '{request.user.username}': {form.errors}")
    else:
        form = ServicioForm()
    return render(request, 'administracion/servicio_form.html', {'form': form, 'titulo': 'Crear Servicio Fotovoltaico'})


@login_required
@user_passes_test(es_administrador)
def servicio_editar(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    if request.method == 'POST':
        form = ServicioForm(request.POST, request.FILES, instance=servicio)
        if form.is_valid():
            form.save()
            logger.info(f"[CRUD SERVICIOS] Servicio actualizado: ID {servicio.id} - '{servicio.nombre}' por usuario '{request.user.username}'")
            messages.success(request, f"Servicio '{servicio.nombre}' actualizado correctamente.")
            return redirect('servicio_listar')
    else:
        form = ServicioForm(instance=servicio)
    return render(request, 'administracion/servicio_form.html', {'form': form, 'titulo': 'Editar Servicio Fotovoltaico'})


@login_required
@user_passes_test(es_administrador)
def servicio_eliminar(request, pk):
    servicio = get_object_or_404(Servicio, pk=pk)
    if request.method == 'POST':
        nombre = servicio.nombre
        servicio.delete()
        logger.info(f"[CRUD SERVICIOS] Servicio eliminado: ID {pk} - '{nombre}' por usuario '{request.user.username}'")
        messages.success(request, f"Servicio '{nombre}' eliminado correctamente.")
        return redirect('servicio_listar')
    return render(request, 'administracion/servicio_confirm_delete.html', {'servicio': servicio})


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