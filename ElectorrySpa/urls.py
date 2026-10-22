
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    # Área cliente y mantenedores personalizados
    path('', include('mainPage.urls')),

    # Django admin (se mantiene disponible en /admin/)
    path('admin/', admin.site.urls),

    # Área administración Electorry
    path('administracion/', include('administracion.urls')),
]
