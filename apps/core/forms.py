from django import forms
from django.core.validators import RegexValidator

from .models import ConfiguracionSitio


class ConfiguracionSitioForm(forms.ModelForm):
    whatsapp = forms.CharField(
        required=False,
        max_length=20,
        validators=[RegexValidator(r"^[0-9]*$", "Ingresa solo dígitos, incluido el código de país.")],
        help_text="Solo dígitos, incluido el código de país. Déjalo vacío para ocultar el acceso.",
    )

    class Meta:
        model = ConfiguracionSitio
        fields = (
            "nombre",
            "eslogan",
            "email",
            "telefono",
            "whatsapp",
            "direccion",
            "titulo_inicio",
            "texto_inicio",
        )
        labels = {
            "nombre": "Nombre de la empresa",
            "email": "Correo de contacto",
            "telefono": "Teléfono de contacto",
            "titulo_inicio": "Título institucional de inicio",
            "texto_inicio": "Texto institucional de inicio",
        }
        widgets = {
            "texto_inicio": forms.Textarea(attrs={"rows": 4}),
        }
