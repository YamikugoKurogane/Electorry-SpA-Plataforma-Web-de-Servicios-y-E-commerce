import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class Estado(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_REVISION = "EN_REVISION", "En revisión"
    COTIZADA = "COTIZADA", "Cotizada"
    ACEPTADA = "ACEPTADA", "Aceptada"
    EN_EJECUCION = "EN_EJECUCION", "En ejecución"
    FINALIZADA = "FINALIZADA", "Finalizada"
    CANCELADA = "CANCELADA", "Cancelada"


class SolicitudCotizacion(models.Model):
    """RF-03: solicitud de cotización con descripción, ubicación y contacto."""

    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes")
    servicio = models.ForeignKey("catalogo.Servicio", on_delete=models.PROTECT, related_name="solicitudes")
    descripcion = models.TextField("descripción del requerimiento")
    direccion = models.CharField("dirección / ubicación", max_length=250)
    comuna = models.CharField(max_length=100, blank=True)
    nombre_contacto = models.CharField(max_length=150)
    telefono_contacto = models.CharField(max_length=20)
    email_contacto = models.EmailField()
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada", "-id"]
        verbose_name = "solicitud de cotización"
        verbose_name_plural = "solicitudes de cotización"
        indexes = [models.Index(fields=["cliente", "-creada"]), models.Index(fields=["estado", "-creada"])]

    def __str__(self):
        return self.codigo

    @property
    def codigo(self):
        return f"SOL-{self.pk:05d}" if self.pk else "SOL-nueva"

    def get_absolute_url(self):
        return reverse("solicitudes:detalle", kwargs={"pk": self.pk})


def ruta_adjunto(instancia, nombre):
    """Nombre aleatorio: se descarta el nombre original (EC-10)."""
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else "bin"
    return f"adjuntos/{instancia.solicitud_id}/{uuid.uuid4().hex}.{ext}"


class Adjunto(models.Model):
    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.CASCADE, related_name="adjuntos")
    archivo = models.FileField(upload_to=ruta_adjunto, max_length=200)
    nombre_original = models.CharField(max_length=150)
    tamano = models.PositiveIntegerField(default=0)
    subido = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.nombre_original

    @property
    def es_imagen(self):
        return self.archivo.name.lower().endswith((".jpg", ".jpeg", ".png"))


class HistorialEstado(models.Model):
    """Historial de cambios de estado (RF-05, RNF-AUD-01): usuario, fecha, anterior y nuevo."""

    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.CASCADE, related_name="historial")
    estado_anterior = models.CharField(max_length=15, choices=Estado.choices, blank=True)
    estado_nuevo = models.CharField(max_length=15, choices=Estado.choices)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    usuario_nombre = models.CharField(max_length=150, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    comentario = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "historial de estado"
        verbose_name_plural = "historial de estados"
