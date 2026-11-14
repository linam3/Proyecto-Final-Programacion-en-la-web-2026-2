from Evento.models import Evento, Actividad

def es_admin_general(usuario):
    if ( (usuario.rol)=="admin"):
        return True
    else:
        return False
def es_coordinador(usuario):
    if ( (usuario.rol)=="coordinador" or (usuario.rol)=="admin"):
        return True
    else: 
        return False
def eventos_de(usuario):
    if es_admin_general(usuario):
        return Evento.objects.all()
    elif es_coordinador(usuario):
        return Evento.objects.filter(coordinadores=usuario)
    else:
        return Evento.objects.none()
def actividades_de(usuario):
    if es_admin_general(usuario):
        return Actividad.objects.all()
    elif es_coordinador(usuario):
        return Actividad.objects.filter(evento__coordinadores=usuario).all()
    else:
        return Actividad.objects.none()