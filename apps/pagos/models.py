from django.db import models


class EstadoPago(models.TextChoices):
    INICIADO = "INICIADO", "Iniciado"
    APROBADO = "APROBADO", "Aprobado"
    RECHAZADO = "RECHAZADO", "Rechazado"
    ERROR = "ERROR", "Error de comunicación"


class Pago(models.Model):
    """Intento de pago de una venta. NO almacena datos de tarjeta (RNF-SEG-06)."""

    venta = models.ForeignKey("tienda.Venta", on_delete=models.PROTECT, related_name="pagos")
    proveedor = models.CharField(max_length=30)
    token = models.CharField(max_length=200, blank=True, db_index=True)
    monto = models.PositiveIntegerField()
    estado = models.CharField(max_length=10, choices=EstadoPago.choices, default=EstadoPago.INICIADO, db_index=True)
    referencia = models.CharField("referencia del proveedor", max_length=100, blank=True)
    detalle = models.JSONField(default=dict, blank=True)  # respuesta del proveedor, sin datos sensibles
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["proveedor", "token"], condition=~models.Q(token=""), name="pago_proveedor_token_unico")
        ]

    def __str__(self):
        return f"Pago {self.pk} ({self.proveedor}) {self.estado}"

    @property
    def final(self):
        return self.estado in (EstadoPago.APROBADO, EstadoPago.RECHAZADO)
