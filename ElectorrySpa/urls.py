
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Área cliente
    path('', include('mainPage.urls')),

    # Área administración Electorry
    path('administracion/', include('administracion.urls')),
]
