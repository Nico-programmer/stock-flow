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


def inventory_access_required(view_func):
    """Deja pasar al admin de plataforma (soporte, ve cualquier empresa) o a un usuario de
    negocio cuyo grupo tenga can_access_inventory. Va siempre debajo de @login_required."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        has_access = user.is_platform_admin or (user.group_id and user.group.can_access_inventory)
        if not has_access:
            messages.error(request, "No tienes permiso para acceder a esta sección.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper