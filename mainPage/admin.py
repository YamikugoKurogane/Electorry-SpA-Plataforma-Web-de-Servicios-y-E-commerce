from django.contrib import admin

from .models import (
    Rol,
    Usuario,
    Categoria,
    Producto,
    Servicio,
    Oferta,
    Cotizacion,
    DetalleCotizacion,
    Pedido,
    DetallePedido,
    MedioPago,
    Pago,
    Contacto,
)


# ============================================================
# ROL
# ============================================================

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "descripcion",
    )

    search_fields = (
        "nombre",
        "descripcion",
    )

    ordering = ("nombre",)


# ============================================================
# USUARIO
# ============================================================

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "apellido",
        "email",
        "telefono",
        "rol",
        "estado",
        "fecha_registro",
    )

    search_fields = (
        "nombre",
        "apellido",
        "email",
        "telefono",
    )

    list_filter = (
        "rol",
        "estado",
        "fecha_registro",
    )

    ordering = ("-fecha_registro",)


# ============================================================
# CATEGORIA
# ============================================================

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "estado",
    )

    search_fields = (
        "nombre",
        "descripcion",
    )

    list_filter = (
        "estado",
    )

    ordering = ("nombre",)


# ============================================================
# PRODUCTO
# ============================================================

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "categoria",
        "sku",
        "precio",
        "stock",
        "estado",
    )

    search_fields = (
        "nombre",
        "sku",
        "descripcion",
    )

    list_filter = (
        "categoria",
        "estado",
    )

    ordering = ("nombre",)

    list_per_page = 20


# ============================================================
# SERVICIO
# ============================================================

@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "precio_referencial",
        "estado",
    )

    search_fields = (
        "nombre",
        "descripcion",
    )

    list_filter = (
        "estado",
    )

    ordering = ("nombre",)


# ============================================================
# OFERTA
# ============================================================

@admin.register(Oferta)
class OfertaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "producto",
        "descuento",
        "fecha_inicio",
        "fecha_fin",
        "estado",
    )

    search_fields = (
        "nombre",
        "producto__nombre",
    )

    list_filter = (
        "estado",
        "fecha_inicio",
        "fecha_fin",
    )

    ordering = ("-fecha_inicio",)


# ============================================================
# COTIZACION
# ============================================================

@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "fecha_creacion",
        "estado",
    )

    search_fields = (
        "usuario__nombre",
        "usuario__apellido",
        "usuario__email",
        "observaciones",
    )

    list_filter = (
        "estado",
        "fecha_creacion",
    )

    ordering = ("-fecha_creacion",)


# ============================================================
# DETALLE DE COTIZACION
# ============================================================

@admin.register(DetalleCotizacion)
class DetalleCotizacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cotizacion",
        "producto",
        "cantidad",
        "precio_referencial",
    )

    search_fields = (
        "cotizacion__id",
        "producto__nombre",
    )

    ordering = ("-id",)


# ============================================================
# PEDIDO
# ============================================================

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "usuario",
        "fecha_creacion",
        "estado",
        "total",
    )

    search_fields = (
        "usuario__nombre",
        "usuario__apellido",
        "usuario__email",
    )

    list_filter = (
        "estado",
        "fecha_creacion",
    )

    ordering = ("-fecha_creacion",)


# ============================================================
# DETALLE DE PEDIDO
# ============================================================

@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pedido",
        "producto",
        "cantidad",
        "precio_unitario",
    )

    search_fields = (
        "pedido__id",
        "producto__nombre",
    )

    ordering = ("-id",)


# ============================================================
# MEDIO DE PAGO
# ============================================================

@admin.register(MedioPago)
class MedioPagoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "estado",
    )

    search_fields = (
        "nombre",
    )

    list_filter = (
        "estado",
    )

    ordering = ("nombre",)


# ============================================================
# PAGO
# ============================================================

@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pedido",
        "medio_pago",
        "monto",
        "estado",
        "codigo_transaccion",
        "fecha_pago",
    )

    search_fields = (
        "codigo_transaccion",
        "pedido__id",
        "pedido__usuario__email",
    )

    list_filter = (
        "estado",
        "medio_pago",
        "fecha_pago",
    )

    ordering = ("-fecha_pago",)


# ============================================================
# CONTACTO
# ============================================================

@admin.register(Contacto)
class ContactoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nombre",
        "email",
        "telefono",
        "asunto",
        "estado",
        "fecha_creacion",
    )

    search_fields = (
        "nombre",
        "email",
        "telefono",
        "asunto",
        "mensaje",
    )

    list_filter = (
        "estado",
        "fecha_creacion",
    )

    ordering = ("-fecha_creacion",)