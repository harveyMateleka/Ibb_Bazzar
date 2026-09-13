"""Module Utilisateurs & Profil — vues fonctions (FBV).

Chaque action est protégée par une permission granulaire. La désactivation
n'est jamais une suppression : l'historique est conservé.
"""

from django.contrib import messages
from django.contrib.auth.models import Permission
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import UtilisateurForm
from .models import AuditLog, Role, Succursale, User
from .permissions import groupes_permissions_metier, permissions_metier, require_permission
from .services import RoleService, UserService


@require_permission('core.view_utilisateur')
def dashboard(request):
    utilisateurs = User.objects.select_related('compte')
    derniere_activite = AuditLog.objects.select_related(
        'utilisateur', 'succursale'
    )[:10]
    return render(
        request,
        'core/dashboard.html',
        {
            'nb_utilisateurs': utilisateurs.count(),
            'nb_actifs': utilisateurs.filter(compte__is_active=True).count(),
            'nb_inactifs': utilisateurs.filter(compte__is_active=False).count(),
            'utilisateurs': utilisateurs.prefetch_related('roles')[:8],
            'derniere_activite': derniere_activite,
        },
    )


@require_permission('core.view_utilisateur')
def liste(request):
    recherche = request.GET.get('q', '').strip()
    utilisateurs = User.objects.select_related('compte', 'cree_par').prefetch_related(
        'roles',
    )
    if recherche:
        utilisateurs = utilisateurs.filter(
            Q(compte__username__icontains=recherche)
            | Q(compte__first_name__icontains=recherche)
            | Q(compte__last_name__icontains=recherche)
            | Q(compte__email__icontains=recherche)
            | Q(telephone__icontains=recherche)
            | Q(fonction__icontains=recherche)
        )
    return render(
        request,
        'core/utilisateurs.html',
        {'utilisateurs': utilisateurs, 'recherche': recherche},
    )


@require_permission('core.view_utilisateur')
def detail(request, pk):
    utilisateur = get_object_or_404(
        User.objects.select_related('compte', 'cree_par').prefetch_related('roles'),
        pk=pk,
    )
    audits = (
        AuditLog.objects.filter(objet_type='User', objet_id=utilisateur.pk)
        .select_related('utilisateur', 'succursale')[:20]
    )
    return render(
        request,
        'core/utilisateur_detail.html',
        {'utilisateur': utilisateur, 'audits': audits},
    )


@require_permission('core.create_utilisateur')
def utilisateur_nouveau(request):
    formulaire = UtilisateurForm(
        request.POST if request.method == 'POST' else None
    )
    if request.method == 'POST' and formulaire.is_valid():
        user = UserService.creer(
            username=formulaire.cleaned_data['username'],
            password=formulaire.cleaned_data['password'],
            nom=formulaire.cleaned_data['last_name'],
            prenom=formulaire.cleaned_data['first_name'],
            email=formulaire.cleaned_data['email'],
            telephone=formulaire.cleaned_data['telephone'],
            fonction=formulaire.cleaned_data['fonction'],
            roles=formulaire.cleaned_data['roles'],
            cree_par=request.user,
        )
        # Affectation immédiate : succursale + domaine (+ rôle) → l'utilisateur
        # a un périmètre exploitable dès sa création (contexte auto-rempli).
        UserService.affecter_succursale(
            user,
            formulaire.cleaned_data['succursale'],
            formulaire.cleaned_data['domaine'],
            principale=True,
            role=formulaire.cleaned_data.get('role_affectation'),
            par=request.user,
        )
        messages.success(
            request,
            f'Utilisateur {user.username} créé et affecté à '
            f'{formulaire.cleaned_data["succursale"]} / '
            f'{formulaire.cleaned_data["domaine"]}.',
        )
        return redirect('core:utilisateur_detail', pk=user.pk)
    return render(
        request,
        'core/utilisateur_form.html',
        {'form': formulaire},
    )


@require_permission('core.deactivate_utilisateur')
@require_POST
def desactiver(request, pk):
    utilisateur = get_object_or_404(User, pk=pk)
    if utilisateur.pk == request.user.pk:
        messages.error(request, 'Vous ne pouvez pas désactiver votre propre compte.')
    elif utilisateur.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Seul un superutilisateur peut désactiver un superutilisateur.')
    else:
        utilisateur.deactiver(par=request.user)
        messages.success(request, f'{utilisateur} a été désactivé(e).')
    return redirect('core:utilisateur_detail', pk=utilisateur.pk)


@require_permission('core.activate_utilisateur')
@require_POST
def activer(request, pk):
    utilisateur = get_object_or_404(User, pk=pk)
    if utilisateur.is_active:
        messages.info(request, f'{utilisateur} est déjà actif.')
    else:
        utilisateur.activer(par=request.user)
        messages.success(request, f'{utilisateur} a été réactivé(e).')
    return redirect('core:utilisateur_detail', pk=utilisateur.pk)


@require_permission('core.view_role')
def roles(request):
    roles_qs = Role.objects.annotate(nb_utilisateurs=Count('utilisateurs'))
    return render(
        request,
        'core/roles.html',
        {'roles': roles_qs},
    )


@require_permission('core.update_role')
def role_permissions(request, pk):
    role = get_object_or_404(Role, pk=pk)
    groupes = groupes_permissions_metier()
    metier = permissions_metier()
    if request.method == 'POST':
        ids = [int(pk_perm) for pk_perm in request.POST.getlist('permissions') if str(pk_perm).isdigit()]
        choisies = list(metier.filter(pk__in=ids))
        techniques = list(role.permissions.exclude(pk__in=metier.values('pk')))
        RoleService.definir_permissions(role, techniques + choisies, par=request.user)
        messages.success(
            request,
            f'Permissions du profil « {role.nom} » enregistrées. '
            'L’annulation se coche à part de l’enregistrement du document.',
        )
        return redirect('core:role_permissions', pk=role.pk)
    selection = set(role.permissions.values_list('pk', flat=True))
    return render(
        request,
        'core/role_form.html',
        {
            'role': role,
            'groupes': groupes,
            'selection': selection,
        },
    )


@require_permission('core.view_succursale')
def succursales(request):
    succursales_qs = Succursale.objects.annotate(
        nb_utilisateurs=Count('affectations', distinct=True)
    )
    return render(
        request,
        'core/succursales.html',
        {'succursales': succursales_qs},
    )


@require_permission('core.view_permission')
def permissions(request):
    permissions_qs = Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'codename'
    )
    return render(
        request,
        'core/permissions.html',
        {'permissions': permissions_qs},
    )


@require_permission('core.view_audit')
def audit(request):
    traces = AuditLog.objects.select_related('utilisateur', 'succursale')[:50]
    return render(
        request,
        'core/audit.html',
        {'traces': traces},
    )
