from django import forms
from .models import Actividad, AsistenteActividad, Evento


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
        # Cancelar se hace con su propio botón, no desde el formulario
        self.fields["estado"].choices = [
            (valor, nombre) for valor, nombre in self.fields["estado"].choices
            if valor != Actividad.Estado.CANCELADO
        ]

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