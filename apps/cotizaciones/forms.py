from django import forms
from django.utils import timezone

from .models import Cotizacion, LineaCotizacion


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ["validez_hasta", "observaciones"]
        widgets = {
            "validez_hasta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_validez_hasta(self):
        v = self.cleaned_data.get("validez_hasta")
        if v and v < timezone.localdate():
            raise forms.ValidationError("La fecha de validez no puede estar en el pasado.")
        return v


class LineaForm(forms.ModelForm):
    class Meta:
        model = LineaCotizacion
        fields = ["descripcion", "cantidad", "precio_unitario"]
        widgets = {"cantidad": forms.NumberInput(attrs={"min": 1}), "precio_unitario": forms.NumberInput(attrs={"min": 0})}

    def clean_cantidad(self):
        c = self.cleaned_data["cantidad"]
        if c < 1:
            raise forms.ValidationError("La cantidad debe ser al menos 1.")
        return c


LineaFormSet = forms.inlineformset_factory(
    Cotizacion, LineaCotizacion, form=LineaForm, extra=1, can_delete=True, min_num=1, validate_min=True
)
