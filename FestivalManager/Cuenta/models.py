# cuentas/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Sum


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        PARTICIPANTE = "participante", "Participante"
        COORDINADOR = "coordinador", "Coordinador de actividades"
        ADMIN = "admin", "Administrador general"

    codigo = models.CharField(max_length=20, unique=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.PARTICIPANTE)

    REQUIRED_FIELDS = ["email", "codigo"]

    @property
    def puntos(self):
        total = self.participaciones.aggregate(t=Sum("puntos_otorgados"))["t"]
        return total or 0
    @property
    def es_participante(self):
        return self.rol == self.Rol.PARTICIPANTE

    def __str__(self):
        return f"{self.codigo} - {self.get_full_name() or self.username}"