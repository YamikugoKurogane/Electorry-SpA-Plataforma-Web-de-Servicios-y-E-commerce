from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.auditoria.models import RegistroAuditoria
from apps.catalogo.forms import CategoriaServicioForm, ServicioForm
from apps.catalogo.models import CategoriaServicio, Servicio
from apps.core.permisos import PERSONAL, SOLO_ADMIN, rol_requerido
from apps.cotizaciones import services as cot_services
from apps.cotizaciones.forms import CotizacionForm, LineaFormSet
from apps.cotizaciones.models import Cotizacion, EstadoCotizacion
from apps.notificaciones import services as notif_services
from apps.notificaciones.models import Notificacion
from apps.solicitudes import services as sol_services
from apps.solicitudes.forms import CambioEstadoForm
from apps.solicitudes.models import Estado, SolicitudCotizacion
from apps.tienda import services as venta_services
from apps.tienda.forms import CategoriaProductoForm, ProductoForm
from apps.tienda.models import CategoriaProducto, EstadoVenta, Producto, Venta
from apps.usuarios import services as usuario_services
from apps.usuarios.forms import UsuarioPersonalForm
from apps.usuarios.models import Rol, Usuario

from .crud import CrudCreateView, CrudEliminarView, CrudListView, CrudUpdateView


# ================================================================= dashboard
@rol_requerido(*PERSONAL)
def dashboard(request):
    por_estado = {e: 0 for e, _ in Estado.choices}
    for f in SolicitudCotizacion.objects.values("estado").annotate(n=Count("id")):
        por_estado[f["estado"]] = f["n"]
    ctx = {
        "seccion": "dashboard",
        "tarjetas": [(Estado(e).label, n, e) for e, n in por_estado.items() if e not in ("CANCELADA",)],
        "recientes": SolicitudCotizacion.objects.select_related("servicio").order_by("-creada")[:8],
        "borradores": Cotizacion.objects.filter(estado=EstadoCotizacion.BORRADOR).count(),
        "ventas_pendientes": Venta.objects.filter(estado=EstadoVenta.PENDIENTE_PAGO).count(),
        "correos_pendientes": Notificacion.objects.filter(estado=Notificacion.Estado.PENDIENTE).count(),
        "correos_fallidos": Notificacion.objects.filter(estado=Notificacion.Estado.FALLIDA).count(),
    }
    return render(request, "panel/dashboard.html", ctx)


# ================================================================= solicitudes (RF-05)
@rol_requerido(*PERSONAL)
def solicitudes_lista(request):
    qs = SolicitudCotizacion.objects.select_related("servicio", "cliente")
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    servicio = request.GET.get("servicio", "")
    desde, hasta = parse_date(request.GET.get("desde", "") or ""), parse_date(request.GET.get("hasta", "") or "")
    if q:
        cond = Q(nombre_contacto__icontains=q) | Q(email_contacto__icontains=q) | Q(descripcion__icontains=q) | Q(direccion__icontains=q)
        if q.upper().startswith("SOL-") and q[4:].isdigit():
            cond |= Q(pk=int(q[4:]))
        elif q.isdigit():
            cond |= Q(pk=int(q))
        qs = qs.filter(cond)
    if estado in dict(Estado.choices):
        qs = qs.filter(estado=estado)
    if servicio.isdigit():
        qs = qs.filter(servicio_id=int(servicio))
    if desde:
        qs = qs.filter(creada__date__gte=desde)
    if hasta:
        qs = qs.filter(creada__date__lte=hasta)
    pagina = Paginator(qs, 20).get_page(request.GET.get("pagina"))
    return render(
        request, "panel/solicitudes_lista.html",
        {"seccion": "solicitudes", "pagina": pagina, "estados": Estado.choices, "servicios": Servicio.objects.all(),
         "q": q, "estado": estado, "servicio": servicio, "desde": request.GET.get("desde", ""), "hasta": request.GET.get("hasta", "")},
    )


@rol_requerido(*PERSONAL)
def solicitud_detalle(request, pk):
    solicitud = sol_services.obtener_solicitud_para(request.user, pk, request)
    permitidos = sol_services.transiciones_permitidas(solicitud.estado)
    form = CambioEstadoForm(request.POST or None, permitidos=permitidos)
    if request.method == "POST":
        if form.is_valid():
            try:
                sol_services.cambiar_estado(solicitud, form.cleaned_data["estado"], request.user, form.cleaned_data["comentario"], request)
                messages.success(request, "Estado actualizado y cliente notificado.")
                return redirect("panel:solicitud_detalle", pk=pk)
            except sol_services.TransicionInvalida as exc:
                messages.error(request, str(exc))
    return render(
        request, "panel/solicitud_detalle.html",
        {"seccion": "solicitudes", "solicitud": solicitud, "form": form, "permitidos": permitidos,
         "historial": solicitud.historial.all(), "adjuntos": solicitud.adjuntos.all(),
         "cotizaciones": solicitud.cotizaciones.prefetch_related("lineas")},
    )


