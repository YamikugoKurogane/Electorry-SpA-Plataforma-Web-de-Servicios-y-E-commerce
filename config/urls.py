from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("cuenta/", include("apps.usuarios.urls")),
    path("servicios/", include("apps.catalogo.urls")),
    path("solicitudes/", include("apps.solicitudes.urls")),
    path("cotizaciones/", include("apps.cotizaciones.urls")),
    path("productos/", include("apps.tienda.urls")),
    path("pagos/", include("apps.pagos.urls")),
    path("panel/", include("apps.panel.urls")),
    path("api/v1/", include("apps.api.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "apps.core.views.error_400"
handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
