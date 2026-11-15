from django import forms
from django.contrib.auth import get_user_model
from .models import Actividad, AsistenteActividad, ConfiguracionSitio, Evento

def _bloquear_estado(form, campo, Estado):
    """Deja elegir solo borrador/publicado. Si ya está en curso o finalizado, el campo queda fijo."""
    if form.instance.pk and form.instance.estado in (Estado.EN_CURSO, Estado.FINALIZADO):
        campo.choices = [(v, n) for v, n in campo.choices if v != Estado.CANCELADO]
        campo.disabled = True
    else:
        campo.choices = [(v, n) for v, n in campo.choices if v in (Estado.BORRADOR, Estado.PUBLICADO)]

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = "__all__"
        widgets = {
            "color_primario": forms.TextInput(attrs={"type": "color"}),
            "color_acento": forms.TextInput(attrs={"type": "color"}),
        }


class ActividadForm(forms.ModelForm):
    class Meta:
        model = Actividad
        fields = (
            "nombre", "descripcion", "lugar", "cupo", "categoria",
            "fecha_inicio", "fecha_fin", "imagen", "estado", "puntos",
        )
        labels = {
            "descripcion": "Descripción",
            "categoria": "Categoría",
            "fecha_inicio": "Inicio",
            "fecha_fin": "Fin",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "fecha_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_fin": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cancelar, iniciar y finalizar se hacen con sus propios botones (o solos, por la hora).
        _bloquear_estado(self, self.fields["estado"], Actividad.Estado)
    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"]
        repetida = (
            Actividad.objects
            .filter(evento_id=self.instance.evento_id, nombre__iexact=nombre)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if repetida:
            raise forms.ValidationError("Ya existe una actividad con ese nombre en este evento.")
        return nombre


class AsistenteForm(forms.ModelForm):
    class Meta:
        model = AsistenteActividad
        fields = ("codigo", "nombres", "apellidos")
        labels = {"codigo": "Código"}
class AparienciaEventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ("color_primario", "color_acento")
        labels = {
            "color_primario": "Color principal",
            "color_acento": "Color de acento",
        }
        widgets = {
            "color_primario": forms.TextInput(attrs={"type": "color"}),
            "color_acento": forms.TextInput(attrs={"type": "color"}),
        }

class EventoGestionForm(forms.ModelForm):
    """Paso 9: el administrador general crea/edita eventos y asigna coordinadores."""
    class Meta:
        model = Evento
        fields = ("nombre", "descripcion", "fecha_inicio", "fecha_fin", "sede",
                  "imagen", "estado", "coordinadores")
        labels = {"descripcion": "Descripción"}
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "coordinadores": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Usuario = get_user_model()
        # Solo se pueden asignar usuarios con rol de coordinador
        self.fields["coordinadores"].queryset = Usuario.objects.filter(rol=Usuario.Rol.COORDINADOR)
        # Cancelar, iniciar y finalizar se hacen con sus propios botones (o solos, por la hora)
        _bloquear_estado(self, self.fields["estado"], Evento.Estado)

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
        if self.instance.pk and inicio and fin:
            fuera = [
                a.nombre for a in self.instance.actividades.exclude(estado=Actividad.Estado.CANCELADO)
                if a.fecha_inicio.date() < inicio or a.fecha_fin.date() > fin
            ]
            if fuera:
                raise forms.ValidationError(
                    "Estas actividades quedarían fuera de las nuevas fechas: " + ", ".join(fuera)
                )
        return datos

class ConfiguracionSitioForm(forms.ModelForm):
    """El administrador general cambia el nombre, el logo y los colores de todo el sitio."""
    class Meta:
        model = ConfiguracionSitio
        fields = ("nombre", "logo", "titulo_portada", "descripcion_portada", "color_primario", "color_acento")
        widgets = {
            "color_primario": forms.TextInput(attrs={"type": "color"}),
            "color_acento": forms.TextInput(attrs={"type": "color"}),
        }