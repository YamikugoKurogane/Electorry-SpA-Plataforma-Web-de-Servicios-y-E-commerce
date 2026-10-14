from django import forms  # type: ignore[reportMissingImports]
from django.contrib.auth.models import User  # type: ignore[reportMissingImports]

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
from django import forms  # type: ignore[reportMissingImports]
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
# ============================================================
# FORMULARIO CRUD DE PRODUCTOS
# ============================================================

from .models import Producto, Servicio


class ProductoForm(forms.ModelForm):

    class Meta:
        model = Producto
        fields = [
            'categoria',
            'nombre',
            'descripcion',
            'sku',
            'precio',
            'stock',
            'imagen_url',
            'estado',
        ]

        widgets = {
            'categoria': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'nombre': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Nombre del producto'
                }
            ),
            'descripcion': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Descripción del producto',
                    'rows': 4
                }
            ),
            'sku': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Código SKU (opcional)'
                }
            ),
            'precio': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0',
                    'step': '0.01'
                }
            ),
            'stock': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0',
                    'step': '1'
                }
            ),
            'imagen_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'https://ejemplo.com/imagen.jpg'
                }
            ),
            'estado': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio < 0:
            raise forms.ValidationError(
                'El precio no puede ser negativo.'
            )
        return precio

    def clean_stock(self):
        stock = self.cleaned_data['stock']
        if stock < 0:
            raise forms.ValidationError(
                'El stock no puede ser negativo.'
            )
        return stock


# ============================================================
# FORMULARIO CRUD DE SERVICIOS
# ============================================================

class ServicioForm(forms.ModelForm):

    class Meta:
        model = Servicio
        fields = [
            'nombre',
            'descripcion',
            'precio_referencial',
            'estado',
        ]

        widgets = {
            'nombre': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Nombre del servicio'
                }
            ),
            'descripcion': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Descripción del servicio',
                    'rows': 4
                }
            ),
            'precio_referencial': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0',
                    'step': '0.01',
                    'placeholder': 'Precio referencial'
                }
            ),
            'estado': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def clean_precio_referencial(self):
        precio = self.cleaned_data.get('precio_referencial')

        if precio is not None and precio < 0:
            raise forms.ValidationError(
                'El precio referencial no puede ser negativo.'
            )

        return precio