from django.db import models


class ConfiguracionSitio(models.Model):
    """Datos públicos editables desde el panel de administración."""

    nombre = models.CharField(max_length=100)
    eslogan = models.CharField(max_length=200)
    email = models.EmailField()
    telefono = models.CharField(max_length=30)
    whatsapp = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=150)
    titulo_inicio = models.CharField(max_length=200)
    texto_inicio = models.TextField()

    class Meta:
        verbose_name = "configuración del sitio"
        verbose_name_plural = "configuración del sitio"

    def __str__(self):
        return "Configuración del sitio"