# ================================================================= cotizaciones (RF-08)
@rol_requerido(*PERSONAL)
def cotizaciones_lista(request):
    qs = Cotizacion.objects.select_related("solicitud__servicio").prefetch_related("lineas")
    estado = request.GET.get("estado", "")
    q = request.GET.get("q", "").strip()
    if estado in dict(EstadoCotizacion.choices):
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(Q(solicitud__nombre_contacto__icontains=q) | Q(solicitud__email_contacto__icontains=q))
    pagina = Paginator(qs, 20).get_page(request.GET.get("pagina"))
    return render(request, "panel/cotizaciones_lista.html", {"seccion": "cotizaciones", "pagina": pagina, "estados": EstadoCotizacion.choices, "estado": estado, "q": q})


def _lineas_validas(formset):
    return [
        {"descripcion": f.cleaned_data["descripcion"], "cantidad": f.cleaned_data["cantidad"], "precio_unitario": f.cleaned_data["precio_unitario"]}
        for f in formset.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")
    ]


@rol_requerido(*PERSONAL)
def cotizacion_form(request, solicitud_id=None, pk=None):
    if pk:
        cot = get_object_or_404(Cotizacion.objects.select_related("solicitud"), pk=pk)
        solicitud = cot.solicitud
        if not cot.editable:
            messages.error(request, "Solo se pueden editar cotizaciones en borrador.")
            return redirect("cotizaciones:detalle", pk=pk)
    else:
        solicitud = get_object_or_404(SolicitudCotizacion, pk=solicitud_id)
        cot = Cotizacion(solicitud=solicitud)
    form = CotizacionForm(request.POST or None, instance=cot)
    formset = LineaFormSet(request.POST or None, instance=cot)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        lineas = _lineas_validas(formset)
        try:
            if pk:
                cot = cot_services.actualizar_cotizacion(cot, usuario=request.user, lineas=lineas, validez_hasta=form.cleaned_data["validez_hasta"], observaciones=form.cleaned_data["observaciones"], request=request)
            else:
                cot = cot_services.crear_cotizacion(solicitud=solicitud, usuario=request.user, lineas=lineas, validez_hasta=form.cleaned_data["validez_hasta"], observaciones=form.cleaned_data["observaciones"], request=request)
            messages.success(request, "Cotización guardada como borrador. Revísala y envíala al cliente.")
            return redirect("cotizaciones:detalle", pk=cot.pk)
        except cot_services.CotizacionError as exc:
            messages.error(request, str(exc))
    return render(request, "panel/cotizacion_form.html", {"seccion": "cotizaciones", "form": form, "formset": formset, "solicitud": solicitud, "cot": cot if pk else None})


@require_POST
@rol_requerido(*PERSONAL)
def cotizacion_enviar(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    try:
        cot_services.enviar_cotizacion(cot, request.user, request)
        messages.success(request, "Cotización enviada al cliente.")
    except cot_services.CotizacionError as exc:
        messages.error(request, str(exc))
    return redirect("cotizaciones:detalle", pk=pk)


# ================================================================= clientes (RF-07)
@rol_requerido(*PERSONAL)
def clientes_lista(request):
    qs = Usuario.objects.filter(rol=Rol.CLIENTE).annotate(
        n_solicitudes=Count("solicitudes", distinct=True), n_compras=Count("ventas", distinct=True)
    ).order_by("last_name", "first_name")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(telefono__icontains=q))
    pagina = Paginator(qs, 20).get_page(request.GET.get("pagina"))
    return render(request, "panel/clientes_lista.html", {"seccion": "clientes", "pagina": pagina, "q": q})


@rol_requerido(*PERSONAL)
def cliente_detalle(request, pk):
    cliente = get_object_or_404(Usuario, pk=pk, rol=Rol.CLIENTE)
    return render(
        request, "panel/cliente_detalle.html",
        {"seccion": "clientes", "cliente": cliente,
         "solicitudes": cliente.solicitudes.select_related("servicio"), "ventas": cliente.ventas.all()},
    )


@require_POST
@rol_requerido(*SOLO_ADMIN)
def cliente_anonimizar(request, pk):
    cliente = get_object_or_404(Usuario, pk=pk, rol=Rol.CLIENTE)
    usuario_services.anonimizar_usuario(cliente, por=request.user, request=request)
    messages.success(request, "Se eliminaron los datos personales del cliente.")
    return redirect("panel:clientes")


