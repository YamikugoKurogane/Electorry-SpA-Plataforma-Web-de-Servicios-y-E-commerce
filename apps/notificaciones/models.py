from django.db import models


class Notificacion(models.Model):
    """Bandeja de salida de correos (patrón outbox, D8, EC-06).

    Se registra dentro de la transacción del negocio y se envía al confirmarla.
    Si el SMTP falla, queda PENDIENTE y se reintenta; nunca bloquea el flujo.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADA = "ENVIADA", "Enviada"
        FALLIDA = "FALLIDA", "Fallida"

    destinatario = models.EmailField()
    asunto = models.CharField(max_length=200)
    cuerpo = models.TextField()
    evento = models.CharField(max_length=50, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    enviada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return f"{self.asunto} → {self.destinatario} [{self.estado}]"
