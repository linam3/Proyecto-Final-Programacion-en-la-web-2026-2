"""Cambio automático de estados según la hora (el administrador/coordinador también puede hacerlo a mano)."""
from django.utils import timezone

from .models import Actividad, Evento


def sincronizar_estados():
    ahora = timezone.now()
    hoy = timezone.localdate()

    # 1. Actividades cuya hora de fin ya pasó -> finalizadas (y se cierra la asistencia)
    for a in Actividad.objects.filter(
        estado__in=[Actividad.Estado.PUBLICADO, Actividad.Estado.EN_CURSO],
        fecha_fin__lte=ahora,
    ).exclude(evento__estado__in=[Evento.Estado.BORRADOR, Evento.Estado.CANCELADO]):
        a.finalizar()

    # 2. Actividades cuya hora de inicio ya llegó -> en curso
    Actividad.objects.filter(
        estado=Actividad.Estado.PUBLICADO,
        fecha_inicio__lte=ahora, fecha_fin__gt=ahora,
        evento__estado__in=[Evento.Estado.PUBLICADO, Evento.Estado.EN_CURSO],
    ).update(estado=Actividad.Estado.EN_CURSO)

    # 3. Eventos
    Evento.objects.filter(
        estado__in=[Evento.Estado.PUBLICADO, Evento.Estado.EN_CURSO], fecha_fin__lt=hoy
    ).update(estado=Evento.Estado.FINALIZADO)
    Evento.objects.filter(
        estado=Evento.Estado.PUBLICADO, fecha_inicio__lte=hoy, fecha_fin__gte=hoy
    ).update(estado=Evento.Estado.EN_CURSO)