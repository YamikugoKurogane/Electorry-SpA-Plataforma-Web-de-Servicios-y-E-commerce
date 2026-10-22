from rest_framework import serializers

from apps.catalogo.models import Servicio
from apps.tienda.models import Producto


class ServicioSerializer(serializers.ModelSerializer):
    categoria = serializers.CharField(source="categoria.nombre")

    class Meta:
        model = Servicio
        fields = ["slug", "nombre", "categoria", "resumen", "descripcion", "disponible"]


class ProductoSerializer(serializers.ModelSerializer):
    categoria = serializers.CharField(source="categoria.nombre")

    class Meta:
        model = Producto
        fields = ["slug", "nombre", "categoria", "descripcion", "precio"]