# ================================================================= servicios y categorías (RF-06)
class ServicioLista(CrudListView):
    roles = SOLO_ADMIN
    seccion = "servicios"
    model = Servicio
    queryset = Servicio.objects.select_related("categoria")
    titulo = "Servicios"
    columnas = [("Servicio", "nombre"), ("Categoría", "categoria"), ("Disponible", "disponible")]
    busqueda = ("nombre", "resumen")
    url_crear, url_editar, url_eliminar = "panel:servicio_crear", "panel:servicio_editar", "panel:servicio_eliminar"


class ServicioCrear(CrudCreateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "servicios", "Nuevo servicio", "servicio", "panel:servicios"
    model, form_class = Servicio, ServicioForm


class ServicioEditar(CrudUpdateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "servicios", "Editar servicio", "servicio", "panel:servicios"
    model, form_class = Servicio, ServicioForm


class ServicioEliminar(CrudEliminarView):
    roles = SOLO_ADMIN
    modelo, entidad, url_lista, campo_activo = Servicio, "servicio", "panel:servicios", "disponible"


class CategoriaServicioLista(CrudListView):
    roles = SOLO_ADMIN
    seccion = "servicios"
    model = CategoriaServicio
    titulo = "Categorías de servicios"
    columnas = [("Nombre", "nombre"), ("Orden", "orden"), ("Activa", "activa")]
    busqueda = ("nombre",)
    url_crear, url_editar, url_eliminar = "panel:catserv_crear", "panel:catserv_editar", "panel:catserv_eliminar"


class CategoriaServicioCrear(CrudCreateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "servicios", "Nueva categoría", "categoria_servicio", "panel:catserv"
    model, form_class = CategoriaServicio, CategoriaServicioForm


class CategoriaServicioEditar(CrudUpdateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "servicios", "Editar categoría", "categoria_servicio", "panel:catserv"
    model, form_class = CategoriaServicio, CategoriaServicioForm


class CategoriaServicioEliminar(CrudEliminarView):
    roles = SOLO_ADMIN
    modelo, entidad, url_lista, campo_activo = CategoriaServicio, "categoria_servicio", "panel:catserv", "activa"


# ================================================================= productos y categorías (RF-12)
class ProductoLista(CrudListView):
    roles = SOLO_ADMIN
    seccion = "productos"
    model = Producto
    queryset = Producto.objects.select_related("categoria")
    titulo = "Productos"
    columnas = [("Producto", "nombre"), ("Categoría", "categoria"), ("Precio", "precio"), ("Activo", "activo")]
    busqueda = ("nombre", "descripcion")
    url_crear, url_editar, url_eliminar = "panel:producto_crear", "panel:producto_editar", "panel:producto_eliminar"


class ProductoCrear(CrudCreateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "productos", "Nuevo producto", "producto", "panel:productos"
    model, form_class = Producto, ProductoForm


class ProductoEditar(CrudUpdateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "productos", "Editar producto", "producto", "panel:productos"
    model, form_class = Producto, ProductoForm


class ProductoEliminar(CrudEliminarView):
    roles = SOLO_ADMIN
    modelo, entidad, url_lista, campo_activo = Producto, "producto", "panel:productos", "activo"


class CategoriaProductoLista(CrudListView):
    roles = SOLO_ADMIN
    seccion = "productos"
    model = CategoriaProducto
    titulo = "Categorías de productos"
    columnas = [("Nombre", "nombre"), ("Activa", "activa")]
    busqueda = ("nombre",)
    url_crear, url_editar, url_eliminar = "panel:catprod_crear", "panel:catprod_editar", "panel:catprod_eliminar"


class CategoriaProductoCrear(CrudCreateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "productos", "Nueva categoría", "categoria_producto", "panel:catprod"
    model, form_class = CategoriaProducto, CategoriaProductoForm


class CategoriaProductoEditar(CrudUpdateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "productos", "Editar categoría", "categoria_producto", "panel:catprod"
    model, form_class = CategoriaProducto, CategoriaProductoForm


class CategoriaProductoEliminar(CrudEliminarView):
    roles = SOLO_ADMIN
    modelo, entidad, url_lista, campo_activo = CategoriaProducto, "categoria_producto", "panel:catprod", "activa"


# ================================================================= ventas (RF-14)
@rol_requerido(*PERSONAL)
def ventas_lista(request):
    qs = Venta.objects.select_related("cliente")
    estado = request.GET.get("estado", "")
    q = request.GET.get("q", "").strip()
    if estado in dict(EstadoVenta.choices):
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(Q(nombre_cliente__icontains=q) | Q(cliente__email__icontains=q))
    pagina = Paginator(qs, 20).get_page(request.GET.get("pagina"))
    return render(request, "panel/ventas_lista.html", {"seccion": "ventas", "pagina": pagina, "estados": EstadoVenta.choices, "estado": estado, "q": q})


@rol_requerido(*PERSONAL)
def venta_detalle(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("cliente").prefetch_related("detalles", "pagos"), pk=pk)
    return render(request, "panel/venta_detalle.html", {"seccion": "ventas", "venta": venta})


@require_POST
@rol_requerido(*SOLO_ADMIN)
def venta_accion(request, pk):
    accion = request.POST.get("accion")
    try:
        if accion == "cancelar":
            venta_services.cancelar_venta(pk, request.user, request)
            messages.success(request, "Venta cancelada.")
        elif accion == "pagada_manual":
            venta_services.marcar_pagada(pk, usuario=request.user, referencia="transferencia/manual", request=request)
            messages.success(request, "Venta marcada como pagada (pago manual).")
    except venta_services.VentaError as exc:
        messages.error(request, str(exc))
    return redirect("panel:venta_detalle", pk=pk)


# ================================================================= usuarios y roles (RF-10)
class UsuarioLista(CrudListView):
    roles = SOLO_ADMIN
    seccion = "usuarios"
    model = Usuario
    titulo = "Usuarios y roles"
    columnas = [("Nombre", "nombre_completo"), ("Correo", "email"), ("Rol", "get_rol_display"), ("Activo", "is_active")]
    busqueda = ("email", "first_name", "last_name")
    url_crear, url_editar = "panel:usuario_crear", "panel:usuario_editar"

    def get_queryset(self):
        qs = super().get_queryset()
        rol = self.request.GET.get("rol", "")
        return qs.filter(rol=rol) if rol in dict(Rol.choices) else qs


class UsuarioCrear(CrudCreateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "usuarios", "Nuevo usuario", "usuario", "panel:usuarios"
    model, form_class = Usuario, UsuarioPersonalForm


class UsuarioEditar(CrudUpdateView):
    roles = SOLO_ADMIN
    seccion, titulo, entidad, url_lista = "usuarios", "Editar usuario", "usuario", "panel:usuarios"
    model, form_class = Usuario, UsuarioPersonalForm

    def form_valid(self, form):
        if self.object.pk == self.request.user.pk and (not form.cleaned_data["is_active"] or form.cleaned_data["rol"] != Rol.ADMIN):
            messages.error(self.request, "No puedes quitarte tu propio acceso de administrador.")
            return self.form_invalid(form)
        return super().form_valid(form)


# ================================================================= auditoría y notificaciones
@rol_requerido(*SOLO_ADMIN)
def auditoria_lista(request):
    qs = RegistroAuditoria.objects.all()
    entidad, accion, q = request.GET.get("entidad", ""), request.GET.get("accion", ""), request.GET.get("q", "").strip()
    entidad_id = request.GET.get("id", "")
    if entidad:
        qs = qs.filter(entidad=entidad)
    if accion:
        qs = qs.filter(accion=accion)
    if entidad_id.isdigit():
        qs = qs.filter(entidad_id=int(entidad_id))
    if q:
        qs = qs.filter(Q(usuario_email__icontains=q) | Q(descripcion__icontains=q))
    pagina = Paginator(qs, 30).get_page(request.GET.get("pagina"))
    return render(
        request, "panel/auditoria_lista.html",
        {"seccion": "auditoria", "pagina": pagina, "entidad": entidad, "accion": accion, "q": q, "id": entidad_id,
         "entidades": RegistroAuditoria.objects.order_by().values_list("entidad", flat=True).distinct(),
         "acciones": RegistroAuditoria.objects.order_by().values_list("accion", flat=True).distinct()},
    )


@rol_requerido(*SOLO_ADMIN)
def notificaciones_lista(request):
    if request.method == "POST":
        n = notif_services.reintentar_pendientes()
        messages.success(request, f"Reintento completado: {n} correo(s) enviado(s).")
        return redirect("panel:notificaciones")
    estado = request.GET.get("estado", "")
    qs = Notificacion.objects.all()
    if estado in dict(Notificacion.Estado.choices):
        qs = qs.filter(estado=estado)
    pagina = Paginator(qs, 30).get_page(request.GET.get("pagina"))
    return render(request, "panel/notificaciones_lista.html", {"seccion": "notificaciones", "pagina": pagina, "estado": estado, "estados": Notificacion.Estado.choices})
