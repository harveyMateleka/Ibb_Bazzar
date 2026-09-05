"""Services métier centraux (transactions + audit).

Les opérations critiques passent par ces services afin de garantir :
- atomicité (transaction.atomic) ;
- traçabilité (AuditLog) ;
- contrôles métier (désactivation sans suppression, etc.).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction

from .models import AuditLog, Domaine, Role, Succursale, User, UserSuccursale


def compte_de(utilisateur):
    """Retourne le compte Django, qu'on reçoive un profil ou un auth.User."""
    if utilisateur is None:
        return None
    return getattr(utilisateur, 'compte', utilisateur)


class AuditService:
    """Écrit une trace d'audit centralisée."""

    @classmethod
    def auditer(
        cls,
        *,
        utilisateur,
        module,
        action,
        objet_type='',
        objet_id=None,
        ancienne_valeur=None,
        nouvelle_valeur=None,
        motif='',
        succursale=None,
        adresse_ip=None,
    ):
        AuditLog.objects.create(
            utilisateur=compte_de(utilisateur) if getattr(utilisateur, 'pk', None) else None,
            succursale=succursale,
            module=module,
            action=action,
            objet_type=objet_type,
            objet_id=objet_id,
            ancienne_valeur=ancienne_valeur,
            nouvelle_valeur=nouvelle_valeur,
            motif=motif,
            adresse_ip=adresse_ip,
        )


class PermissionService:
    """Référence des permissions applicatives (gérées par Django).

    Les permissions sont déclarées en natif dans les `Meta.permissions` des
    modèles (core, approvisionnement, boutique, immobilisations). Django crée
    alors automatiquement les objets `Permission`, utilisables via
    `user.has_perm('app_label.codename')` et composables par rôle dans l'admin.
    Ce service n'est qu'une référence documentaire et des raccourcis utiles.
    """

    # Exemple de catalogue (les permissions réelles sont créées par Django
    # à partir des Meta.permissions de chaque app).
    CATALOGUE = [
        'core.view_utilisateur', 'core.create_utilisateur', 'core.update_utilisateur',
        'core.activate_utilisateur', 'core.deactivate_utilisateur',
        'core.view_role', 'core.create_role', 'core.update_role', 'core.delete_role',
        'core.view_permission', 'core.view_audit',
        'core.view_succursale', 'core.create_succursale', 'core.update_succursale',
        'core.view_domaine',
        # À venir : approvisionnement.* (Phase 2), boutique.* (Phase 3),
        # asset.* (Phase 4) — ajoutés via Meta.permissions des modèles concernés.
    ]

    @classmethod
    def nb_permissions(cls):
        """Nombre de permissions réellement présentes en base."""
        return Permission.objects.count()


class RoleService:
    """Gestion transactionnelle des rôles."""

    @classmethod
    def creer(cls, nom, code, permissions=None, description='', par=None):
        with transaction.atomic():
            role = Role.objects.create(
                nom=nom,
                code=code,
                description=description,
            )
            if permissions:
                role.permissions.set(permissions)
            AuditService.auditer(
                utilisateur=par,
                module='CORE',
                action='role.create',
                objet_type='Role',
                objet_id=role.pk,
                nouvelle_valeur={'nom': nom, 'code': code},
            )
        return role

    @classmethod
    def definir_permissions(cls, role, permissions, par=None):
        with transaction.atomic():
            anciennes = list(role.permissions.values_list('codename', flat=True))
            role.permissions.set(permissions)
            AuditService.auditer(
                utilisateur=par,
                module='CORE',
                action='role.permissions',
                objet_type='Role',
                objet_id=role.pk,
                ancienne_valeur={'permissions': anciennes},
                nouvelle_valeur={
                    'permissions': list(permissions.values_list('codename', flat=True))
                },
            )
        return role


class SuccursaleService:
    """Gestion transactionnelle des succursales."""

    @classmethod
    def creer(cls, nom, code, adresse='', description='', par=None):
        with transaction.atomic():
            succursale = Succursale.objects.create(
                nom=nom,
                code=code,
                adresse=adresse,
                description=description,
            )
            AuditService.auditer(
                utilisateur=par,
                module='CORE',
                action='succursale.create',
                objet_type='Succursale',
                objet_id=succursale.pk,
                nouvelle_valeur={'nom': nom, 'code': code},
            )
        return succursale


