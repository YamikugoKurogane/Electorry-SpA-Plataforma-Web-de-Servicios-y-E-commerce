from django import forms
from django.core.exceptions import ValidationError

from apps.usuarios.forms import validar_telefono

from .models import CategoriaProducto, Producto


def validar_imagen(imagen):
    if imagen and hasattr(imagen, "size"):
        nombre = (imagen.name or "").lower()
        if not nombre.endswith((".jpg", ".jpeg", ".png")):
            raise ValidationError("La imagen debe ser JPG o PNG.")
        if imagen.size > 2 * 1024 * 1024:
            raise ValidationError("La imagen no puede superar 2 MB.")
    return imagen


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["categoria", "nombre", "descripcion", "precio", "imagen", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def clean_imagen(self):
        return validar_imagen(self.cleaned_data.get("imagen"))

    def clean_precio(self):
        p = self.cleaned_data["precio"]
        if p <= 0:
            raise ValidationError("El precio debe ser mayor a 0.")
        return p


class CategoriaProductoForm(forms.ModelForm):
    class Meta:
        model = CategoriaProducto
        fields = ["nombre", "activa"]


class CheckoutForm(forms.Form):
    nombre_cliente = forms.CharField(label="Nombre de quien recibe", max_length=150)
    direccion_entrega = forms.CharField(label="Dirección de entrega", max_length=250)
    telefono_contacto = forms.CharField(label="Teléfono de contacto", max_length=20, validators=[validar_telefono])

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None and not self.is_bound:
            self.initial.setdefault("nombre_cliente", usuario.nombre_completo)
            self.initial.setdefault("telefono_contacto", usuario.telefono)
