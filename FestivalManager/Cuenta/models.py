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
    telefono = models.CharField(max_length=20, blank=True)
    verificado = models.BooleanField(
        default=False,
        help_text="Márcalo cuando hayas comprobado que el código y el nombre son reales. "
                  "Un participante sin verificar no puede inscribirse.",
    )

    REQUIRED_FIELDS = ["email", "codigo"]

    def save(self, *args, **kwargs):
        # Un superusuario creado con `createsuperuser` nace como administrador general
        if not self.pk and self.is_superuser and self.rol == self.Rol.PARTICIPANTE:
            self.rol = self.Rol.ADMIN
            self.verificado = True
        super().save(*args, **kwargs)

    @property
    def puntos(self):
        # Los puntos de actividades (o eventos) cancelados no cuentan
        total = (
            self.participaciones
            .exclude(actividad__estado="cancelado")
            .exclude(actividad__evento__estado="cancelado")
            .aggregate(t=Sum("puntos_otorgados"))["t"]
        )
        return total or 0

    @property
    def es_participante(self):
        return self.rol == self.Rol.PARTICIPANTE

    def __str__(self):
        return f"{self.codigo} - {self.get_full_name() or self.username}"