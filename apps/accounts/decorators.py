from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def superuser_required(view_func):
    """Deja pasar SOLO al superusuario de la plataforma (is_superuser=True).

    Se usa en la gestión de usuarios y empresas: ese panel ve TODO, sin filtrar por empresa.
    Distinto de un 'admin' de negocio (role == 'admin'), que solo vería su propia empresa.
    Va siempre debajo de @login_required (asume que request.user ya está autenticado).
    """
    @wraps(view_func)  # conserva nombre/docstring de la vista original (para debug y para Django)
    def wrapper(request, *args, **kwargs):
        # Cualquiera que no sea superusuario se rebota al dashboard con un mensaje.
        if not request.user.is_superuser:
            messages.error(request, "No tienes permiso para acceder a esta sección.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper