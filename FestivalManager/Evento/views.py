from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from Cuenta.permisos import actividades_de, es_coordinador, eventos_de
from .forms import AsistenteForm, ActividadForm, AparienciaEventoForm
from .models import Actividad, Categoria, Evento, Participacion
import io
import uuid

import qrcode
import qrcode.image.svg
from django.http import JsonResponse
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
@login_required
@require_POST

def inscribirse(request,pk):
    usuario=request.user
    if not request.user.es_participante:
        messages.error(request, "Solo los participantes pueden inscribirse en actividades.")
        return redirect("evento:actividad", pk=pk)
    actividad = get_object_or_404(
    Actividad.objects.select_related("evento", "categoria"),
    pk=pk, estado="publicado",
    )
    participacion=(
                actividad.participaciones.filter(usuario=request.user)
                .first()
            )
    if ( participacion and participacion.estado!="cancelado" ):
        messages.info(request,"Usuario ya inscrito.")
        
    elif (actividad.inscritos >= actividad.cupo):
        messages.error(request,"Cupo máximo excedido.")
    else:
        if participacion:
            participacion.estado="inscrito"
            participacion.save()
        elif participacion==None:
            Participacion.objects.create(usuario=usuario,actividad=actividad)
            messages.success(request,"Inscripción completada con éxito")
    return redirect("evento:actividad",pk=pk)
@login_required
@require_POST
def cancelar(request,pk):
    participacion=get_object_or_404(Participacion,actividad_id=pk,usuario=request.user,estado="inscrito")
    participacion.estado="cancelado"
    participacion.save()
    messages.success(request,"Inscripción cancelada")
    return redirect("evento:actividad",pk=pk)

@login_required
def panel(request):
    if not es_coordinador(request.user):
        raise PermissionDenied
    eventos = eventos_de(request.user).prefetch_related("actividades")
    return render(request, "panel/inicio.html", {"eventos": eventos})
def _actividad_del_panel(request, pk):
    """Devuelve la actividad solo si el usuario puede gestionarla (si no: 403 o 404)."""
    if not es_coordinador(request.user):
        raise PermissionDenied
    return get_object_or_404(actividades_de(request.user).select_related("evento"), pk=pk)


def _rechazar_si_cancelada(request, actividad):
    """Una actividad cancelada no admite cambios de asistencia."""
    if actividad.estado == Actividad.Estado.CANCELADO:
        messages.error(request, "La actividad está cancelada; no se puede modificar la asistencia.")
        return True
    return False


@login_required
def asistencia(request, pk):
    actividad = _actividad_del_panel(request, pk)
    participaciones = (
        actividad.participaciones
        .exclude(estado=Participacion.Estado.CANCELADO)
        .select_related("usuario")
        .order_by("usuario__last_name", "usuario__first_name")
    )
    return render(request, "panel/asistencia.html", {
        "actividad": actividad,
        "participaciones": participaciones,
        "pendientes": participaciones.filter(estado=Participacion.Estado.INSCRITO).count(),
        "asistentes": actividad.asistentes.order_by("-fecha_registro"),
        "form": AsistenteForm(),
    })


@login_required
@require_POST
def marcar_asistencia_vista(request, pk, participacion_id):
    actividad = _actividad_del_panel(request, pk)
    if _rechazar_si_cancelada(request, actividad):
        return redirect("evento:asistencia", pk=actividad.pk)

    participacion = get_object_or_404(
        actividad.participaciones.exclude(estado=Participacion.Estado.CANCELADO).select_related("usuario"),
        pk=participacion_id,
    )
    asistio = request.POST.get("asistio") == "1"
    cambio = participacion.marcar_asistencia(asistio, metodo=Participacion.Metodo.MANUAL)

    nombre = participacion.usuario.get_full_name() or participacion.usuario.username
    if not cambio:
        messages.info(request, f"{nombre} ya tenía la asistencia registrada.")
    elif asistio:
        messages.success(request, f"Asistencia registrada: {nombre} (+{participacion.puntos_otorgados} puntos).")
    else:
        messages.info(request, f"{nombre} quedó como «No asistió».")
    return redirect("evento:asistencia", pk=actividad.pk)


