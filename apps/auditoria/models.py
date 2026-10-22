from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    """Quién, cuándo y qué cambió (RF-15, RNF-AUD-01)."""

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    usuario_email = models.CharField(max_length=254, blank=True)  # se conserva aunque se anonimice
    accion = models.CharField(max_length=30, db_index=True)
    entidad = models.CharField(max_length=40, db_index=True)
    entidad_id = models.PositiveBigIntegerField(null=True, blank=True)
    descripcion = models.CharField(max_length=300, blank=True)
    antes = models.JSONField(null=True, blank=True)
    despues = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        indexes = [models.Index(fields=["entidad", "entidad_id"])]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.accion} {self.entidad}#{self.entidad_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Los registros de auditoría son inmutables.")
        super().save(*args, **kwargs)
