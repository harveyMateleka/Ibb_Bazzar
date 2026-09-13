"""Couche d'autorisation : permissions granulaires + périmètre succursale.

Chaque vue backend doit vérifier, dans l'ordre :
1. utilisateur authentifié et actif ;
2. permission requise ;
3. succursale / domaine autorisé ;
4. objet accessible.
Le frontend n'est JAMAIS utilisé comme mécanisme de sécurité.
"""

from functools import wraps

from django.apps import apps
from django.contrib.admin import ModelAdmin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Domaine

PERMISSIONS_METIER_GROUPES = (
    ('restauration', 'Restauration'),
    ('approvisionnement', 'Approvisionnement'),
    ('boutique', 'Boutique'),
    ('facturation', 'Facturation'),
    ('immobilisations', 'Immobilisations'),
    ('core', 'Utilisateurs et sécurité'),
)

MESSAGE_ACCES_REFUSE = (
    'Vous n’avez pas le droit pour ce module. '
    'Prière de contacter votre administrateur.'
)


def interdire_suppression_sauf_superuser(utilisateur):
    """Les suppressions sont réservées au superuser."""
    if not getattr(utilisateur, 'is_superuser', False):
        raise PermissionDenied(
            'La suppression est interdite. Seul un superuser peut supprimer un enregistrement.'
        )


def restreindre_suppressions_admin():
    """Admin Django : delete_* uniquement pour le superuser."""
    if getattr(ModelAdmin.has_delete_permission, '_ibb_superuser_only', False):
        return

    def has_delete_permission(self, request, obj=None):
        return bool(getattr(request.user, 'is_superuser', False))

    has_delete_permission._ibb_superuser_only = True
    ModelAdmin.has_delete_permission = has_delete_permission


def permissions_metier():
    """Permissions métier (Meta.permissions), sans add/change/delete Django."""
    filtres = Q()
    vide = True
    for model in apps.get_models():
        extra = tuple(model._meta.permissions or ())
        if not extra:
            continue
        ct = ContentType.objects.get_for_model(model, for_concrete_model=False)
        for codename, _libelle in extra:
            vide = False
            filtres |= Q(content_type_id=ct.pk, codename=codename)
    if vide:
        return Permission.objects.none()
    return Permission.objects.filter(filtres).select_related('content_type').order_by(
        'content_type__app_label', 'codename'
    )


def groupes_permissions_metier():
    """Permissions métier regroupées par module, pour l’écran des profils."""
    par_app = {}
    for perm in permissions_metier():
        par_app.setdefault(perm.content_type.app_label, []).append(perm)
    groupes = []
    for app_label, libelle in PERMISSIONS_METIER_GROUPES:
        perms = par_app.pop(app_label, [])
        if not perms:
            continue
        groupes.append({
            'app_label': app_label,
            'libelle': libelle,
            'permissions': [
                {
                    'perm': perm,
                    'est_annulation': perm.codename.startswith('cancel_'),
                }
                for perm in perms
            ],
        })
    for app_label, perms in sorted(par_app.items()):
        groupes.append({
            'app_label': app_label,
            'libelle': app_label.title(),
            'permissions': [
                {
                    'perm': perm,
                    'est_annulation': perm.codename.startswith('cancel_'),
                }
                for perm in perms
            ],
        })
    return groupes


def require_permission(codename):
    """Décorateur : authentifie + vérifie la permission granulaire.

    `codename` peut être une permission Django ('approvisionnement.view_article')
    ou une permission du catalogue ('core.view_audit').
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_active:
                raise PermissionDenied(
                    'Votre compte est désactivé. Prière de contacter votre administrateur.'
                )
            if not request.user.has_perm(codename):
                raise PermissionDenied(MESSAGE_ACCES_REFUSE)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def succursales_autorisees(utilisateur, domaine=None):
    """Succursales actives accessibles à l'utilisateur, filtrées par domaine."""
    from .models import Succursale, User, UserSuccursale
    from .services import compte_de

    if isinstance(utilisateur, User):
        return utilisateur.succursales_autorisees(domaine=domaine)
    profil = getattr(utilisateur, 'profil', None)
    if profil is not None:
        return profil.succursales_autorisees(domaine=domaine)
    if getattr(utilisateur, 'is_superuser', False):
        return Succursale.objects.filter(actif=True)
    qs = UserSuccursale.objects.filter(
        utilisateur=compte_de(utilisateur),
        succursale__actif=True,
    )
    if domaine is not None:
        qs = qs.filter(domaine=domaine)
    return Succursale.objects.filter(pk__in=qs.values('succursale_id'))


def appliquer_contexte(form, contexte):
    """Auto-remplit succursale/domaine et les verrouille (readonly).

    `contexte` est le dict retourné par `User.contexte_actif()`.
    Les champs verrouillés ne sont pas soumis : leurs valeurs doivent être
    réappliquées depuis le contexte dans la vue lors de l'enregistrement.
    """
    if not contexte:
        return form
    for champ in ('succursale', 'domaine'):
        if champ not in form.fields:
            continue
        valeur = contexte.get(champ)
        if valeur is not None:
            form.fields[champ].initial = valeur
        if contexte.get('verrouille'):
            form.fields[champ].disabled = True
            form.fields[champ].help_text = 'Déterminé automatiquement depuis votre périmètre.'
    return form


def domaine_par_code(code):
    try:
        return Domaine.objects.get(code=code)
    except Domaine.DoesNotExist:
        return None
