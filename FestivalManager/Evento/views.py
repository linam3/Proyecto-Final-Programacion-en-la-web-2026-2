from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render

from .models import Actividad, Categoria, Evento

# Estados que el público puede ver (los borradores y cancelados quedan ocultos)
VISIBLES = ["publicado", "en_curso", "finalizado"]


def lista_eventos(request):
    activas = Q(actividades__estado__in=VISIBLES)
    eventos = (
        Evento.objects.filter(estado__in=VISIBLES)
        .annotate(
            num_actividades=Count("actividades", filter=activas),
            puntos_posibles=Sum("actividades__puntos", filter=activas),
        )
        .order_by("fecha_inicio")
    )
    return render(request, "evento/lista.html", {"eventos": eventos})


def detalle_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk, estado__in=VISIBLES)
    actividades = evento.actividades.filter(estado__in=VISIBLES).select_related("categoria")
    puntos_posibles = actividades.aggregate(total=Sum("puntos"))["total"] or 0

    categoria_sel = request.GET.get("categoria", "")
    estado_sel = request.GET.get("estado", "")
    if categoria_sel.isdigit():
        actividades = actividades.filter(categoria_id=categoria_sel)
    if estado_sel in VISIBLES:
        actividades = actividades.filter(estado=estado_sel)

    return render(request, "evento/detalle_evento.html", {
        "evento": evento,
        "actividades": actividades,
        "puntos_posibles": puntos_posibles,
        "categorias": Categoria.objects.all(),
        "estados": [(v, n) for v, n in Actividad.Estado.choices if v in VISIBLES],
        "categoria_sel": categoria_sel,
        "estado_sel": estado_sel,
    })


def detalle_actividad(request, pk):
    actividad = get_object_or_404(
        Actividad.objects.select_related("evento", "categoria"),
        pk=pk, estado__in=VISIBLES, evento__estado__in=VISIBLES,
    )
    participacion = None
    if request.user.is_authenticated:
        participacion = (
            actividad.participaciones.filter(usuario=request.user)
            .exclude(estado="cancelado").first()
        )
    otras = (
        actividad.evento.actividades.filter(estado__in=VISIBLES)
        .exclude(pk=actividad.pk).select_related("categoria")[:3]
    )
    return render(request, "evento/detalle_actividad.html", {
        "actividad": actividad,
        "participacion": participacion,
        "otras": otras,
    })