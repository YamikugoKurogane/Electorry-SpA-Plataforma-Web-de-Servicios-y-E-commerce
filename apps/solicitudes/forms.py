from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError


from apps.catalogo.models import Servicio
from apps.tienda.models import Producto
from apps.usuarios.forms import validar_telefono

from .models import Estado
from .services import MAX_CANTIDAD_POR_PRODUCTO, MAX_PRODUCTOS_POR_SOLICITUD
from .validators import validar_adjunto


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ".jpg,.jpeg,.png,.pdf"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        archivos = data if isinstance(data, (list, tuple)) else [data]
        if len(archivos) > settings.ADJUNTOS_MAX_CANTIDAD:
            raise ValidationError(f"Puedes adjuntar hasta {settings.ADJUNTOS_MAX_CANTIDAD} archivos.")
        limpios = []
        for a in archivos:
            limpios.append(validar_adjunto(super().clean(a, initial)))
        return limpios


class SolicitudForm(forms.Form):
    """Formulario mínimo (EC-04, RNF-USA-01)."""

    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.none(), required=False, label="Servicio (opcional si cotizas productos)",
        empty_label="Sin servicio: solo productos",
    )
    descripcion = forms.CharField(
        label="Cuéntanos qué necesitas", min_length=15, widget=forms.Textarea(attrs={"rows": 5}),
        error_messages={"min_length": "Describe tu requerimiento con al menos 15 caracteres."},
    )
    observaciones = forms.CharField(
        label="Observaciones (opcional)", required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Horarios, accesos, plazos u otra información útil.",
    )
    direccion = forms.CharField(label="Dirección donde se realizará", max_length=250)
    comuna = forms.CharField(label="Comuna", max_length=100, required=False)
    nombre_contacto = forms.CharField(label="Nombre de contacto", max_length=150)
    telefono_contacto = forms.CharField(label="Teléfono de contacto", max_length=20, validators=[validar_telefono])
    email_contacto = forms.EmailField(label="Correo de contacto")
    archivos = MultipleFileField(
        label="Fotos o documentos (opcional)", required=False,
        help_text="JPG, PNG o PDF. Hasta 5 archivos de 5 MB cada uno.",
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servicio"].queryset = Servicio.objects.filter(disponible=True, categoria__activa=True)
        if usuario is not None and not self.is_bound:
            self.initial.setdefault("nombre_contacto", usuario.nombre_completo)
            self.initial.setdefault("telefono_contacto", usuario.telefono)
            self.initial.setdefault("email_contacto", usuario.email)


class ItemSolicitudForm(forms.Form):
    """Una fila «producto + cantidad». Las filas sin producto se ignoran."""

    producto = forms.ModelChoiceField(queryset=Producto.objects.none(), required=False, empty_label="Selecciona un producto", label="Producto")
    cantidad = forms.IntegerField(
        required=False, initial=1, min_value=1, max_value=MAX_CANTIDAD_POR_PRODUCTO, label="Cantidad",
        error_messages={"min_value": "La cantidad mínima es 1.", "max_value": f"La cantidad máxima es {MAX_CANTIDAD_POR_PRODUCTO}."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.select_related("categoria").filter(activo=True, categoria__activa=True)
        self.fields["producto"].label_from_instance = lambda p: p.nombre

    def clean(self):
        datos = super().clean()
        if datos.get("producto") and not datos.get("cantidad"):
            datos["cantidad"] = 1
        return datos


ItemFormSet = forms.formset_factory(ItemSolicitudForm, extra=2, max_num=MAX_PRODUCTOS_POR_SOLICITUD, validate_max=True)


def items_validos(formset):
    """Lista de (producto, cantidad) de las filas con producto (las repetidas las une el servicio)."""
    return [
        (f.cleaned_data["producto"], f.cleaned_data.get("cantidad") or 1)
        for f in formset.forms if f.cleaned_data and f.cleaned_data.get("producto")
    ]


class CambioEstadoForm(forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado", choices=[])
    comentario = forms.CharField(label="Comentario (se envía al cliente)", max_length=300, required=False)

    def __init__(self, *args, permitidos=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = [(e, Estado(e).label) for e in permitidos]
