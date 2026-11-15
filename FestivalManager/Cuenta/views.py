from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import PerfilForm, RegistroForm


def registro(request):
    if request.user.is_authenticated:
        return redirect("perfil")
    form = RegistroForm(request.POST or None)
    if form.is_valid():
        usuario = form.save()
        login(request, usuario)
        messages.info(request, "Cuenta creada. Un administrador verificará tus datos para que puedas inscribirte.")
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "cuenta/registro.html", {"form": form})


@login_required
def perfil(request):
    participaciones = (
        request.user.participaciones
        .select_related("actividad__evento")
        .order_by("-actividad__evento__fecha_inicio", "actividad__evento_id", "actividad__fecha_inicio")
    )
    return render(request, "cuenta/perfil.html", {"participaciones": participaciones})


@login_required
def editar_perfil(request):
    form = PerfilForm(request.POST or None, instance=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Datos de contacto actualizados.")
        return redirect("perfil")
    return render(request, "cuenta/editar_perfil.html", {"form": form})