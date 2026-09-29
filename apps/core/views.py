from datetime import timedelta

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F
from django.utils import timezone

from apps.companies.models import Company, Branch
from apps.accounts.models import User, Group
from apps.inventory.models import Product, Stock, Movement
from apps.inventory.views import _allowed_branches

# Paleta cíclica de la dona (ver .seg-*/.dot-* en pages/dashboard.css).
DONUT_COLORS = ['purple', 'cyan', 'blue', 'pink', 'orange']


# Arma los segmentos de la dona SVG a partir de pares (label, value).
# r=15.915 en el SVG hace que la circunferencia sea ~100, por eso dash/offset se calculan en "% de 100".
def build_donut(counts):
    total = sum(value for _, value in counts)
    if not total:
        return [], 0

    segments = []
    cumulative = 0
    for (label, value), color in zip(counts, DONUT_COLORS):
        pct = round(value / total * 100, 1)
        segments.append({
            'label': label,
            'value': value,
            'pct': pct,
            'color': color,
            'dash': f'{pct} {100 - pct}',
            'offset': -cumulative,
        })
        cumulative += pct

    return segments, total


# Resumen de UNA empresa: sucursales/usuarios activos, grupos y usuarios por grupo (dona).
# Lo usa tanto el dashboard de un usuario normal (su propia empresa) como el del admin de
# plataforma cuando filtra por una empresa puntual.
def _company_dashboard_context(request, company, exclude_user_id=None):
    branches_qs = Branch.objects.filter(company=company) if company else Branch.objects.none()
    users_qs = User.objects.filter(company=company) if company else User.objects.none()

    # group__name es una property (delega a template.name), no un campo real: hay que agrupar
    # por group__template__name y renombrar la clave.
    groups_count = (
        users_qs
        .values('group__template__name')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    counts = [(row['group__template__name'] or 'Sin grupo', row['total']) for row in groups_count]
    segments, total = build_donut(counts)

    colleagues_qs = users_qs.exclude(id=exclude_user_id) if exclude_user_id else users_qs

    context = {
        'company': company,
        'active_branches': branches_qs.filter(is_active=True).count(),
        'active_users': users_qs.filter(is_active=True).count(),
        'total_groups': Group.objects.filter(company=company).count() if company else 0,
        'colleagues': colleagues_qs.select_related('group').order_by('username')[:8],
        'donut_segments': segments,
        'donut_total': total,
    }

    # Resumen de inventario: solo si puede ver algo de eso (admin de soporte, o su grupo tiene
    # alguno de los 3 permisos). Es un pantallazo general (últimos 7 días, sin filtros); el
    # detalle filtrable vive en Reportes, no acá.
    group = getattr(request.user, 'group', None)
    can_see_inventory = request.user.is_platform_admin or (group and (
        group.can_access_inventory or group.can_manage_inventory or group.can_access_movements
    ))
    context['show_inventory_summary'] = bool(can_see_inventory) and company is not None

    if context['show_inventory_summary']:
        allowed_branches = _allowed_branches(request, company)
        week_ago = timezone.localdate() - timedelta(days=6)

        stock_qs = Stock.objects.filter(branch__in=allowed_branches)
        low_stock_count = (
            stock_qs.filter(quantity__lte=F('product__min_stock'), product__is_active=True)
            .values('product_id').distinct().count()
        )
        movements_qs = Movement.objects.filter(
            company=company, branch__in=allowed_branches, created_at__date__gte=week_ago,
        )

        context.update({
            'total_products': Product.objects.filter(company=company, is_active=True).count(),
            'total_stock_units': stock_qs.aggregate(total=Sum('quantity'))['total'] or 0,
            'low_stock_count': low_stock_count,
            'week_movements_in': sum(m.quantity for m in movements_qs if m.movement_type == Movement.IN),
            'week_movements_out': sum(m.quantity for m in movements_qs if m.movement_type == Movement.OUT),
            'recent_movements': movements_qs.select_related('product', 'branch').order_by('-created_at')[:5],
        })

    return context


@login_required
def dashboard(request):
    user = request.user

    if user.is_platform_admin:
        companies_qs = Company.objects.order_by('name')
        selected_company_id = request.GET.get('company', '').strip()

        if selected_company_id:
            selected_company = get_object_or_404(Company, id=selected_company_id)
            context = _company_dashboard_context(request, selected_company)
        else:
            selected_company = None
            top_companies = (
                companies_qs
                .annotate(user_count=Count('users'))
                .filter(user_count__gt=0)
                .order_by('-user_count')[:5]
            )
            counts = [(c.name, c.user_count) for c in top_companies]

            others = User.objects.filter(is_platform_admin=False).count() - sum(v for _, v in counts)
            if others > 0:
                counts.append(('Otras', others))

            segments, total = build_donut(counts)

            context = {
                'active_companies': companies_qs.filter(is_active=True).count(),
                'inactive_companies': companies_qs.filter(is_active=False).count(),
                'active_users': User.objects.filter(is_platform_admin=False, is_active=True).count(),
                'total_groups': Group.objects.count(),
                'recent_companies': companies_qs.order_by('-created_at')[:5],
                'donut_segments': segments,
                'donut_total': total,
            }

        context['companies'] = companies_qs
        context['selected_company_id'] = selected_company_id
        context['selected_company'] = selected_company
        return render(request, 'dashboard_admin.html', context)

    context = _company_dashboard_context(request, user.company, exclude_user_id=user.id)
    return render(request, 'dashboard_user.html', context)
