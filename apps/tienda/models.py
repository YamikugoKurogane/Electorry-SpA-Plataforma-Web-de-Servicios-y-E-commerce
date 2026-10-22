import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "categoría de producto"
        verbose_name_plural = "categorías de producto"

    def __str__(self):
        return self.nombre


def ruta_imagen_producto(instancia, nombre):
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else "jpg"
    return f"productos/{uuid.uuid4().hex}.{ext}"


class Producto(models.Model):
    """RF-12: producto del e-commerce. Precios en pesos chilenos (enteros), IVA incluido."""

    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.PROTECT, related_name="productos")
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.PositiveIntegerField("precio (IVA incluido)")
    imagen = models.ImageField(upload_to=ruta_imagen_producto, blank=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        indexes = [models.Index(fields=["activo", "categoria"]), models.Index(fields=["nombre"])]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("tienda:detalle", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre)[:150] or "producto"
            slug, n = base, 2
            while Producto.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class EstadoVenta(models.TextChoices):
    PENDIENTE_PAGO = "PENDIENTE_PAGO", "Pendiente de pago"
    PAGADA = "PAGADA", "Pagada"
    CANCELADA = "CANCELADA", "Cancelada"


class Venta(models.Model):
    """RF-13 / RF-14: Venta → Detalle → Producto. Queda «pendiente de pago» hasta confirmar."""

    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    estado = models.CharField(max_length=15, choices=EstadoVenta.choices, default=EstadoVenta.PENDIENTE_PAGO, db_index=True)
    total = models.PositiveIntegerField(default=0)
    nombre_cliente = models.CharField(max_length=150, blank=True)
    direccion_entrega = models.CharField(max_length=250, blank=True)
    telefono_contacto = models.CharField(max_length=20, blank=True)
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)
    pagada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada", "-id"]
        indexes = [models.Index(fields=["cliente", "-creada"])]

    def __str__(self):
        return self.codigo

    @property
    def codigo(self):
        return f"VTA-{self.pk:05d}" if self.pk else "VTA-nueva"

    @property
    def pagable(self):
        return self.estado == EstadoVenta.PENDIENTE_PAGO


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="detalles_venta")
    nombre_producto = models.CharField(max_length=150)  # se congela el nombre y precio al comprar
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(cantidad__gt=0), name="detalle_venta_cantidad_positiva"),
        ]

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
