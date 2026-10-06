from django.shortcuts import render

# Create your views here.
def home(request):
    return render(request, "index.html")

import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .forms import RegistroClienteForm

logger = logging.getLogger('django')

def registro_cliente_view(request):
    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            logger.info(f"Nuevo cliente registrado exitosamente: {user.username} ({user.email})")
            
            login(request, user)
            messages.success(request, f"¡Bienvenido/a {user.first_name}! Registro completado con éxito.")
            return redirect('home')
        else:
            logger.warning("Intento fallido de registro de usuario.")
    else:
        form = RegistroClienteForm()

    return render(request, 'registro.html', {'form': form})

#solicitud de cotizacion
from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import SolicitudCotizacionForm
from .models import GestionEstadoCotizacion, EstadoCotizacion


def solicitar_cotizacion(request):

    if request.method == 'POST':

        form = SolicitudCotizacionForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            solicitud = form.save()

            GestionEstadoCotizacion.objects.create(
                solicitud=solicitud,
                estado=EstadoCotizacion.PENDIENTE,
                observacion='Solicitud creada por el cliente.'
            )

            messages.success(
                request,
                'Su solicitud de cotización fue enviada correctamente.'
            )

            return redirect('main')

    else:

        form = SolicitudCotizacionForm()

    return render(
        request,
        'main.html',
        {
            'form': form
        }
    )