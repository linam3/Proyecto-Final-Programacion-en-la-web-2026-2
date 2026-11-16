import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator

color_hex = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Usa un color en formato #RRGGBB.")

class Categoria(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre


class Evento(models.Model):
    color_primario = models.CharField(
        max_length=7, default="#1F3864", validators=[color_hex],
        help_text="Color de la barra, títulos y botones",
    )
    color_acento = models.CharField(
        max_length=7, default="#2e7d32", validators=[color_hex],
        help_text="Color de los puntos y destacados",
    )
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADO = "publicado", "Publicado"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADO = "finalizado", "Finalizado"
        CANCELADO = "cancelado", "Cancelado"

    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=250)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    sede = models.CharField(max_length=120)
    imagen = models.ImageField(upload_to="eventos/", blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="eventos_creados"
    )
    coordinadores = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="eventos_asignados"
    )

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha de fin no puede ser anterior a la de inicio.")

    def cancelar(self):
        """Cancela el evento y, en cascada, todas sus actividades."""
        self.estado = self.Estado.CANCELADO
        self.save()
        self.actividades.update(estado=Actividad.Estado.CANCELADO)

    def __str__(self):
        return self.nombre


class Actividad(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADO = "publicado", "Publicado"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADO = "finalizado", "Finalizado"
        CANCELADO = "cancelado", "Cancelado"

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="actividades")
    nombre = models.CharField(max_length=250)
    descripcion = models.TextField()
    lugar = models.CharField(max_length=120)
    cupo = models.PositiveIntegerField()
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="actividades"
    )
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    imagen = models.ImageField(upload_to="actividades/", blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    puntos = models.PositiveIntegerField(help_text="Puntos que gana quien asiste")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="actividades_creadas"
    )
    coordinadores = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="actividades_asignadas"
    )

    class Meta:
        verbose_name_plural = "actividades"
        ordering = ["fecha_inicio"]
        constraints = [
            models.UniqueConstraint(fields=["evento", "nombre"], name="actividad_unica_por_evento")
        ]

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError("La fecha de fin no puede ser anterior a la de inicio.")
        if self.evento_id and self.fecha_inicio and self.fecha_fin:
            if (self.fecha_inicio.date() < self.evento.fecha_inicio
                    or self.fecha_fin.date() > self.evento.fecha_fin):
                raise ValidationError("La actividad debe estar dentro de las fechas del evento.")

    def cancelar(self):
        self.estado = self.Estado.CANCELADO
        self.save()

    def cerrar_asistencia(self):
        """Al terminar la actividad: quien siguió inscrito y no fue escaneado queda como 'no asistió'."""
        return self.participaciones.filter(estado=Participacion.Estado.INSCRITO).update(
            estado=Participacion.Estado.NO_ASISTIO, puntos_otorgados=0
        )

    @property
    def inscritos(self):
        return self.participaciones.exclude(estado=Participacion.Estado.CANCELADO).count()

    def __str__(self):
        return f"{self.nombre} ({self.evento})"


class Participacion(models.Model):
    class Estado(models.TextChoices):
        INSCRITO = "inscrito", "Inscrito"
        ASISTIO = "asistio", "Asistió"
        NO_ASISTIO = "no_asistio", "No asistió"
        CANCELADO = "cancelado", "Cancelado"

    class Metodo(models.TextChoices):
        QR = "qr", "QR"
        MANUAL = "manual", "Manual"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participaciones"
    )
    actividad = models.ForeignKey(
        Actividad, on_delete=models.CASCADE, related_name="participaciones"
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.INSCRITO)
    puntos_otorgados = models.PositiveIntegerField(default=0)
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)

    # Asistencia (QR o manual)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fecha_asistencia = models.DateTimeField(null=True, blank=True)
    metodo_registro = models.CharField(max_length=10, choices=Metodo.choices, blank=True)

    class Meta:
        verbose_name_plural = "participaciones"
        unique_together = ("usuario", "actividad")

    def marcar_asistencia(self, asistio: bool, metodo=Metodo.MANUAL):
        """Única puerta para dar o quitar puntos. Devuelve False si ya estaba registrado."""
        if asistio and self.estado == self.Estado.ASISTIO:
            return False  # escanear dos veces no hace nada
        if asistio:
            self.estado = self.Estado.ASISTIO
            self.puntos_otorgados = self.actividad.puntos
            self.fecha_asistencia = timezone.now()
            self.metodo_registro = metodo
        else:
            self.estado = self.Estado.NO_ASISTIO
            self.puntos_otorgados = 0
        self.save()
        return True

    def __str__(self):
        return f"{self.usuario} → {self.actividad} ({self.get_estado_display()})"


class AsistenteActividad(models.Model):
    """Registro manual de respaldo: el coordinador anota a quien asistió."""
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, related_name="asistentes")
    codigo = models.CharField(max_length=20)
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name_plural = "asistentes"
        unique_together = ("actividad", "codigo")

    def save(self, *args, **kwargs):
        self.usuario = get_user_model().objects.filter(codigo=self.codigo).first()
        super().save(*args, **kwargs)
        if self.usuario:
            participacion, _ = Participacion.objects.get_or_create(
                usuario=self.usuario, actividad=self.actividad
            )
            participacion.marcar_asistencia(True, metodo=Participacion.Metodo.MANUAL)

    def __str__(self):
        return f"{self.codigo} - {self.nombres} {self.apellidos}"