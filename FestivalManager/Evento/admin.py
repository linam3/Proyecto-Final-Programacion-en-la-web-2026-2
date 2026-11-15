# Evento/admin.py
from django.contrib import admin
from .models import Categoria, ConfiguracionSitio, Evento, Actividad, Participacion, AsistenteActividad

from .forms import EventoForm

class ActividadInline(admin.StackedInline):
    model = Actividad
    extra = 0
    exclude = ("creado_por",)
    filter_horizontal = ("coordinadores",)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    form = EventoForm
    list_display = ("nombre", "fecha_inicio", "fecha_fin", "estado")
    list_filter = ("estado",)
    exclude = ("creado_por",)
    filter_horizontal = ("coordinadores",)
    inlines = [ActividadInline]

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        for actividad in formset.save(commit=False):
            if not actividad.creado_por_id:
                actividad.creado_por = request.user
            actividad.save()
        for eliminada in formset.deleted_objects:
            eliminada.delete()
        formset.save_m2m()


@admin.register(Participacion)
class ParticipacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "actividad", "estado", "puntos_otorgados")
    list_filter = ("estado", "actividad__evento")
    readonly_fields = ("token",)

@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ConfiguracionSitio.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register([Categoria, AsistenteActividad])

