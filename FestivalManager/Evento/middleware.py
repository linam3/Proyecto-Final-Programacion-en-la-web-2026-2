import time

from .estados import sincronizar_estados

_ultima = 0.0
INTERVALO = 60  # segundos entre sincronizaciones


class SincronizarEstadosMiddleware:
    """Revisa los estados como máximo una vez por minuto, al llegar cualquier petición."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _ultima
        ahora = time.monotonic()
        if ahora - _ultima > INTERVALO:
            _ultima = ahora
            sincronizar_estados()
        return self.get_response(request)