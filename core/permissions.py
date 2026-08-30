"""Couche d'autorisation : permissions granulaires + périmètre succursale.

Chaque vue backend doit vérifier, dans l'ordre :
1. utilisateur authentifié et actif ;
2. permission requise ;
3. succursale / domaine autorisé ;
4. objet accessible.
Le frontend n'est JAMAIS utilisé comme mécanisme de sécurité.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Domaine


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
                raise PermissionDenied('Compte désactivé.')
            if not request.user.has_perm(codename):
                raise PermissionDenied(
                    f'Vous n’avez pas la permission requise : {codename}'
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def succursales_autorisees(utilisateur, domaine=None):
    """Succursales actives accessibles à l'utilisateur, filtrées par domaine."""
    return utilisateur.succursales_autorisees(domaine=domaine)


def appliquer_contexte(form, contexte):
    """Auto-remplit succursale/domaine et les verrouille (readonly).

    `contexte` est le dict retourné par `User.contexte_actif()`.
    Les champs verrouillés ne sont pas soumis : leurs valeurs doivent être
    réappliquées depuis le contexte dans la vue lors de l'enregistrement.
    """
    if not contexte:
        return form
    for champ in ('succursale', 'domaine'):
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
