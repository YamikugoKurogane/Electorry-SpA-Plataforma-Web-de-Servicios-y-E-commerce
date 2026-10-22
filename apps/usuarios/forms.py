import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from apps.core.utils import ip_cliente

from . import services
from .models import Rol, Usuario

TELEFONO_RE = re.compile(r"^\+?[0-9 ()-]{8,20}$")


def validar_telefono(valor):
    if valor and not TELEFONO_RE.match(valor):
        raise ValidationError("Ingresa un teléfono válido, por ejemplo +56 9 1234 5678.")
    return valor


class RegistroForm(forms.ModelForm):
    """RF-01: correo único y campos obligatorios."""

    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(
        label="Repite la contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    acepta_privacidad = forms.BooleanField(
        label="He leído y acepto el aviso de privacidad y el tratamiento de mis datos personales",
        error_messages={"required": "Debes aceptar el aviso de privacidad para registrarte."},
    )

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "telefono"]
        labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Correo electrónico", "telefono": "Teléfono"}
        error_messages = {"email": {"unique": "Ya existe una cuenta con este correo."}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in ("first_name", "last_name", "email"):
            self.fields[nombre].required = True
        self.fields["telefono"].required = True
        self.fields["telefono"].validators.append(validar_telefono)
        self.fields["email"].widget.attrs["autocomplete"] = "email"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con este correo.")
        return email

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            candidato = Usuario(
                email=datos.get("email", ""), first_name=datos.get("first_name", ""), last_name=datos.get("last_name", "")
            )
            try:
                password_validation.validate_password(p1, candidato)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return datos

    def save(self, request=None):
        d = self.cleaned_data
        return services.registrar_cliente(
            email=d["email"], password=d["password1"], first_name=d["first_name"], last_name=d["last_name"],
            telefono=d["telefono"], acepta_privacidad=d["acepta_privacidad"], request=request,
        )


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos.",
        "inactive": "Esta cuenta está inactiva.",
    }

    def clean(self):
        email = (self.cleaned_data.get("username") or "").strip().lower()
        ip = ip_cliente(self.request) if self.request else None
        if email and services.esta_bloqueado(email, ip):
            raise ValidationError(
                "Demasiados intentos fallidos. Espera unos minutos antes de volver a intentarlo.", code="bloqueado"
            )
        self.cleaned_data["username"] = email
        try:
            datos = super().clean()
        except ValidationError:
            services.registrar_intento(email, ip, exitoso=False)
            raise
        services.registrar_intento(email, ip, exitoso=True)
        return datos


class PerfilForm(forms.ModelForm):
    """Rectificación de datos personales (RNF-SEG-07)."""

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "telefono"]
        labels = {"first_name": "Nombre", "last_name": "Apellido", "telefono": "Teléfono"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["telefono"].validators.append(validar_telefono)


class EliminarCuentaForm(forms.Form):
    password = forms.CharField(label="Confirma tu contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

    def clean_password(self):
        if not self.usuario.check_password(self.cleaned_data["password"]):
            raise ValidationError("La contraseña no es correcta.")
        return self.cleaned_data["password"]


class UsuarioPersonalForm(forms.ModelForm):
    """Alta/edición de usuarios y roles por el administrador (RF-10)."""

    password = forms.CharField(
        label="Contraseña", required=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Al crear un usuario es obligatoria. Al editar, déjala vacía para no cambiarla.",
    )

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "telefono", "rol", "is_active"]
        labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Correo electrónico", "telefono": "Teléfono", "rol": "Rol", "is_active": "Activo"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Ya existe un usuario con este correo.")
        return email

    def clean(self):
        datos = super().clean()
        pw = datos.get("password")
        if not self.instance.pk and not pw:
            self.add_error("password", "Define una contraseña para el nuevo usuario.")
        if pw:
            try:
                password_validation.validate_password(pw, self.instance)
            except ValidationError as exc:
                self.add_error("password", exc)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get("password"):
            usuario.set_password(self.cleaned_data["password"])
        elif not usuario.pk:
            usuario.set_unusable_password()
        if commit:
            usuario.save()
        return usuario
