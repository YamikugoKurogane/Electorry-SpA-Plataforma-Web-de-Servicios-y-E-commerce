from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.busqueda import filtrar_texto
from apps.core.permisos import SOLO_CLIENTE, TODOS_AUTENTICADOS, rol_requerido

from . import services
from .carrito import Carrito
from .forms import CheckoutForm
from .models import CategoriaProducto, Producto


def lista(request):
    qs = Producto.objects.select_related("categoria").filter(activo=True, categoria__activa=True)
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("categoria", "")
    qs = filtrar_texto(qs, ("nombre", "descripcion"), q)
    if cat.isdigit():
        qs = qs.filter(categoria_id=int(cat))
    pagina = Paginator(qs, 12).get_page(request.GET.get("pagina"))
    return render(
        request, "tienda/lista.html",
        {"pagina": pagina, "categorias": CategoriaProducto.objects.filter(activa=True), "q": q, "cat": cat},
    )


def detalle(request, slug):
    producto = get_object_or_404(Producto.objects.select_related("categoria"), slug=slug, activo=True)
    return render(request, "tienda/detalle.html", {"producto": producto})


# ------------------------------------------------------------------ carrito


def ver_carrito(request):
    c = Carrito(request)
    return render(request, "tienda/carrito.html", {"lineas": c.lineas(), "total": c.total()})


@require_POST
def carrito_agregar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, activo=True, categoria__activa=True)
    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except ValueError:
        cantidad = 1
    Carrito(request).agregar(producto.pk, cantidad)
    messages.success(request, f"«{producto.nombre}» se agregó al carrito.")
    return redirect(request.POST.get("next") or "tienda:carrito")


@require_POST
def carrito_actualizar(request, producto_id):
    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except ValueError:
        cantidad = 1
    Carrito(request).agregar(producto_id, cantidad, reemplazar=True)
    return redirect("tienda:carrito")


@require_POST
def carrito_quitar(request, producto_id):
    Carrito(request).quitar(producto_id)
    return redirect("tienda:carrito")


# ------------------------------------------------------------------ compra


@rol_requerido(*SOLO_CLIENTE)
def checkout(request):
    carrito = Carrito(request)
    lineas = carrito.lineas()
    if not lineas:
        messages.info(request, "Tu carrito está vacío.")
        return redirect("tienda:lista")
    form = CheckoutForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            venta = services.crear_venta(cliente=request.user, lineas=lineas, datos_entrega=form.cleaned_data, request=request)
        except services.VentaError as exc:
            messages.error(request, str(exc))
            return redirect("tienda:carrito")
        carrito.vaciar()
        return redirect("pagos:iniciar", venta_id=venta.pk)
    return render(request, "tienda/checkout.html", {"form": form, "lineas": lineas, "total": carrito.total()})


@rol_requerido(*SOLO_CLIENTE)
def mis_compras(request):
    qs = services.ventas_visibles_para(request.user)
    pagina = Paginator(qs, 10).get_page(request.GET.get("pagina"))
    return render(request, "tienda/mis_compras.html", {"pagina": pagina})


@rol_requerido(*TODOS_AUTENTICADOS)
def compra_detalle(request, pk):
    venta = get_object_or_404(services.ventas_visibles_para(request.user).prefetch_related("detalles", "pagos"), pk=pk)
    return render(request, "tienda/compra_detalle.html", {"venta": venta})
