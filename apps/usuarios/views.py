from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.auditoria import services as auditoria

from . import services
from .forms import EliminarCuentaForm, LoginForm, PerfilForm, RegistroForm


class IngresarView(LoginView):
    template_name = "usuarios/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        destino = self.get_redirect_url()
        if destino:
            return destino
        return reverse("panel:dashboard") if self.request.user.es_personal else reverse("core:inicio")


def registro(request):
    if request.user.is_authenticated:
        return redirect("core:inicio")
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save(request=request)
        login(request, usuario)
        messages.success(request, "¡Cuenta creada! Ya puedes solicitar cotizaciones y comprar.")
        return redirect(request.POST.get("next") or request.GET.get("next") or "core:inicio")
    return render(request, "usuarios/registro.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def perfil(request):
    form = PerfilForm(request.POST or None, instance=request.user, prefix="perfil")
    if request.method == "POST" and form.is_valid():
        form.save()
        auditoria.registrar(
            usuario=request.user, accion=auditoria.Accion.EDITAR, entidad="usuario", entidad_id=request.user.pk,
            descripcion="Actualización de datos personales", request=request,
        )
        messages.success(request, "Tus datos fueron actualizados.")
        return redirect("usuarios:perfil")
    return render(request, "usuarios/perfil.html", {"form": form})


@login_required
def cambiar_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        messages.success(request, "Contraseña actualizada.")
        return redirect("usuarios:perfil")
    return render(request, "usuarios/cambiar_password.html", {"form": form})


@login_required
def eliminar_cuenta(request):
    """Derecho de supresión de datos personales (RNF-SEG-07)."""
    if not request.user.es_cliente:
        messages.error(request, "Las cuentas internas las gestiona un administrador.")
        return redirect("usuarios:perfil")
    form = EliminarCuentaForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        services.anonimizar_usuario(request.user, request=request)
        logout(request)
        messages.success(request, "Eliminamos tus datos personales. Gracias por haber usado Electorry.")
        return redirect("core:inicio")
    return render(request, "usuarios/eliminar_cuenta.html", {"form": form})


@require_POST
def salir(request):
    logout(request)
    return redirect("core:inicio")
