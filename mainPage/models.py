from django.db import models


# ============================================================
# ROL
# ============================================================

class Rol(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "rol"
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# ============================================================
# USUARIO
# ============================================================

class Usuario(models.Model):
    id = models.BigAutoField(primary_key=True)

    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        related_name="usuarios"
    )

    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    email = models.EmailField(unique=True)

    telefono = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    password_hash = models.TextField()

    fecha_registro = models.DateTimeField(
        auto_now_add=True
    )

    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "usuario"
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# ============================================================
# CATEGORIA
# ============================================================

class Categoria(models.Model):
    id = models.BigAutoField(primary_key=True)

    nombre = models.CharField(
        max_length=100,
        unique=True
    )

    descripcion = models.TextField(
        blank=True,
        null=True
    )

    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "categoria"
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# ============================================================
# PRODUCTO
# ============================================================

class Producto(models.Model):
    id = models.BigAutoField(primary_key=True)

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="productos"
    )

    nombre = models.CharField(max_length=150)

    descripcion = models.TextField(
        blank=True,
        null=True
    )

    sku = models.CharField(
        max_length=80,
        unique=True,
        blank=True,
        null=True
    )

    precio = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    stock = models.IntegerField(default=0)

    imagen_url = models.TextField(
        blank=True,
        null=True
    )

    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "producto"
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# ============================================================
# SERVICIO
# ============================================================

class Servicio(models.Model):
    id = models.BigAutoField(primary_key=True)

    nombre = models.CharField(max_length=150)

    descripcion = models.TextField(
        blank=True,
        null=True
    )

    precio_referencial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "servicio"
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# ============================================================
# OFERTA
# ============================================================

class Oferta(models.Model):
    id = models.BigAutoField(primary_key=True)

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="ofertas"
    )

    nombre = models.CharField(max_length=150)

    descuento = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    fecha_inicio = models.DateTimeField()

    fecha_fin = models.DateTimeField()

    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "oferta"
        verbose_name = "Oferta"
        verbose_name_plural = "Ofertas"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return self.nombre


# ============================================================
# COTIZACION
# ============================================================

class Cotizacion(models.Model):

    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("EN_REVISION", "En revisión"),
        ("RESPONDIDA", "Respondida"),
        ("ACEPTADA", "Aceptada"),
        ("RECHAZADA", "Rechazada"),
        ("VENCIDA", "Vencida"),
    ]

    id = models.BigAutoField(primary_key=True)

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="cotizaciones"
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="PENDIENTE"
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "cotizacion"
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Cotización #{self.id}"


# ============================================================
# DETALLE COTIZACION
# ============================================================

class DetalleCotizacion(models.Model):
    id = models.BigAutoField(primary_key=True)

    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="detalles_cotizacion",
        blank=True,
        null=True
    )

    cantidad = models.IntegerField()

    precio_referencial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    observacion = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "detalle_cotizacion"
        verbose_name = "Detalle de cotización"
        verbose_name_plural = "Detalles de cotización"

    def __str__(self):
        return f"Detalle cotización #{self.id}"


# ============================================================
# PEDIDO
# ============================================================

class Pedido(models.Model):

    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("PAGADO", "Pagado"),
        ("PREPARANDO", "Preparando"),
        ("ENVIADO", "Enviado"),
        ("ENTREGADO", "Entregado"),
        ("CANCELADO", "Cancelado"),
    ]

    id = models.BigAutoField(primary_key=True)

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name="pedidos"
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="PENDIENTE"
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    class Meta:
        db_table = "pedido"
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Pedido #{self.id}"


# ============================================================
# DETALLE PEDIDO
# ============================================================

class DetallePedido(models.Model):
    id = models.BigAutoField(primary_key=True)

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="detalles_pedido"
    )

    cantidad = models.IntegerField()

    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    class Meta:
        db_table = "detalle_pedido"
        verbose_name = "Detalle de pedido"
        verbose_name_plural = "Detalles de pedido"

    def __str__(self):
        return f"Detalle pedido #{self.id}"


# ============================================================
# MEDIO DE PAGO
# ============================================================

class MedioPago(models.Model):
    id = models.BigAutoField(primary_key=True)

    nombre = models.CharField(
        max_length=80,
        unique=True
    )

    estado = models.BooleanField(default=True)

    class Meta:
        db_table = "medio_pago"
        verbose_name = "Medio de pago"
        verbose_name_plural = "Medios de pago"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# ============================================================
# PAGO
# ============================================================

class Pago(models.Model):

    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("APROBADO", "Aprobado"),
        ("RECHAZADO", "Rechazado"),
        ("ANULADO", "Anulado"),
    ]

    id = models.BigAutoField(primary_key=True)

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.PROTECT,
        related_name="pagos"
    )

    medio_pago = models.ForeignKey(
        MedioPago,
        on_delete=models.PROTECT,
        related_name="pagos"
    )

    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="PENDIENTE"
    )

    codigo_transaccion = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True
    )

    fecha_pago = models.DateTimeField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = "pago"
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-fecha_pago"]

    def __str__(self):
        return f"Pago #{self.id}"


# ============================================================
# CONTACTO
# ============================================================

class Contacto(models.Model):

    ESTADOS = [
        ("NUEVO", "Nuevo"),
        ("EN_REVISION", "En revisión"),
        ("RESPONDIDO", "Respondido"),
        ("CERRADO", "Cerrado"),
    ]

    id = models.BigAutoField(primary_key=True)

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name="contactos",
        blank=True,
        null=True
    )

    nombre = models.CharField(max_length=120)

    email = models.EmailField(max_length=150)

    telefono = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    asunto = models.CharField(max_length=150)

    mensaje = models.TextField()

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADOS,
        default="NUEVO"
    )

    class Meta:
        db_table = "contacto"
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.nombre} - {self.asunto}"

#modelo para solicitud de cotizacion

# ============================================================
# SOLICITUD DE COTIZACIÓN
# ============================================================

class SolicitudCotizacion(models.Model):

    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("EN_REVISION", "En revisión"),
        ("COTIZADA", "Cotizada"),
        ("RECHAZADA", "Rechazada"),
        ]


    TIPOS_SOLICITUD = [
        ("INSTALACION_ELECTRICA", "Instalación eléctrica"),
        ("PANELES_FOTOVOLTAICOS", "Paneles fotovoltaicos"),
        ("MANTENCION_REPARACION", "Mantención y reparación"),
        ("OTRO", "Otro"),
    ]

    id = models.BigAutoField(primary_key=True)

    nombre = models.CharField(
        max_length=100
    )

    apellido = models.CharField(
        max_length=100
    )

    correo = models.EmailField(
        max_length=150
    )

    telefono = models.CharField(
        max_length=30
    )

    tipo_solicitud = models.CharField(
        max_length=50,
        choices=TIPOS_SOLICITUD
    )

    descripcion = models.TextField()

    ubicacion = models.CharField(
        max_length=250
    )

    archivo = models.FileField(
        upload_to="solicitudes_cotizacion/",
        blank=True,
        null=True
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="PENDIENTE"
    )

    class Meta:
        db_table = "solicitud_cotizacion"
        verbose_name = "Solicitud de cotización"
        verbose_name_plural = "Solicitudes de cotización"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Solicitud #{self.id} - {self.nombre} {self.apellido}"