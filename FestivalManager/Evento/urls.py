from django.urls import path
from . import views

app_name = "evento"

urlpatterns = [
    # Público y participante
    path("", views.lista_eventos, name="lista"),
    path("eventos/<int:pk>/", views.detalle_evento, name="detalle"),
    path("actividades/<int:pk>/", views.detalle_actividad, name="actividad"),
    path("actividades/<int:pk>/inscribirse", views.inscribirse, name="inscribirse"),
    path("actividades/<int:pk>/cancelar", views.cancelar, name="cancelar"),
    path("asistir/<uuid:token>/", views.asistir, name="asistir"),  # destino del QR

    # Panel de coordinadores / administrador
    path("panel/", views.panel, name="panel"),
    path("panel/actividades/<int:pk>/asistencia/", views.asistencia, name="asistencia"),
    path("panel/actividades/<int:pk>/asistencia/<int:participacion_id>/", views.marcar_asistencia_vista, name="marcar"),
    path("panel/actividades/<int:pk>/asistentes/agregar/", views.agregar_asistente, name="agregar_asistente"),
    path("panel/actividades/<int:pk>/asistencia/cerrar/", views.cerrar_asistencia_vista, name="cerrar_asistencia"),
    path("panel/actividades/<int:pk>/qr/", views.qr_actividad, name="qr"),
    path("panel/actividades/<int:pk>/qr/descargar/", views.qr_actividad_descargar, name="qr_descargar"),
    path("panel/actividades/<int:pk>/iniciar/", views.iniciar_actividad, name="iniciar_actividad"),
    path("panel/actividades/<int:pk>/finalizar/", views.finalizar_actividad, name="finalizar_actividad"),
    path("panel/eventos/<int:pk>/actividades/nueva/", views.crear_actividad, name="crear_actividad"),
    path("panel/actividades/<int:pk>/editar/", views.editar_actividad, name="editar_actividad"),
    path("panel/actividades/<int:pk>/cancelar/", views.cancelar_actividad, name="cancelar_actividad"),
    path("panel/eventos/<int:pk>/apariencia/", views.apariencia_evento, name="apariencia_evento"),
    path("panel/eventos/<int:pk>/iniciar/", views.iniciar_evento, name="iniciar_evento"),
    path("panel/eventos/<int:pk>/finalizar/", views.finalizar_evento, name="finalizar_evento"),
    path("panel/eventos/<int:pk>/reporte/", views.reporte_evento, name="reporte"),
    path("panel/eventos/<int:pk>/reporte/csv/", views.reporte_evento_csv, name="reporte_csv"),

    # Panel del administrador general
    path("gestion/", views.gestion, name="gestion"),
    path("gestion/sitio/", views.sitio_config, name="sitio_config"),
    path("gestion/eventos/nuevo/", views.evento_nuevo, name="evento_nuevo"),
    path("gestion/eventos/<int:pk>/editar/", views.evento_editar, name="evento_editar"),
    path("gestion/eventos/<int:pk>/cancelar/", views.evento_cancelar, name="evento_cancelar"),
]