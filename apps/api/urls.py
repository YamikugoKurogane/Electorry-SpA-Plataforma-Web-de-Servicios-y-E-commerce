from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("servicios", views.ServicioViewSet, basename="api-servicio")
router.register("productos", views.ProductoViewSet, basename="api-producto")

urlpatterns = router.urls
