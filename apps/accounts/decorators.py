from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect


def superuser_required(view_func):
    """Restringe el acceso solo a superusuarios de la plataforma (tú)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # This only happens if the user has is_superuser=True
        if not request.user.is_superuser:
            messages.error(request, "No tienes permiso para acceder a esta sección.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper