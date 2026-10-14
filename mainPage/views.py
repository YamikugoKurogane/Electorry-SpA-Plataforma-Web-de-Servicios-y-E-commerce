import io
import logging

from django.contrib import messages  # pyright: ignore[reportMissingModuleSource]
from django.contrib.auth import login  # pyright: ignore[reportMissingModuleSource]
from django.contrib.auth.decorators import user_passes_test  # pyright: ignore[reportMissingModuleSource]
from django.http import HttpResponse  # pyright: ignore[reportMissingModuleSource]
from django.shortcuts import get_object_or_404, redirect, render  # pyright: ignore[reportMissingModuleSource]
from django.template.loader import get_template  # pyright: ignore[reportMissingModuleSource]
from django.views.decorators.http import require_POST  # pyright: ignore[reportMissingModuleSource]

try:
    from xhtml2pdf import pisa  # pyright: ignore[reportMissingImports]
except ImportError:
    pisa = None

from .forms import ProductoForm, RegistroClienteForm, ServicioForm
from .models import Cotizacion, Producto, Servicio

logger = logging.getLogger("django")


def home(request):
    return render(request, "index.html")


def registro_cliente_view(request):
    if request.method == "POST":
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()

            logger.info(f"Nuevo cliente registrado exitosamente: {user.username} ({user.email})")

            login(request, user)
            messages.success(request, f"¡Bienvenido/a {user.first_name}! Registro completado con éxito.")
            return redirect("home")
        else:
            logger.warning("Intento fallido de registro de usuario.")
    else:
        form = RegistroClienteForm()

    return render(request, "registro.html", {"form": form})


# --- Función para generar PDF de Cotización [RF-28] ---

def es_administrador(user):
    return user.is_authenticated and user.is_staff


# ============================================================
# MANTENEDOR CRUD DE PRODUCTOS [HU-11/12 - RF-13]
# ============================================================


@user_passes_test(es_administrador)
def admin_productos(request):
    productos = Producto.objects.select_related("categoria").all()

    return render(
        request,
        "mainPage/admin_productos.html",
        {"productos": productos},
    )


@user_passes_test(es_administrador)
def crear_producto(request):
    form = ProductoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Producto creado correctamente.")
        return redirect("admin_productos")

    return render(
        request,
        "mainPage/producto_form.html",
        {"form": form, "titulo": "Crear producto"},
    )


@user_passes_test(es_administrador)
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    form = ProductoForm(request.POST or None, instance=producto)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Producto actualizado correctamente.")
        return redirect("admin_productos")

    return render(
        request,
        "mainPage/producto_form.html",
        {"form": form, "titulo": "Editar producto"},
    )


@user_passes_test(es_administrador)
@require_POST
def desactivar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    producto.estado = False
    producto.save(update_fields=["estado"])

    messages.success(request, "Producto desactivado correctamente.")
    return redirect("admin_productos")


# ============================================================
# MANTENEDOR CRUD DE SERVICIOS [HU-13 - RF-14]
# ============================================================


@user_passes_test(es_administrador)
def admin_servicios(request):
    servicios = Servicio.objects.all()

    return render(
        request,
        "mainPage/admin_servicios.html",
        {"servicios": servicios},
    )


@user_passes_test(es_administrador)
def crear_servicio(request):
    form = ServicioForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Servicio creado correctamente.")
        return redirect("admin_servicios")

    return render(
        request,
        "mainPage/servicio_form.html",
        {"form": form, "titulo": "Crear servicio"},
    )


@user_passes_test(es_administrador)
def editar_servicio(request, servicio_id):
    servicio = get_object_or_404(Servicio, id=servicio_id)
    form = ServicioForm(request.POST or None, instance=servicio)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Servicio actualizado correctamente.")
        return redirect("admin_servicios")

    return render(
        request,
        "mainPage/servicio_form.html",
        {"form": form, "titulo": "Editar servicio"},
    )


@user_passes_test(es_administrador)
@require_POST
def desactivar_servicio(request, servicio_id):
    servicio = get_object_or_404(Servicio, id=servicio_id)
    servicio.estado = False
    servicio.save(update_fields=["estado"])

    messages.success(request, "Servicio desactivado correctamente.")
    return redirect("admin_servicios")


def generar_cotizacion_pdf(request, cotizacion_id):
    cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id)
    template = get_template("cotizaciones/cotizacion_pdf.html")
    context = {"cotizacion": cotizacion, "empresa": "Electorry SpA"}
    html = template.render(context)

    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)

    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Cotizacion_Electorry_{cotizacion.id}.pdf"'
        )
        return response

    return HttpResponse("Error al generar el PDF", status=500)
