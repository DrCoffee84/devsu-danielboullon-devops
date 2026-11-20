from django.db import DatabaseError, connection
from django.http import JsonResponse


class HealthCheckMiddleware:
    """Responde /healthz y /readyz antes que el resto de los middlewares.

    Va primero en MIDDLEWARE para no pasar por la validación de ALLOWED_HOSTS:
    las probes del kubelet llegan con la IP del pod como Host.

    - /healthz (liveness): el proceso responde. No toca la base, así un
      problema de la DB no hace que Kubernetes reinicie los pods.
    - /readyz (readiness): además hay conexión a la base. Si falla, el pod
      sale del Service hasta que se recupere.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/healthz':
            return JsonResponse({'status': 'ok'})

        if request.path == '/readyz':
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1')
            except DatabaseError:
                return JsonResponse({'status': 'unavailable'}, status=503)
            return JsonResponse({'status': 'ok'})

        return self.get_response(request)
