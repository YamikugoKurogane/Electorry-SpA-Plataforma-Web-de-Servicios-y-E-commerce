from django import forms

from apps.catalogo.models import Servicio
from apps.tienda.models import Producto

from . import services
from .models import Oferta


class OfertaForm(forms.ModelForm):
    class Meta:
        model = Oferta
        fields = ["titulo", "descripcion", "descuento", "fecha_inicio", "fecha_fin", "solo_clientes", "productos", "servicios"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descuento": forms.NumberInput(attrs={"min": 1, "max": 90}),
            "productos": forms.CheckboxSelectMultiple,
            "servicios": forms.CheckboxSelectMultiple,
        }
        help_texts = {"productos": "Marca los productos incluidos.", "servicios": "Marca los servicios incluidos."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        seleccionados = []
        if self.instance.pk:
            seleccionados = list(self.instance.productos.values_list("pk", flat=True))
        activos = Producto.objects.filter(activo=True, categoria__activa=True) | Producto.objects.filter(pk__in=seleccionados)
        self.fields["productos"].queryset = activos.distinct().order_by("nombre")
        self.fields["productos"].label_from_instance = lambda p: f"{p.nombre} (${p.precio:,})".replace(",", ".")
        self.fields["servicios"].queryset = Servicio.objects.filter(categoria__activa=True).order_by("nombre")
        self.fields["descuento"].help_text = "Porcentaje entre 1 y 90."

    def clean(self):
        datos = super().clean()
        # Las mismas reglas que aplica el servicio (se informan todas juntas en el formulario)
        if not self.errors:
            for problema in services.validar_oferta(datos, datos.get("productos") or [], datos.get("servicios") or [], oferta=self.instance if self.instance.pk else None):
                self.add_error(None, problema)
        return datos

    def datos(self):
        d = self.cleaned_data
        return {k: d[k] for k in ("titulo", "descripcion", "descuento", "fecha_inicio", "fecha_fin", "solo_clientes")}
