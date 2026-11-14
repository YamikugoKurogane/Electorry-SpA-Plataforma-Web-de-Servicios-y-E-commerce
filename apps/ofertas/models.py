from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

DESCUENTO_MAXIMO = 90  # un descuento mayor casi siempre es un error de digitación


class EstadoOferta(models.TextChoices):
    PROGRAMADA = "PROGRAMADA", "Programada"
    VIGENTE = "VIGENTE", "Vigente"
    VENCIDA = "VENCIDA", "Vencida"
    FINALIZADA = "FINALIZADA", "Finalizada"


class OfertaQuerySet(models.QuerySet):
    def vigentes(self, hoy=None):
        """Ofertas que hoy se pueden aplicar: no finalizadas y dentro de su vigencia (fechas inclusivas)."""
        hoy = hoy or timezone.localdate()
        return self.filter(finalizada_en__isnull=True, fecha_inicio__lte=hoy, fecha_fin__gte=hoy)


class Oferta(models.Model):
    """RF-16: oferta con vigencia sobre productos y/o servicios. RF-17: la ven los clientes mientras está vigente."""

    titulo = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    descuento = models.PositiveSmallIntegerField(
        "descuento (%)", validators=[MinValueValidator(1), MaxValueValidator(DESCUENTO_MAXIMO)]
    )
    fecha_inicio = models.DateField("vigente desde")
    fecha_fin = models.DateField("vigente hasta (inclusive)")
    solo_clientes = models.BooleanField(
        "exclusiva para clientes registrados", default=False,
        help_text="Si se marca, los visitantes sin sesión no la ven ni se les aplica.",
    )
    productos = models.ManyToManyField("tienda.Producto", blank=True, related_name="ofertas")
    servicios = models.ManyToManyField("catalogo.Servicio", blank=True, related_name="ofertas")
    finalizada_en = models.DateTimeField(null=True, blank=True)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    objects = OfertaQuerySet.as_manager()

    class Meta:
        ordering = ["-fecha_inicio", "-id"]
        indexes = [models.Index(fields=["finalizada_en", "fecha_inicio", "fecha_fin"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(fecha_fin__gte=models.F("fecha_inicio")), name="oferta_fechas_coherentes"),
            models.CheckConstraint(
                condition=models.Q(descuento__gte=1) & models.Q(descuento__lte=DESCUENTO_MAXIMO), name="oferta_descuento_entre_1_y_90"
            ),
        ]

    def __str__(self):
        return f"{self.titulo} (−{self.descuento} %)"

    def estado_en(self, hoy=None):
        hoy = hoy or timezone.localdate()
        if self.finalizada_en:
            return EstadoOferta.FINALIZADA
        if hoy < self.fecha_inicio:
            return EstadoOferta.PROGRAMADA
        if hoy > self.fecha_fin:
            return EstadoOferta.VENCIDA
        return EstadoOferta.VIGENTE

    @property
    def estado(self):
        return self.estado_en()

    @property
    def get_estado_display(self):
        return EstadoOferta(self.estado).label

    @property
    def vigente(self):
        return self.estado == EstadoOferta.VIGENTE

    @property
    def editable(self):
        return self.finalizada_en is None  # una oferta vencida se puede reabrir ampliando su fecha de término
