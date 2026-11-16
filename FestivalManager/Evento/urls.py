from django.urls import path
from . import views

app_name = "evento"

urlpatterns = [
    path("", views.lista_eventos, name="lista"),
    path("eventos/<int:pk>/", views.detalle_evento, name="detalle"),
    path("actividades/<int:pk>/", views.detalle_actividad, name="actividad"),
    # Paso 6: inscribirse y cancelar
]