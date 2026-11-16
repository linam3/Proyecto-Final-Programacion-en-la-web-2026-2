from django import forms
from .models import Evento


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = "__all__"
        widgets = {
            "color_primario": forms.TextInput(attrs={"type": "color"}),
            "color_acento": forms.TextInput(attrs={"type": "color"}),
        }