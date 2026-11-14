from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegistroForm


def registro(request):
    if request.user.is_authenticated:
        return redirect("perfil")
    form = RegistroForm(request.POST or None)
    if form.is_valid():
        usuario = form.save()
        login(request, usuario)
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

