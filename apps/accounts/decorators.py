from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def platform_admin_required(view_func):
    """Deja pasar SOLO al administrador de plataforma (is_platform_admin=True).

    Se usa en la gestión de empresas: ese panel ve TODAS las Company, sin filtrar por empresa.
    Distinto de un usuario de negocio (con company/group propios), que solo ve lo suyo.
    Va siempre debajo de @login_required (asume que request.user ya está autenticado).
    """
    @wraps(view_func)  # conserva nombre/docstring de la vista original (para debug y para Django)
    def wrapper(request, *args, **kwargs):
        # Cualquiera que no sea admin de plataforma se rebota al dashboard con un mensaje.
        if not request.user.is_platform_admin:
            messages.error(request, "No tienes permiso para acceder a esta sección.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper