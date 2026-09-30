from django.urls import reverse

from .models import PasswordResetRequest


# Campanita del topbar (ver includes/topbar.html): corre en TODAS las páginas, así que se
# queda corto y barato. Devuelve una lista plana de notificaciones {icon, text, timestamp, url}
# para que sea fácil sumar más tipos a futuro (ej. avisos de stock bajo) sin tocar el topbar.
def notifications(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    items = []

    can_manage_users = user.is_platform_admin or (user.group_id and user.group.can_access_users)
    if can_manage_users:
        qs = PasswordResetRequest.objects.filter(resolved_at__isnull=True).select_related('user')
        if not user.is_platform_admin:
            qs = qs.filter(user__company_id=user.company_id)

        for r in qs.order_by('-created_at')[:15]:
            items.append({
                'icon': 'fa-key',
                'text': f'{r.user.full_name} olvidó su contraseña.',
                'timestamp': r.created_at,
                'url': reverse('account:update', args=[r.user.id]),
            })

    return {'notifications': items, 'notifications_count': len(items)}
