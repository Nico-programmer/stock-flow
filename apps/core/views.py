from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from apps.companies.models import Company, Branch
from apps.accounts.models import User, Group

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
def _company_dashboard_context(company, exclude_user_id=None):
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

    return {
        'company': company,
        'active_branches': branches_qs.filter(is_active=True).count(),
        'active_users': users_qs.filter(is_active=True).count(),
        'total_groups': Group.objects.filter(company=company).count() if company else 0,
        'colleagues': colleagues_qs.select_related('group').order_by('username')[:8],
        'donut_segments': segments,
        'donut_total': total,
    }


@login_required
def dashboard(request):
    user = request.user

    if user.is_platform_admin:
        companies_qs = Company.objects.order_by('name')
        selected_company_id = request.GET.get('company', '').strip()

        if selected_company_id:
            selected_company = get_object_or_404(Company, id=selected_company_id)
            context = _company_dashboard_context(selected_company)
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

    context = _company_dashboard_context(user.company, exclude_user_id=user.id)
    return render(request, 'dashboard_user.html', context)
