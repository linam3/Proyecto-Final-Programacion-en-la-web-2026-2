from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from .models import Usuario


class RegistroForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "codigo", "first_name", "last_name", "email", "telefono")
        labels = {
            "codigo": "Código estudiantil",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "telefono": "Teléfono",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("first_name", "last_name", "email"):
            self.fields[campo].required = True

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip()


class PerfilForm(forms.ModelForm):
    """Solo se editan datos de contacto. Código, nombres y apellidos los cambia un administrador."""
    class Meta:
        model = Usuario
        fields = ("email", "telefono")
        labels = {"email": "Correo electrónico", "telefono": "Teléfono"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Usuario o contraseña incorrectos.",
    }