class UserService:
    """Gestion transactionnelle des utilisateurs."""

    @classmethod
    def creer(
        cls,
        *,
        username,
        password,
        nom=None,
        prenom=None,
        email='',
        telephone='',
        fonction='',
        roles=None,
        cree_par=None,
    ):
        with transaction.atomic():
            compte = get_user_model().objects.create_user(
                username=username,
                password=password,
                first_name=prenom or '',
                last_name=nom or '',
                email=email,
            )
            utilisateur, _ = User.objects.update_or_create(
                compte=compte,
                defaults={
                    'telephone': telephone,
                    'fonction': fonction,
                    'cree_par': compte_de(cree_par),
                },
            )
            if roles:
                utilisateur.roles.set(roles)
            AuditService.auditer(
                utilisateur=compte_de(cree_par) or compte,
                module='CORE',
                action='user.create',
                objet_type='User',
                objet_id=utilisateur.pk,
                nouvelle_valeur={'username': username},
            )
        return utilisateur

    @classmethod
    def modifier(cls, utilisateur, par=None, **champs):
        """Modifie des champs du profil avec traçabilité (audit avant/après)."""
        with transaction.atomic():
            ancien = {k: getattr(utilisateur, k) for k in champs if hasattr(utilisateur, k)}
            for k, v in champs.items():
                if hasattr(utilisateur, k):
                    setattr(utilisateur, k, v)
            if champs:
                utilisateur.save(update_fields=[k for k in champs if hasattr(utilisateur, k)])
            AuditService.auditer(
                utilisateur=par,
                module='CORE',
                action='user.update',
                objet_type='User',
                objet_id=utilisateur.pk,
                ancienne_valeur=ancien,
                nouvelle_valeur={k: v for k, v in champs.items() if hasattr(utilisateur, k)},
            )
        return utilisateur

    @classmethod
    def assigner_role(cls, utilisateur, role, par=None):
        with transaction.atomic():
            avant = list(utilisateur.roles.values_list('code', flat=True))
            utilisateur.roles.add(role)
            AuditService.auditer(
                utilisateur=par,
                module='CORE',
                action='user.role_add',
                objet_type='User',
                objet_id=utilisateur.pk,
                ancienne_valeur={'roles': avant},
                nouvelle_valeur={'roles': list(utilisateur.roles.values_list('code', flat=True))},
            )
        return utilisateur

    @classmethod
    def retirer_role(cls, utilisateur, role, par=None):
        with transaction.atomic():
            avant = list(utilisateur.roles.values_list('code', flat=True))
            utilisateur.roles.remove(role)
            AuditService.auditer(
                utilisateur=par,
                module='CORE',
                action='user.role_remove',
                objet_type='User',
                objet_id=utilisateur.pk,
                ancienne_valeur={'roles': avant},
                nouvelle_valeur={'roles': list(utilisateur.roles.values_list('code', flat=True))},
            )
        return utilisateur

    @classmethod
    def affecter_succursale(cls, utilisateur, succursale, domaine, principale=False, role=None, par=None):
        with transaction.atomic():
            compte = getattr(utilisateur, 'compte', utilisateur)
            affectation, cree = UserSuccursale.objects.get_or_create(
                utilisateur=compte,
                succursale=succursale,
                domaine=domaine,
                defaults={'principale': principale, 'role': role},
            )
            if not cree and role is not None:
                affectation.role = role
                affectation.save(update_fields=['role'])
            if principale and cree:
                UserSuccursale.objects.filter(
                    utilisateur=compte, principale=True
                ).exclude(pk=affectation.pk).update(principale=False)
            AuditService.auditer(
                utilisateur=par or compte,
                module='CORE',
                action='user.affecter_succursale',
                objet_type='UserSuccursale',
                objet_id=affectation.pk,
                nouvelle_valeur={
                    'succursale': succursale.code,
                    'domaine': domaine.code,
                    'principale': principale,
                },
            )
        return affectation

    @classmethod
    def desaffecter_succursale(cls, affectation, par=None):
        with transaction.atomic():
            AuditService.auditer(
                utilisateur=par or affectation.utilisateur,
                module='CORE',
                action='user.desaffecter_succursale',
                objet_type='UserSuccursale',
                objet_id=affectation.pk,
                ancienne_valeur={
                    'succursale': affectation.succursale.code,
                    'domaine': affectation.domaine.code,
                },
            )
            affectation.delete()
