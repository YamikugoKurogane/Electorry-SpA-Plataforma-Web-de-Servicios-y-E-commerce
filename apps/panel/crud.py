"""Vistas CRUD genéricas del panel: evitan repetir código en cada mantenedor."""
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.auditoria import services as auditoria
from apps.core.permisos import PERSONAL, RolRequeridoMixin


class PanelMixin(RolRequeridoMixin):
    roles = PERSONAL
    seccion = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["seccion"] = self.seccion
        return ctx


class CrudListView(PanelMixin, ListView):
    template_name = "panel/crud_list.html"
    paginate_by = 20
    page_kwarg = "pagina"
    titulo = ""
    columnas = []  # [(etiqueta, atributo)]
    busqueda = ()  # campos para el buscador
    url_crear = None
    url_editar = None
    url_eliminar = None
    etiqueta_eliminar = "Eliminar"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.busqueda:
            cond = Q()
            for campo in self.busqueda:
                cond |= Q(**{f"{campo}__icontains": q})
            qs = qs.filter(cond)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            titulo=self.titulo, columnas=self.columnas, url_crear=self.url_crear, url_editar=self.url_editar,
            url_eliminar=self.url_eliminar, etiqueta_eliminar=self.etiqueta_eliminar,
            q=self.request.GET.get("q", ""), con_busqueda=bool(self.busqueda),
        )
        return ctx


class _FormAuditado(PanelMixin):
    template_name = "panel/crud_form.html"
    titulo = ""
    entidad = ""
    url_lista = ""

    def get_success_url(self):
        from django.urls import reverse

        return reverse(self.url_lista)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(titulo=self.titulo, url_lista=self.url_lista, multipart=self._multipart())
        return ctx

    def _multipart(self):
        form_class = self.get_form_class()
        return any(getattr(f.widget, "needs_multipart_form", False) for f in form_class.base_fields.values())

    def form_valid(self, form):
        nuevo = self.object is None
        with transaction.atomic():
            respuesta = super().form_valid(form)
            antes = None if nuevo else {c: form.initial.get(c) for c in form.changed_data if c != "password"}
            despues = {c: form.cleaned_data.get(c) for c in form.changed_data if c != "password"}
            auditoria.registrar(
                usuario=self.request.user,
                accion=auditoria.Accion.CREAR if nuevo else auditoria.Accion.EDITAR,
                entidad=self.entidad, entidad_id=self.object.pk, descripcion=str(self.object)[:200],
                antes=antes, despues=despues, request=self.request,
            )
        messages.success(self.request, "Guardado correctamente.")
        return respuesta


class CrudCreateView(_FormAuditado, CreateView):
    pass


class CrudUpdateView(_FormAuditado, UpdateView):
    pass


class CrudEliminarView(PanelMixin, View):
    """Elimina; si el registro está en uso (PROTECT) lo desactiva en vez de romper la integridad."""

    modelo = None
    entidad = ""
    url_lista = ""
    campo_activo = None  # p. ej. "activo" | "disponible" | "activa"

    def post(self, request, pk):
        obj = get_object_or_404(self.modelo, pk=pk)
        nombre = str(obj)
        try:
            with transaction.atomic():
                obj.delete()
                auditoria.registrar(
                    usuario=request.user, accion=auditoria.Accion.ELIMINAR, entidad=self.entidad, entidad_id=pk,
                    descripcion=nombre[:200], request=request,
                )
            messages.success(request, f"«{nombre}» fue eliminado.")
        except ProtectedError:
            if self.campo_activo:
                setattr(obj, self.campo_activo, False)
                obj.save()
                auditoria.registrar(
                    usuario=request.user, accion=auditoria.Accion.EDITAR, entidad=self.entidad, entidad_id=pk,
                    descripcion=f"{nombre} desactivado (tiene registros asociados)", request=request,
                )
                messages.warning(request, f"«{nombre}» tiene registros asociados, por lo que se desactivó en lugar de eliminarse.")
            else:
                messages.error(request, f"«{nombre}» no se puede eliminar porque tiene registros asociados.")
        from django.urls import reverse

        return redirect(reverse(self.url_lista))
