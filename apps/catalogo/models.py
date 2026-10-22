from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class CategoriaServicio(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=300, blank=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "categoría de servicio"
        verbose_name_plural = "categorías de servicio"

    def __str__(self):
        return self.nombre


class Servicio(models.Model):
    """RF-02 / RF-06: servicio publicado con detalle, categoría y disponibilidad."""

    categoria = models.ForeignKey(CategoriaServicio, on_delete=models.PROTECT, related_name="servicios")
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    resumen = models.CharField(max_length=250)
    descripcion = models.TextField()
    disponible = models.BooleanField("disponible", default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categoria__orden", "nombre"]
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        indexes = [models.Index(fields=["disponible", "categoria"]), models.Index(fields=["nombre"])]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("catalogo:detalle", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre)[:150] or "servicio"
            slug, n = base, 2
            while Servicio.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)
