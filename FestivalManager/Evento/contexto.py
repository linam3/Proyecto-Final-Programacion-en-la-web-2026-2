from django.db.utils import OperationalError, ProgrammingError

from .models import ConfiguracionSitio


def sitio(request):
    """Pone `sitio` (nombre, logo, colores) disponible en todas las plantillas."""
    try:
        return {"sitio": ConfiguracionSitio.obtener()}
    except (OperationalError, ProgrammingError):  # antes de migrar
        return {"sitio": ConfiguracionSitio()}