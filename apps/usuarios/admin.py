from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import IntentoLogin, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "rol", "is_active")
    list_filter = ("rol", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "telefono")}),
        ("Acceso", {"fields": ("rol", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Privacidad", {"fields": ("acepta_privacidad", "fecha_privacidad", "anonimizado")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "rol", "password1", "password2")}),)


admin.site.register(IntentoLogin)
