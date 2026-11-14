"""Información adicional desde el panel: pedir datos al cliente y retirar preguntas (RF-25, S4-R2)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.core.permisos import PERSONAL, rol_requerido
from apps.solicitudes import requerimientos, services
from apps.solicitudes.forms import PedirInfoForm
from apps.solicitudes.models import RequerimientoInfo


@require_POST
@rol_requerido(*PERSONAL)
def info_pedir(request, pk):
    solicitud = services.obtener_solicitud_para(request.user, pk, request)
    form = PedirInfoForm(request.POST)
    if form.is_valid():
        try:
            requerimientos.pedir_informacion(solicitud, request.user, form.cleaned_data["pregunta"], request)
            messages.success(request, "Pregunta enviada. Avisamos al cliente por correo.")
        except requerimientos.RequerimientoError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, " ".join(form.errors["pregunta"]))
    return redirect("panel:solicitud_detalle", pk=pk)


@require_POST
@rol_requerido(*PERSONAL)
def info_cancelar(request, pk):
    req = get_object_or_404(RequerimientoInfo, pk=pk)
    try:
        requerimientos.cancelar_requerimiento(req.pk, request.user, request)
        messages.success(request, "Pregunta cancelada.")
    except requerimientos.RequerimientoError as exc:
        messages.error(request, str(exc))
    return redirect("panel:solicitud_detalle", pk=req.solicitud_id)
