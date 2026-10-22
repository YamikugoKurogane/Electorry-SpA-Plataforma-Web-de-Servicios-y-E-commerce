from django import forms

from .models import CategoriaServicio, Servicio


class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["categoria", "nombre", "resumen", "descripcion", "disponible"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaServicio.objects.filter(activa=True)
        if self.instance.pk:
            self.fields["categoria"].queryset = CategoriaServicio.objects.all()


class CategoriaServicioForm(forms.ModelForm):
    class Meta:
        model = CategoriaServicio
        fields = ["nombre", "descripcion", "orden", "activa"]
