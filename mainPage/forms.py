from django import forms
from django.contrib.auth.models import User

class RegistroClienteForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'}),
        label="Contraseña"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar Contraseña'}),
        label="Confirmar Contraseña"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Correo electrónico'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

#Formulario para generar solicitud de cotizacion
from django import forms
from .models import SolicitudCotizacion


class SolicitudCotizacionForm(forms.ModelForm):

    class Meta:
        model = SolicitudCotizacion

        fields = [
            'nombre',
            'apellido',
            'correo',
            'telefono',
            'tipo_solicitud',
            'descripcion',
            'ubicacion',
            'archivo',
            'observaciones',
        ]

        widgets = {
            'nombre': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ingrese su nombre'
                }
            ),

            'apellido': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ingrese su apellido'
                }
            ),

            'correo': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'ejemplo@correo.com'
                }
            ),

            'telefono': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': '+56 9 XXXX XXXX'
                }
            ),

            'tipo_solicitud': forms.Select(
                attrs={
                    'class': 'form-control'
                }
            ),

            'descripcion': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Describa el producto o servicio que necesita',
                    'rows': 5
                }
            ),

            'ubicacion': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Indique la ubicación del proyecto'
                }
            ),

            'archivo': forms.ClearableFileInput(
                attrs={
                    'class': 'form-control'
                }
            ),

            'observaciones': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Agregue información adicional si es necesario',
                    'rows': 4
                }
            ),
        }

        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'correo': 'Correo electrónico',
            'telefono': 'Teléfono',
            'tipo_solicitud': 'Tipo de solicitud',
            'descripcion': 'Descripción',
            'ubicacion': 'Ubicación del proyecto',
            'archivo': 'Fotografías o archivos adicionales',
            'observaciones': 'Observaciones',
        }