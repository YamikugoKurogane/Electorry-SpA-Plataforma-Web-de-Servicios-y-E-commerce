from django.contrib import admin

from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("creada", "destinatario", "asunto", "estado", "intentos")
    list_filter = ("estado", "evento")
    search_fields = ("destinatario", "asunto")
