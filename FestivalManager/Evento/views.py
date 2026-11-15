import csv
import datetime as dt
import io

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.db import transaction

from Cuenta.permisos import actividades_de, es_admin_general, es_coordinador, eventos_de
from .forms import (AsistenteForm, ActividadForm, AparienciaEventoForm, ConfiguracionSitioForm,
                    EventoGestionForm)
from .models import Actividad, Categoria, ConfiguracionSitio, Evento, Participacion

# Estados que el público puede ver (los borradores y cancelados quedan ocultos)
VISIBLES = ["publicado", "en_curso", "finalizado"]


def _fecha(valor):
    """Convierte 'AAAA-MM-DD' en fecha; si viene vacío o mal escrito devuelve None."""
    try:
        return dt.date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def _rango_fechas(request):
    """Lee ?desde=&hasta= y valida que el rango tenga sentido."""
    desde, hasta = _fecha(request.GET.get("desde")), _fecha(request.GET.get("hasta"))
    if desde and hasta and desde > hasta:
        messages.error(request, "La fecha «Desde» no puede ser posterior a «Hasta».")
        return None, None
    return desde, hasta


# ===== Público =====

def lista_eventos(request):
    desde, hasta = _rango_fechas(request)
    activas = Q(actividades__estado__in=VISIBLES)
    eventos = (
        Evento.objects.filter(estado__in=VISIBLES)
        .annotate(
            num_actividades=Count("actividades", filter=activas),
            puntos_posibles=Sum("actividades__puntos", filter=activas),
        )
        .order_by("fecha_inicio")
    )
    if desde:
        eventos = eventos.filter(fecha_fin__gte=desde)   # el evento termina después de «desde»
    if hasta:
        eventos = eventos.filter(fecha_inicio__lte=hasta)  # y empieza antes de «hasta»
    return render(request, "evento/lista.html", {
        "eventos": eventos,
        "desde": desde.isoformat() if desde else "",
        "hasta": hasta.isoformat() if hasta else "",
    })


