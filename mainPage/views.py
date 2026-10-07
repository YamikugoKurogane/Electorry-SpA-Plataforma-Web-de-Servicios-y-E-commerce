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

# --- Función para generar PDF de Cotización [RF-28] ---
import io
from django.http import HttpResponse
from django.template.loader import get_template
from django.shortcuts import get_object_or_404
from xhtml2pdf import pisa
from .models import Cotizacion

def generar_cotizacion_pdf(request, cotizacion_id):
    cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id)
    template = get_template('cotizaciones/cotizacion_pdf.html')
    context = {'cotizacion': cotizacion, 'empresa': 'Electorry SpA'}
    html = template.render(context)
    
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Cotizacion_Electorry_{cotizacion.id}.pdf"'
        return response
    
    return HttpResponse("Error al generar el PDF", status=500)