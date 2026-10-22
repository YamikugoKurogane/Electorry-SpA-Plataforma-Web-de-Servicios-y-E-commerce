from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Sum


class EstadoCotizacion(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    ENVIADA = "ENVIADA", "Enviada"
    ACEPTADA = "ACEPTADA", "Aceptada"
    RECHAZADA = "RECHAZADA", "Rechazada"
    REEMPLAZADA = "REEMPLAZADA", "Reemplazada"


class Cotizacion(models.Model):
    """RF-08: cotización asociada a una solicitud. Montos en pesos chilenos (enteros)."""

    solicitud = models.ForeignKey("solicitudes.SolicitudCotizacion", on_delete=models.PROTECT, related_name="cotizaciones")
    estado = models.CharField(max_length=12, choices=EstadoCotizacion.choices, default=EstadoCotizacion.BORRADOR, db_index=True)
    validez_hasta = models.DateField("válida hasta", null=True, blank=True)
    observaciones = models.TextField(blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)
    enviada_en = models.DateTimeField(null=True, blank=True)
    respondida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada", "-id"]
        verbose_name = "cotización"
        verbose_name_plural = "cotizaciones"

    def __str__(self):
        return self.codigo

    @property
    def codigo(self):
        return f"COT-{self.pk:05d}" if self.pk else "COT-nueva"

    @property
    def editable(self):
        return self.estado == EstadoCotizacion.BORRADOR

    @property
    def neto(self):
        # Usa las líneas ya precargadas (prefetch) para evitar consultas N+1.
        return sum(l.subtotal for l in self.lineas.all())

    @property
    def iva(self):
        valor = Decimal(self.neto) * Decimal(settings.IVA_PORCENTAJE) / Decimal(100)
        return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def total(self):
        return self.neto + self.iva


class LineaCotizacion(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="lineas")
    descripcion = models.CharField(max_length=250)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.PositiveIntegerField("precio unitario (neto)")

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(check=models.Q(cantidad__gt=0), name="linea_cot_cantidad_positiva")]

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


def total_neto_queryset(qs):
    """Suma neta de un queryset de cotizaciones (para reportes)."""
    return qs.aggregate(t=Sum(F("lineas__cantidad") * F("lineas__precio_unitario")))["t"] or 0