@login_required
@require_POST
def agregar_asistente(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if _rechazar_si_cancelada(request, actividad):
        return redirect("evento:asistencia", pk=actividad.pk)

    form = AsistenteForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa los datos: código, nombres y apellidos son obligatorios.")
    elif actividad.asistentes.filter(codigo=form.cleaned_data["codigo"]).exists():
        messages.error(request, f"El código {form.cleaned_data['codigo']} ya está anotado en esta actividad.")
    else:
        asistente = form.save(commit=False)
        asistente.actividad = actividad
        asistente.save()  # el save() del modelo busca al usuario y le suma los puntos
        if asistente.usuario:
            messages.success(request, f"{asistente.nombres} anotado y vinculado a su cuenta (+{actividad.puntos} puntos).")
        else:
            messages.info(request, f"{asistente.nombres} anotado. No hay una cuenta con ese código, así que no recibe puntos.")
    return redirect("evento:asistencia", pk=actividad.pk)


@login_required
@require_POST
def cerrar_asistencia_vista(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if _rechazar_si_cancelada(request, actividad):
        return redirect("evento:asistencia", pk=actividad.pk)

    cantidad = actividad.cerrar_asistencia()
    messages.success(request, f"Asistencia cerrada: {cantidad} inscrito(s) quedaron como «No asistió».")
    return redirect("evento:asistencia", pk=actividad.pk)

@login_required
def crear_actividad(request, pk):
    if not es_coordinador(request.user):
        raise PermissionDenied
    evento = get_object_or_404(eventos_de(request.user), pk=pk)
    if evento.estado == Evento.Estado.CANCELADO:
        messages.error(request, "No se pueden crear actividades en un evento cancelado.")
        return redirect("evento:panel")

    form = ActividadForm(request.POST or None, request.FILES or None)
    form.instance.evento = evento
    form.instance.creado_por = request.user

    if form.is_valid():
        actividad = form.save()
        messages.success(request, f"Actividad «{actividad.nombre}» creada.")
        return redirect("evento:panel")

    return render(request, "panel/actividad_form.html", {
        "form": form,
        "evento": evento,
        "titulo": "Nueva actividad",
    })


@login_required
def editar_actividad(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if actividad.estado == Actividad.Estado.CANCELADO:
        messages.error(request, "Una actividad cancelada no se puede editar.")
        return redirect("evento:panel")

    form = ActividadForm(request.POST or None, request.FILES or None, instance=actividad)

    if form.is_valid():
        form.save()
        messages.success(request, f"Actividad «{actividad.nombre}» actualizada.")
        return redirect("evento:panel")

    return render(request, "panel/actividad_form.html", {
        "form": form,
        "evento": actividad.evento,
        "titulo": "Editar actividad",
    })


@login_required
@require_POST
def cancelar_actividad(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if actividad.estado == Actividad.Estado.CANCELADO:
        messages.info(request, "La actividad ya estaba cancelada.")
    else:
        actividad.cancelar()
        messages.success(request, f"Actividad «{actividad.nombre}» cancelada.")
    return redirect("evento:panel")

@login_required
def mi_entrada(request, pk):
    participacion = get_object_or_404(
        Participacion.objects.select_related("actividad__evento"),
        actividad_id=pk,
        usuario=request.user,
        estado__in=[Participacion.Estado.INSCRITO, Participacion.Estado.ASISTIO],
    )

    # El QR solo contiene el token: aleatorio e imposible de adivinar
    imagen = qrcode.make(str(participacion.token), image_factory=qrcode.image.svg.SvgPathImage)
    memoria = io.BytesIO()
    imagen.save(memoria)
    svg = memoria.getvalue().decode("utf-8")
    svg = svg[svg.find("<svg"):]  # quita la cabecera <?xml ...?>

    return render(request, "evento/mi_entrada.html", {
        "participacion": participacion,
        "actividad": participacion.actividad,
        "qr_svg": svg,
    })

@login_required
def apariencia_evento(request, pk):
    if not es_coordinador(request.user):
        raise PermissionDenied
    evento = get_object_or_404(eventos_de(request.user), pk=pk)

    form = AparienciaEventoForm(request.POST or None, instance=evento)
    if form.is_valid():
        form.save()
        messages.success(request, f"Apariencia de «{evento.nombre}» actualizada.")
        return redirect("evento:panel")

    return render(request, "panel/apariencia.html", {"form": form, "evento": evento})
# ===== Escaneo de QR (Paso 10, parte B) =====

@login_required
def escanear(request, pk):
    actividad = _actividad_del_panel(request, pk)
    return render(request, "panel/escanear.html", {"actividad": actividad})


@login_required
@require_POST
def registrar_qr(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if actividad.estado == Actividad.Estado.CANCELADO:
        return JsonResponse({"ok": False, "mensaje": "La actividad está cancelada."})

    token = request.POST.get("token", "").strip()
    try:
        uuid.UUID(token)
    except ValueError:
        return JsonResponse({"ok": False, "mensaje": "Ese código no es una entrada de UFEST."})

    participacion = actividad.participaciones.select_related("usuario").filter(token=token).first()
    if participacion is None:
        return JsonResponse({"ok": False, "mensaje": "Esta entrada no corresponde a esta actividad."})
    if participacion.estado == Participacion.Estado.CANCELADO:
        return JsonResponse({"ok": False, "mensaje": "Esta inscripción fue cancelada."})

    nombre = participacion.usuario.get_full_name() or participacion.usuario.username
    if not participacion.marcar_asistencia(True, metodo=Participacion.Metodo.QR):
        return JsonResponse({"ok": True, "repetido": True, "mensaje": f"{nombre} ya tenía la asistencia registrada."})
    return JsonResponse({
        "ok": True,
        "mensaje": f"Asistencia registrada: {nombre} (+{participacion.puntos_otorgados} puntos).",
    })