def detalle_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk, estado__in=VISIBLES)
    actividades = evento.actividades.filter(estado__in=VISIBLES).select_related("categoria")
    puntos_posibles = actividades.aggregate(total=Sum("puntos"))["total"] or 0

    categoria_sel = request.GET.get("categoria", "")
    estado_sel = request.GET.get("estado", "")
    desde, hasta = _rango_fechas(request)
    if categoria_sel.isdigit():
        actividades = actividades.filter(categoria_id=categoria_sel)
    if estado_sel in VISIBLES:
        actividades = actividades.filter(estado=estado_sel)
    if desde:
        actividades = actividades.filter(fecha_inicio__date__gte=desde)
    if hasta:
        actividades = actividades.filter(fecha_inicio__date__lte=hasta)

    return render(request, "evento/detalle_evento.html", {
        "evento": evento,
        "actividades": actividades,
        "puntos_posibles": puntos_posibles,
        "categorias": Categoria.objects.all(),
        "estados": [(v, n) for v, n in Actividad.Estado.choices if v in VISIBLES],
        "categoria_sel": categoria_sel,
        "estado_sel": estado_sel,
        "desde": desde.isoformat() if desde else "",
        "hasta": hasta.isoformat() if hasta else "",
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


# ===== Participante =====

@login_required
@require_POST
def inscribirse(request, pk):
    if not request.user.es_participante:
        messages.error(request, "Solo los participantes pueden inscribirse en actividades.")
        return redirect("evento:actividad", pk=pk)
    if not request.user.verificado:
        messages.error(request, "Tu cuenta aún no ha sido verificada por un administrador, por eso no puedes inscribirte todavía.")
        return redirect("evento:actividad", pk=pk)

    # Bloquea la fila de la actividad durante toda la transacción para que dos
    # usuarios concurrentes no lean el mismo contador de "inscritos".
    with transaction.atomic():
        actividad = get_object_or_404(
            Actividad.objects.select_for_update().select_related("evento", "categoria"),
            pk=pk, estado__in=VISIBLES, evento__estado__in=VISIBLES,
        )

        if not actividad.inscripciones_abiertas:
            messages.error(request, "Las inscripciones para esta actividad no están abiertas.")
            return redirect("evento:actividad", pk=pk)

        participacion = actividad.participaciones.filter(usuario=request.user).first()

        if participacion and participacion.estado != "cancelado":
            messages.info(request, "Ya estás inscrito en esta actividad.")
        # OJO: cupo=None significa "sin límite" -> no comparar con None
        elif actividad.cupo is not None and actividad.inscritos >= actividad.cupo:
            messages.error(request, "Cupo máximo excedido.")
        elif participacion:
            participacion.estado = "inscrito"
            participacion.save()
            messages.success(request, "Inscripción completada con éxito.")
        else:
            Participacion.objects.create(usuario=request.user, actividad=actividad)
            messages.success(request, "Inscripción completada con éxito.")

    return redirect("evento:actividad", pk=pk)


@login_required
@require_POST
def cancelar(request, pk):
    participacion = get_object_or_404(Participacion, actividad_id=pk, usuario=request.user, estado="inscrito")
    participacion.estado = "cancelado"
    participacion.save()
    messages.success(request, "Inscripción cancelada")
    return redirect("evento:actividad", pk=pk)


@login_required
def asistir(request, token):
    """GET: muestra confirmación. POST: registra la asistencia (muta estado)."""
    actividad = get_object_or_404(Actividad.objects.select_related("evento"), token_qr=token)

    # ---------- SALIDA 1: GET ----------
    # Va JUSTO AQUÍ, antes de la lógica de registro.
    if request.method == "GET":
        return render(request, "evento/asistir.html", {
            "actividad": actividad,
            "resultado": None,
            "confirmar": True,
        })

    # ---------- Lógica de registro (solo POST) ----------
    resultado = {"tipo": "error", "mensaje": ""}

    if not request.user.es_participante:
        resultado["mensaje"] = "Solo los participantes registran su asistencia escaneando el código."
    elif actividad.estado == Actividad.Estado.CANCELADO or actividad.evento.estado == Evento.Estado.CANCELADO:
        resultado["mensaje"] = "Esta actividad fue cancelada: no se registra asistencia ni se otorgan puntos."
    elif actividad.estado == Actividad.Estado.FINALIZADO:
        resultado["mensaje"] = "Esta actividad ya terminó. Ya no se puede registrar asistencia."
    elif actividad.estado != Actividad.Estado.EN_CURSO:
        resultado["mensaje"] = "Esta actividad todavía no ha comenzado. Vuelve a escanear cuando inicie."
    else:
        participacion = (
            actividad.participaciones.filter(usuario=request.user)
            .exclude(estado=Participacion.Estado.CANCELADO).first()
        )
        if participacion is None:
            resultado["mensaje"] = "No estás inscrito en esta actividad. Inscríbete antes de escanear."
        elif participacion.marcar_asistencia(True, metodo=Participacion.Metodo.QR):
            resultado = {"tipo": "success", "mensaje": f"¡Asistencia registrada! Ganaste +{participacion.puntos_otorgados} puntos."}
        else:
            resultado = {"tipo": "info", "mensaje": "Tu asistencia ya estaba registrada."}

    # ---------- SALIDA 2: POST (final de la vista) ----------
    # Este SUSTITUYE al return render(...) original que había al final.
    return render(request, "evento/asistir.html", {
        "actividad": actividad,
        "resultado": resultado,
        "confirmar": False,
    })


# ===== Panel de coordinadores y administrador =====

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


def _evento_del_panel(request, pk):
    if not es_coordinador(request.user):
        raise PermissionDenied
    return get_object_or_404(eventos_de(request.user), pk=pk)


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
    evento = _evento_del_panel(request, pk)
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
@require_POST
def iniciar_actividad(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if actividad.iniciar():
        messages.success(request, f"«{actividad.nombre}» está en curso: ya se puede escanear el QR.")
    else:
        messages.error(request, "Solo se puede iniciar una actividad publicada, de un evento publicado o en curso.")
    return redirect("evento:panel")


@login_required
@require_POST
def finalizar_actividad(request, pk):
    actividad = _actividad_del_panel(request, pk)
    if actividad.finalizar():
        messages.success(request, f"«{actividad.nombre}» finalizada. Quien no escaneó el QR quedó como «No asistió».")
    else:
        messages.error(request, "Solo se puede finalizar una actividad publicada o en curso.")
    return redirect("evento:panel")


@login_required
@require_POST
def iniciar_evento(request, pk):
    evento = _evento_del_panel(request, pk)
    if evento.iniciar():
        messages.success(request, f"Evento «{evento.nombre}» en curso.")
    else:
        messages.error(request, "Solo se puede iniciar un evento publicado.")
    return redirect("evento:panel")


@login_required
@require_POST
def finalizar_evento(request, pk):
    evento = _evento_del_panel(request, pk)
    if evento.finalizar():
        messages.success(request, f"Evento «{evento.nombre}» finalizado y sus actividades cerradas.")
    else:
        messages.error(request, "Solo se puede finalizar un evento publicado o en curso.")
    return redirect("evento:panel")


@login_required
def apariencia_evento(request, pk):
    evento = _evento_del_panel(request, pk)
    form = AparienciaEventoForm(request.POST or None, instance=evento)
    if form.is_valid():
        form.save()
        messages.success(request, f"Apariencia de «{evento.nombre}» actualizada.")
        return redirect("evento:panel")
    return render(request, "panel/apariencia.html", {"form": form, "evento": evento})


# ===== QR de la actividad (solo administrador y coordinadores del evento) =====

def _url_asistencia(request, actividad):
    return request.build_absolute_uri(reverse("evento:asistir", args=[actividad.token_qr]))


@login_required
def qr_actividad(request, pk):
    actividad = _actividad_del_panel(request, pk)
    url = _url_asistencia(request, actividad)
    imagen = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
    memoria = io.BytesIO()
    imagen.save(memoria)
    svg = memoria.getvalue().decode("utf-8")
    svg = svg[svg.find("<svg"):]  # quita la cabecera <?xml ...?>
    return render(request, "panel/qr.html", {"actividad": actividad, "qr_svg": svg, "url": url})


@login_required
def qr_actividad_descargar(request, pk):
    actividad = _actividad_del_panel(request, pk)
    imagen = qrcode.make(_url_asistencia(request, actividad), box_size=12, border=4)
    memoria = io.BytesIO()
    imagen.save(memoria, format="PNG")
    respuesta = HttpResponse(memoria.getvalue(), content_type="image/png")
    respuesta["Content-Disposition"] = f'attachment; filename="qr-{slugify(actividad.nombre)[:40] or actividad.pk}.png"'
    return respuesta


# ===== Panel del administrador general =====

def _solo_admin(request):
    if not es_admin_general(request.user):
        raise PermissionDenied


ESTADOS_INSCRITOS = ["inscrito", "asistio", "no_asistio"]


@login_required
def gestion(request):
    _solo_admin(request)
    ruta = "actividades__participaciones"
    eventos = Evento.objects.annotate(
        num_actividades=Count("actividades", distinct=True),
        num_inscritos=Count(ruta, filter=Q(**{ruta + "__estado__in": ESTADOS_INSCRITOS}), distinct=True),
        num_asistentes=Count(ruta, filter=Q(**{ruta + "__estado": "asistio"}), distinct=True),
    ).prefetch_related("coordinadores").order_by("-fecha_inicio")
    return render(request, "gestion/inicio.html", {"eventos": eventos})

@login_required
def sitio_config(request):
    """Nombre, logo, textos de la portada y colores generales del sitio."""
    _solo_admin(request)
    form = ConfiguracionSitioForm(request.POST or None, request.FILES or None, instance=ConfiguracionSitio.obtener())
    if form.is_valid():
        form.save()
        messages.success(request, "Apariencia del sitio actualizada.")
        return redirect("evento:sitio_config")
    return render(request, "gestion/sitio.html", {"form": form})


@login_required
def evento_nuevo(request):
    _solo_admin(request)
    form = EventoGestionForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        evento = form.save(commit=False)
        evento.creado_por = request.user
        evento.save()
        form.save_m2m()
        messages.success(request, f"Evento «{evento.nombre}» creado.")
        return redirect("evento:gestion")
    return render(request, "gestion/evento_form.html", {"form": form, "titulo": "Nuevo evento"})


@login_required
def evento_editar(request, pk):
    _solo_admin(request)
    evento = get_object_or_404(Evento, pk=pk)
    if evento.estado == Evento.Estado.CANCELADO:
        messages.error(request, "Un evento cancelado no se puede editar.")
        return redirect("evento:gestion")
    form = EventoGestionForm(request.POST or None, request.FILES or None, instance=evento)
    if form.is_valid():
        form.save()
        messages.success(request, f"Evento «{evento.nombre}» actualizado.")
        return redirect("evento:gestion")
    return render(request, "gestion/evento_form.html", {"form": form, "titulo": "Editar evento"})


@login_required
def evento_cancelar(request, pk):
    """GET: pide confirmación. POST: cancela el evento y sus actividades."""
    _solo_admin(request)
    evento = get_object_or_404(Evento, pk=pk)
    if evento.estado == Evento.Estado.CANCELADO:
        messages.info(request, "El evento ya estaba cancelado.")
        return redirect("evento:gestion")

    if request.method == "POST":
        evento.cancelar()
        messages.success(request, f"Evento «{evento.nombre}» y sus actividades cancelados.")
        return redirect("evento:gestion")

    participaciones = Participacion.objects.filter(actividad__evento=evento)
    return render(request, "gestion/evento_cancelar.html", {
        "evento": evento,
        "num_actividades": evento.actividades.exclude(estado="cancelado").count(),
        "num_inscritos": participaciones.filter(estado__in=ESTADOS_INSCRITOS).count(),
        "num_asistentes": participaciones.filter(estado="asistio").count(),
        "puntos": participaciones.aggregate(t=Sum("puntos_otorgados"))["t"] or 0,
    })


# ===== Reportes de participación (administrador y coordinadores de ese evento) =====

@login_required
def reporte_evento(request, pk):
    evento = _evento_del_panel(request, pk)
    ruta = "participaciones__estado"
    actividades = evento.actividades.annotate(
        n_inscritos=Count("participaciones", filter=Q(**{ruta + "__in": ESTADOS_INSCRITOS})),
        n_asistieron=Count("participaciones", filter=Q(**{ruta: "asistio"})),
        n_no_asistieron=Count("participaciones", filter=Q(**{ruta: "no_asistio"})),
        n_cancelaron=Count("participaciones", filter=Q(**{ruta: "cancelado"})),
        puntos_dados=Sum("participaciones__puntos_otorgados"),
    ).order_by("fecha_inicio")

    filas = []
    total = {"inscritos": 0, "asistieron": 0, "no_asistieron": 0, "cancelaron": 0, "puntos": 0}
    for a in actividades:
        cancelada = a.estado == Actividad.Estado.CANCELADO or evento.estado == Evento.Estado.CANCELADO
        puntos = 0 if cancelada else (a.puntos_dados or 0)  # en actividades canceladas no se cuentan puntos
        porcentaje = round(100 * a.n_asistieron / a.n_inscritos) if a.n_inscritos else 0
        filas.append({"actividad": a, "inscritos": a.n_inscritos, "asistieron": a.n_asistieron,
                      "no_asistieron": a.n_no_asistieron, "cancelaron": a.n_cancelaron,
                      "puntos": puntos, "porcentaje": porcentaje, "cancelada": cancelada})
        total["inscritos"] += a.n_inscritos
        total["asistieron"] += a.n_asistieron
        total["no_asistieron"] += a.n_no_asistieron
        total["cancelaron"] += a.n_cancelaron
        total["puntos"] += puntos
    total["porcentaje"] = round(100 * total["asistieron"] / total["inscritos"]) if total["inscritos"] else 0
    return render(request, "gestion/reporte.html", {"evento": evento, "filas": filas, "total": total})


@login_required
def reporte_evento_csv(request, pk):
    evento = _evento_del_panel(request, pk)
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="reporte-{slugify(evento.nombre)[:40] or evento.pk}.csv"'
    respuesta.write("\ufeff")  # para que Excel respete las tildes
    w = csv.writer(respuesta)
    w.writerow(["Evento", "Actividad", "Estado actividad", "Código", "Nombre", "Estado participación",
                "Puntos", "Método", "Fecha asistencia"])
    participaciones = (
        Participacion.objects.filter(actividad__evento=evento)
        .select_related("usuario", "actividad").order_by("actividad__fecha_inicio", "usuario__last_name")
    )
    for p in participaciones:
        cancelada = p.actividad.estado == "cancelado" or evento.estado == "cancelado"
        w.writerow([
            evento.nombre, p.actividad.nombre, p.actividad.get_estado_display(), p.usuario.codigo,
            p.usuario.get_full_name() or p.usuario.username, p.get_estado_display(),
            0 if cancelada else p.puntos_otorgados, p.get_metodo_registro_display() if p.metodo_registro else "",
            p.fecha_asistencia.astimezone().strftime("%Y-%m-%d %H:%M") if p.fecha_asistencia else "",
        ])
    return respuesta