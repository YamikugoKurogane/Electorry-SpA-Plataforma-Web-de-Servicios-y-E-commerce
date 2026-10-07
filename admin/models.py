
#modelos para la gestion de solicitudes de cotizacion
from django.db import models


class EstadoCotizacion(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    EN_REVISION = 'EN_REVISION', 'En revisión'
    COTIZADA = 'COTIZADA', 'Cotizada'
    ACEPTADA = 'ACEPTADA', 'Aceptada'
    RECHAZADA = 'RECHAZADA', 'Rechazada'
    FINALIZADA = 'FINALIZADA', 'Finalizada'


class GestionEstadoCotizacion(models.Model):
    solicitud = models.ForeignKey(
        'mainPage.SolicitudCotizacion',
        on_delete=models.CASCADE,
        related_name='gestion_estados'
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoCotizacion.choices,
        default=EstadoCotizacion.PENDIENTE
    )

    fecha_cambio = models.DateTimeField(
        auto_now_add=True
    )

    observacion = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['-fecha_cambio']
        verbose_name = 'Gestión de estado de cotización'
        verbose_name_plural = 'Gestión de estados de cotizaciones'

    def __str__(self):
        return f'Solicitud #{self.solicitud_id} - {self.get_estado_display()}'