from rest_framework import viewsets

from apps.catalogo.models import Servicio
from apps.tienda.models import Producto

from .serializers import ProductoSerializer, ServicioSerializer


class ServicioViewSet(viewsets.ReadOnlyModelViewSet):
    """API pública de solo lectura del catálogo (D2). Solo expone datos ya públicos."""

    serializer_class = ServicioSerializer
    lookup_field = "slug"
    queryset = Servicio.objects.select_related("categoria").filter(categoria__activa=True)


class ProductoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductoSerializer
    lookup_field = "slug"
    queryset = Producto.objects.select_related("categoria").filter(activo=True, categoria__activa=True)
